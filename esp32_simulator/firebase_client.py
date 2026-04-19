"""Firebase client for the ESP32 simulator process.

All Firebase Admin SDK calls for the simulator are encapsulated here.
This module is completely independent of ``backend/firebase_client.py`` —
no imports from the ``backend`` package are allowed.

The Firebase Admin SDK is synchronous; every public method wraps its SDK
call in ``asyncio.to_thread()`` so the async polling loop in
``simulator.py`` is never blocked.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import firebase_admin
from firebase_admin import credentials, db


class SimulatorFirebaseClient:
    """Wraps the Firebase Admin SDK Realtime Database for the ESP32 simulator.

    Parameters
    ----------
    credentials_path:
        Absolute or relative path to a Firebase service-account JSON file.
        Pass ``None`` to run without credentials (e.g. against the local
        Firebase emulator via ``FIREBASE_DATABASE_EMULATOR_HOST``).
    database_url:
        The Realtime Database URL, e.g.
        ``"https://<project-id>-default-rtdb.firebaseio.com"``.
    """

    def __init__(self, credentials_path: Optional[str], database_url: str) -> None:
        # Use a named app so this instance never conflicts with any other
        # firebase_admin app that might be initialised in the same process.
        app_name = "esp32_simulator"
        try:
            self._app = firebase_admin.get_app(app_name)
        except ValueError:
            if credentials_path is not None:
                cred = credentials.Certificate(credentials_path)
            else:
                cred = credentials.ApplicationDefault()

            self._app = firebase_admin.initialize_app(
                cred,
                {"databaseURL": database_url},
                name=app_name,
            )

    # ------------------------------------------------------------------
    # Internal sync helpers (run inside asyncio.to_thread)
    # ------------------------------------------------------------------

    def _get_current_mission_id_sync(self) -> Optional[str]:
        ref = db.reference("/missions/current_mission_id", app=self._app)
        value = ref.get()
        if not isinstance(value, str) or not value:
            return None
        return value

    def _get_esp32_command_sync(self, mission_id: str) -> dict:
        ref = db.reference(f"/missions/{mission_id}/esp32_command", app=self._app)
        value = ref.get()
        if not isinstance(value, dict):
            return {}
        return value

    def _write_ack_sync(self, mission_id: str, ack: bool) -> None:
        ref = db.reference(
            f"/missions/{mission_id}/esp32_command/ack", app=self._app
        )
        ref.set(ack)

    def _set_status_sync(self, mission_id: str, status: str) -> None:
        ref = db.reference(f"/missions/{mission_id}/meta/status", app=self._app)
        ref.set(status)

    def _get_path_steps_sync(self, mission_id: str) -> list[dict]:
        ref = db.reference(f"/missions/{mission_id}/path/steps", app=self._app)
        value = ref.get()
        if not isinstance(value, dict):
            return []
        # Firebase returns string keys ("0", "1", "2", …); sort by integer value.
        sorted_steps = [
            value[k] for k in sorted(value.keys(), key=lambda k: int(k))
        ]
        return sorted_steps

    def _write_feedback_sync(
        self,
        mission_id: str,
        step: int,
        action: str,
        heading: float,
        battery: int,
    ) -> None:
        ref = db.reference(f"/missions/{mission_id}/feedback", app=self._app)
        ref.set(
            {
                "current_step": step,
                "action": action,
                "heading": heading,
                "battery": battery,
                "updated_at": db.SERVER_TIMESTAMP,
            }
        )

    def _set_dispatch_sync(self, mission_id: str, value: bool) -> None:
        ref = db.reference(
            f"/missions/{mission_id}/esp32_command/dispatch", app=self._app
        )
        ref.set(value)

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def get_current_mission_id(self) -> Optional[str]:
        """Read ``/missions/current_mission_id`` and return it, or ``None``."""
        return await asyncio.to_thread(self._get_current_mission_id_sync)

    async def get_esp32_command(self, mission_id: str) -> dict:
        """Read ``/missions/{mission_id}/esp32_command/`` and return it as a dict."""
        return await asyncio.to_thread(self._get_esp32_command_sync, mission_id)

    async def write_ack(self, mission_id: str, ack: bool) -> None:
        """Write ``esp32_command/ack`` for the given mission."""
        await asyncio.to_thread(self._write_ack_sync, mission_id, ack)

    async def set_status(self, mission_id: str, status: str) -> None:
        """Write ``meta/status`` for the given mission."""
        await asyncio.to_thread(self._set_status_sync, mission_id, status)

    async def get_path_steps(self, mission_id: str) -> list[dict]:
        """Read all steps from ``/missions/{mission_id}/path/steps/``.

        Returns a list of PathStep dicts sorted by their integer index key.
        Returns an empty list if the node is absent or not a dict.
        """
        return await asyncio.to_thread(self._get_path_steps_sync, mission_id)

    async def write_feedback(
        self,
        mission_id: str,
        step: int,
        action: str,
        heading: float,
        battery: int,
    ) -> None:
        """Write the full feedback node to ``/missions/{mission_id}/feedback/``.

        Fields written: ``current_step``, ``action``, ``heading``,
        ``battery``, and ``updated_at`` (Firebase server timestamp).
        """
        await asyncio.to_thread(
            self._write_feedback_sync, mission_id, step, action, heading, battery
        )

    async def set_dispatch(self, mission_id: str, value: bool) -> None:
        """Write ``esp32_command/dispatch`` for the given mission."""
        await asyncio.to_thread(self._set_dispatch_sync, mission_id, value)
