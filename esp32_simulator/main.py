"""Entry point for the ESP32 simulator process.

Usage
-----
Set the following environment variables before running::

    FIREBASE_CREDENTIALS_PATH=/path/to/serviceAccountKey.json
    FIREBASE_DATABASE_URL=https://<project-id>-default-rtdb.firebaseio.com

Then start the simulator::

    python main.py

The simulator will poll Firebase for dispatched missions and execute them
step-by-step, writing real-time feedback back to Firebase.

This file must not import anything from the ``backend`` package — the
simulator is a completely separate process.
"""

import asyncio
import logging
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

from firebase_client import SimulatorFirebaseClient
import simulator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


def main() -> None:
    credentials_path: str | None = os.environ.get("FIREBASE_CREDENTIALS_PATH")
    database_url: str = os.environ.get(
        "FIREBASE_DATABASE_URL",
        "https://amr-system-nav-default-rtdb.asia-southeast1.firebasedatabase.app",
    )

    if credentials_path:
        logger.info("Initialising Firebase with credentials: %s", credentials_path)
    else:
        logger.info(
            "FIREBASE_CREDENTIALS_PATH not set — using Application Default Credentials "
            "(suitable for emulator or ADC-configured environments)."
        )

    fb = SimulatorFirebaseClient(
        credentials_path=credentials_path,
        database_url=database_url,
    )

    asyncio.run(simulator.run(fb))


if __name__ == "__main__":
    main()
