"""Firebase client for the AMR Navigation System backend.

All Firebase Admin SDK calls are encapsulated in this module.
No other backend module should import or call the Firebase SDK directly.

Supports two initialisation modes:
  1. Service-account credentials: pass a path to a JSON credentials file.
  2. Emulator / credential-less: pass ``credentials_path=None`` and set the
     ``FIREBASE_DATABASE_EMULATOR_HOST`` environment variable before starting
     the process.  The SDK will connect to the local emulator without any
     credentials.
"""

from __future__ import annotations

from typing import Optional

import firebase_admin
from firebase_admin import credentials, db

from coordinate_utils import MapConfig


class FirebaseClient:
    """Wraps the Firebase Admin SDK Realtime Database for the backend.

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
        # Avoid re-initialising if the default app already exists (e.g. when
        # the module is imported multiple times in tests or hot-reload scenarios).
        try:
            self._app = firebase_admin.get_app()
        except ValueError:
            # No app has been initialised yet — create one now.
            if credentials_path is not None:
                cred = credentials.Certificate(credentials_path)
            else:
                # Credential-less mode: works with the Firebase emulator or
                # when Application Default Credentials are configured in the
                # environment.
                cred = credentials.ApplicationDefault()

            self._app = firebase_admin.initialize_app(
                cred,
                {"databaseURL": database_url},
            )

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    def write_map_config(self, mission_id: str, config: MapConfig) -> None:
        """Write all seven MapConfig fields to ``/missions/{mission_id}/map_config/``.

        Parameters
        ----------
        mission_id:
            The mission identifier used as the Firebase path segment.
        config:
            The ``MapConfig`` dataclass instance to persist.
        """
        ref = db.reference(f"/missions/{mission_id}/map_config")
        ref.set(
            {
                "resolution": config.resolution,
                "width_meters": config.width_meters,
                "height_meters": config.height_meters,
                "grid_width": config.grid_width,
                "grid_height": config.grid_height,
                "origin_x": config.origin_x,
                "origin_y": config.origin_y,
            }
        )

    def write_path(
        self, mission_id: str, steps: list[dict], total_steps: int
    ) -> None:
        """Write path steps and total_steps to Firebase.

        Each step dict is written to
        ``/missions/{mission_id}/path/steps/{index}`` and the aggregate
        ``total_steps`` counter is written to
        ``/missions/{mission_id}/path/total_steps``.

        Parameters
        ----------
        mission_id:
            The mission identifier.
        steps:
            Ordered list of PathStep dicts, each containing at minimum the
            keys ``gx``, ``gy``, ``wx``, ``wy``, and ``heading``.
        total_steps:
            The total number of steps (should equal ``len(steps)``).
        """
        path_ref = db.reference(f"/missions/{mission_id}/path")

        # Write each step individually so that the Firebase node structure
        # matches the schema: path/steps/0, path/steps/1, …
        steps_data: dict[str, dict] = {str(i): step for i, step in enumerate(steps)}

        path_ref.set(
            {
                "total_steps": total_steps,
                "steps": steps_data,
            }
        )

    def set_dispatch(self, mission_id: str, mission_id_val: str) -> None:
        """Set the ESP32 dispatch command fields.

        Writes the following values atomically under
        ``/missions/{mission_id}/esp32_command/``:

        * ``dispatch``   → ``True``
        * ``mission_id`` → ``mission_id_val``
        * ``ack``        → ``False``

        Parameters
        ----------
        mission_id:
            The mission identifier used as the Firebase path segment.
        mission_id_val:
            The mission ID string to embed in the command node (may differ
            from ``mission_id`` in future multi-mission scenarios, but is
            typically the same value).
        """
        ref = db.reference(f"/missions/{mission_id}/esp32_command")
        ref.set(
            {
                "dispatch": True,
                "mission_id": mission_id_val,
                "ack": False,
            }
        )

    def set_status(self, mission_id: str, status: str) -> None:
        """Write the mission status string to ``/missions/{mission_id}/meta/status``.

        Valid status values (from the design): ``"planning"``,
        ``"dispatched"``, ``"in_progress"``, ``"completed"``, ``"aborted"``.

        Parameters
        ----------
        mission_id:
            The mission identifier.
        status:
            The new status string.
        """
        ref = db.reference(f"/missions/{mission_id}/meta/status")
        ref.set(status)

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def get_current_mission_id(self) -> str:
        """Read and return the current mission ID from ``/missions/current_mission_id``.

        Returns
        -------
        str
            The current mission ID stored in Firebase.

        Raises
        ------
        ValueError
            If the node is absent or its value is not a non-empty string.
        """
        ref = db.reference("/missions/current_mission_id")
        value = ref.get()
        if not isinstance(value, str) or not value:
            raise ValueError(
                f"Expected a non-empty string at /missions/current_mission_id, "
                f"got {value!r}"
            )
        return value
