"""ESP32 simulator — mission execution and polling loop.

This module simulates the behaviour of an ESP32 robot controller.  It polls
Firebase for a dispatched mission, executes the path step-by-step (with
turning and moving delays), writes real-time feedback, and marks the mission
complete when all steps have been traversed.

Constants
---------
POLL_INTERVAL_SEC   : seconds between each polling cycle
MOVE_STEP_DELAY_SEC : seconds to wait while "moving" to a step
TURN_DELAY_SEC      : seconds to wait while "turning" before a step
TURN_THRESHOLD_DEG  : minimum heading delta (degrees) that triggers a turn
BATTERY_START       : initial battery level (0–100)
"""

from __future__ import annotations

import asyncio
import logging

from firebase_client import SimulatorFirebaseClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Timing / behaviour constants
# ---------------------------------------------------------------------------

POLL_INTERVAL_SEC: float = 0.2
MOVE_STEP_DELAY_SEC: float = 0.3
TURN_DELAY_SEC: float = 0.8
TURN_THRESHOLD_DEG: float = 15.0
BATTERY_START: int = 100


# ---------------------------------------------------------------------------
# Mission execution
# ---------------------------------------------------------------------------


async def execute_mission(fb: SimulatorFirebaseClient, mission_id: str) -> None:
    """Execute a single dispatched mission end-to-end.

    Steps
    -----
    1. Acknowledge the command and set status to ``"in_progress"``.
    2. Fetch all path steps from Firebase.
    3. For each step, optionally write a ``"turning"`` feedback and wait,
       then write a ``"moving"`` feedback and wait.
    4. Decrement battery by 1 per step (floor at 0).
    5. After all steps, write ``"arrived"`` feedback, set status to
       ``"completed"``, and clear the dispatch flag.

    On an empty path, write ``"error"`` feedback and set status to
    ``"aborted"``.

    Parameters
    ----------
    fb:
        The ``SimulatorFirebaseClient`` instance used for all Firebase I/O.
    mission_id:
        The mission identifier to execute.
    """
    # Step 1 — acknowledge and mark in-progress
    await fb.write_ack(mission_id, ack=True)
    await fb.set_status(mission_id, "in_progress")

    # Step 2 — fetch path steps
    steps = await fb.get_path_steps(mission_id)

    if not steps:
        logger.error("Mission %s has no path steps — aborting.", mission_id)
        await fb.write_feedback(
            mission_id,
            step=0,
            action="error",
            heading=0.0,
            battery=BATTERY_START,
        )
        await fb.set_status(mission_id, "aborted")
        return

    battery = BATTERY_START
    prev_heading: float = steps[0].get("heading", 0.0)

    # Step 3 — iterate steps
    for i, step in enumerate(steps):
        heading: float = float(step.get("heading", 0.0))

        # Turn if heading delta exceeds threshold
        if abs(heading - prev_heading) > TURN_THRESHOLD_DEG:
            await fb.write_feedback(
                mission_id,
                step=i,
                action="turning",
                heading=heading,
                battery=battery,
            )
            await asyncio.sleep(TURN_DELAY_SEC)

        # Move to this step
        await asyncio.sleep(MOVE_STEP_DELAY_SEC)
        await fb.write_feedback(
            mission_id,
            step=i,
            action="moving",
            heading=heading,
            battery=battery,
        )

        # Step 4 — decrement battery
        battery = max(0, battery - 1)
        prev_heading = heading

    # Step 5 — mission complete
    final_step = len(steps) - 1
    final_heading = float(steps[final_step].get("heading", 0.0))

    await fb.write_feedback(
        mission_id,
        step=final_step,
        action="arrived",
        heading=final_heading,
        battery=battery,
    )
    await fb.set_status(mission_id, "completed")
    await fb.set_dispatch(mission_id, False)

    logger.info("Mission %s completed successfully.", mission_id)


# ---------------------------------------------------------------------------
# Polling loop
# ---------------------------------------------------------------------------


async def run(fb: SimulatorFirebaseClient) -> None:
    """Main polling loop for the ESP32 simulator.

    Every ``POLL_INTERVAL_SEC`` seconds the loop:

    1. Reads ``/missions/current_mission_id``.
    2. If a mission ID is present, reads ``esp32_command``.
    3. If ``dispatch == True`` and ``ack == False``, calls
       :func:`execute_mission` for that mission.
    4. On any Firebase read failure, logs the error and waits before
       retrying.

    Parameters
    ----------
    fb:
        The ``SimulatorFirebaseClient`` instance used for all Firebase I/O.
    """
    logger.info("ESP32 simulator polling loop started (interval=%.1fs).", POLL_INTERVAL_SEC)

    while True:
        try:
            mission_id = await fb.get_current_mission_id()

            if mission_id is not None:
                command = await fb.get_esp32_command(mission_id)
                dispatch = command.get("dispatch", False)
                ack = command.get("ack", False)

                if dispatch and not ack:
                    logger.info(
                        "Dispatch received for mission %s — starting execution.",
                        mission_id,
                    )
                    await execute_mission(fb, mission_id)

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Firebase read error in polling loop: %s — retrying in %.1fs.",
                exc,
                POLL_INTERVAL_SEC,
            )

        await asyncio.sleep(POLL_INTERVAL_SEC)
