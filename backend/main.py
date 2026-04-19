"""FastAPI application entry point for the AMR Navigation System backend.

Startup sequence:
  1. Load ``inflated_grid.json`` and ``costmap.json`` via ``costmap_loader``.
  2. Derive ``MapConfig`` from the inflated grid via ``coordinate_utils``.
  3. Publish ``MapConfig`` to Firebase via ``firebase_client``.
  4. Store the inflated grid and ``MapConfig`` in ``app.state`` for use by
     the ``/plan-path`` endpoint.

All Firebase access goes through ``FirebaseClient`` — no direct SDK calls here.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

import coordinate_utils
import costmap_loader
import pathfinder
from coordinate_utils import MapConfig
from firebase_client import FirebaseClient

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class PlanPathRequest(BaseModel):
    """Body for ``POST /plan-path``."""

    mission_id: str
    start: list[float]  # [wx, wy]
    goal: list[float]   # [wx, wy]


class PlanPathResponse(BaseModel):
    """Response for ``POST /plan-path``."""

    status: str
    total_steps: int


# ---------------------------------------------------------------------------
# Firebase client factory
# ---------------------------------------------------------------------------

def _make_firebase_client() -> FirebaseClient:
    """Construct a ``FirebaseClient`` from environment variables.

    ``FIREBASE_CREDENTIALS_PATH`` — path to service-account JSON.
        If absent, ``None`` is passed (emulator / Application Default mode).
    ``FIREBASE_DATABASE_URL`` — Realtime Database URL.
        Defaults to an empty string so the SDK can still be instantiated in
        emulator mode (the emulator host is set via
        ``FIREBASE_DATABASE_EMULATOR_HOST``).
    """
    credentials_path: str | None = os.environ.get("FIREBASE_CREDENTIALS_PATH") or None
    database_url: str = os.environ.get(
        "FIREBASE_DATABASE_URL",
        "https://amr-system-nav-default-rtdb.asia-southeast1.firebasedatabase.app",
    )
    return FirebaseClient(credentials_path=credentials_path, database_url=database_url)


# ---------------------------------------------------------------------------
# Map file paths
# ---------------------------------------------------------------------------

# ``Map_extraction/`` lives one level above ``backend/``.
_MAP_DIR = Path(__file__).parent.parent / "Map_extraction"
_INFLATED_GRID_PATH = str(_MAP_DIR / "inflated_grid.json")
_COSTMAP_PATH = str(_MAP_DIR / "costmap.json")


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager.

    Runs the startup sequence before yielding control to the application, and
    any teardown logic after the ``yield`` (currently none needed).
    """
    # 1. Load map files
    inflated_grid, inflated_meta = costmap_loader.load_map(_INFLATED_GRID_PATH)
    _costmap_grid, _costmap_meta = costmap_loader.load_map(_COSTMAP_PATH)

    # 2. Derive MapConfig from the inflated grid (used for path planning)
    map_config: MapConfig = coordinate_utils.build_map_config(inflated_grid, inflated_meta)

    # 3. Publish MapConfig to Firebase
    firebase: FirebaseClient = _make_firebase_client()
    try:
        mission_id = firebase.get_current_mission_id()
        firebase.write_map_config(mission_id, map_config)
    except Exception as exc:  # noqa: BLE001
        # Firebase may be unavailable (e.g. no credentials / emulator not
        # running).  Log the error but do not prevent the server from starting
        # so that the planning endpoints can still be exercised locally.
        print(f"[startup] Firebase write_map_config skipped: {exc}")

    # 4. Store shared state for use by endpoints
    app.state.inflated_grid = inflated_grid
    app.state.map_config = map_config
    app.state.firebase = firebase

    yield
    # Teardown (nothing to clean up for now)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AMR Navigation System",
    description="FastAPI backend for A* path planning on a real indoor map.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the Flutter app (and any dev tooling) to connect from any origin
# during development.  Restrict origins in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/plan-path", response_model=PlanPathResponse)
async def plan_path_endpoint(body: PlanPathRequest, request: Request) -> PlanPathResponse:
    """Plan a path from ``start`` to ``goal`` using A* on the inflated grid.

    Steps:
      1. Run ``pathfinder.plan_path`` with the stored inflated grid and
         ``MapConfig``.
      2. Write the resulting path to Firebase via ``firebase_client.write_path``.
      3. Set the ESP32 dispatch command and mission status.
      4. Return ``PlanPathResponse(status="dispatched", total_steps=N)``.

    Raises
    ------
    HTTPException(400)
        When ``pathfinder.plan_path`` raises ``ValueError`` (start or goal is
        an obstacle cell).
    HTTPException(422)
        When ``pathfinder.plan_path`` raises ``RuntimeError`` (no path found
        between the two cells).
    """
    inflated_grid: np.ndarray = request.app.state.inflated_grid
    map_config: MapConfig = request.app.state.map_config
    firebase: FirebaseClient = request.app.state.firebase

    start_world = (body.start[0], body.start[1])
    goal_world = (body.goal[0], body.goal[1])

    try:
        steps = pathfinder.plan_path(inflated_grid, map_config, start_world, goal_world)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    total_steps = len(steps)

    firebase.write_path(body.mission_id, steps, total_steps)
    firebase.set_dispatch(body.mission_id, body.mission_id)
    firebase.set_status(body.mission_id, "dispatched")

    return PlanPathResponse(status="dispatched", total_steps=total_steps)


@app.get("/map-config")
async def get_map_config_endpoint(request: Request) -> dict[str, Any]:
    """Return the current ``MapConfig`` as a JSON dict.

    Keys use snake_case to match the Firebase schema:
    ``resolution``, ``width_meters``, ``height_meters``, ``grid_width``,
    ``grid_height``, ``origin_x``, ``origin_y``.
    """
    cfg: MapConfig = request.app.state.map_config
    return {
        "resolution": cfg.resolution,
        "width_meters": cfg.width_meters,
        "height_meters": cfg.height_meters,
        "grid_width": cfg.grid_width,
        "grid_height": cfg.grid_height,
        "origin_x": cfg.origin_x,
        "origin_y": cfg.origin_y,
    }
