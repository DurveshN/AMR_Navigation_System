# AMR Navigation System

A four-actor pipeline that lets a user command a simulated mobile robot through a real indoor environment map. The user taps start and goal positions on an SVG map in a Flutter app; a FastAPI backend runs A* on the real inflated costmap and writes the planned path to Firebase; a standalone Python ESP32 simulator reads the path and replays step-by-step movement feedback; the Flutter app animates the robot icon along the path in real time.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Flutter Mobile App                           │
│  MapScreen ──► MissionController ──► CoordinateTransformer.dart     │
│       │               │                                             │
│  MapPainter      FirebaseService.dart ◄──────────────────────┐      │
│  RobotAnimator        │                                       │      │
│                  ApiClient ──────────────────────────────┐    │      │
└──────────────────────────────────────────────────────────┼────┼──────┘
                                                           │    │
                         HTTP POST /plan-path              │    │
                         ─────────────────────────────────►│    │
┌──────────────────────────────────────────────────────────┼────┼──────┐
│                       FastAPI Backend                    │    │      │
│  main.py ──► pathfinder.py ──► coordinate_utils.py       │    │      │
│       │               │                                  │    │      │
│  costmap_loader.py    └──► firebase_client.py ───────────┼────┘      │
│  (reads Map_extraction/)          │                      │           │
└──────────────────────────────────┼──────────────────────┘           │
                                   │ Firebase Admin SDK                │
                                   ▼                                   │
                    ┌──────────────────────────────┐                   │
                    │     Firebase Realtime DB      │                   │
                    │  /missions/{id}/              │◄──────────────────┘
                    │    map_config/                │   Firebase SDK
                    │    waypoints/                 │
                    │    path/steps/                │
                    │    esp32_command/             │
                    │    feedback/                  │
                    └──────────────┬───────────────┘
                                   │ Firebase Admin SDK
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       ESP32 Simulator                                │
│  main.py ──► simulator.py ──► firebase_client.py                     │
│  (polls dispatch, replays path steps, writes feedback)               │
└──────────────────────────────────────────────────────────────────────┘
```

Communication paths:
- Flutter App ↔ Firebase RTDB: Firebase Realtime Database SDK (reads/writes missions tree)
- Flutter App → FastAPI Backend: HTTP POST `/plan-path`, GET `/map-config`
- FastAPI Backend ↔ Firebase RTDB: Firebase Admin SDK REST
- ESP32 Simulator ↔ Firebase RTDB: Firebase Admin SDK REST (separate process, no shared imports with backend)

---

## Firebase Schema

```
/missions/
  current_mission_id: string          ← written by Flutter app before any planning

  /{mission_id}/
    meta/
      status:      string             ← "planning" | "dispatched" | "in_progress" | "completed" | "aborted"
      created_at:  ServerTimestamp
      updated_at:  ServerTimestamp

    map_config/
      resolution:     float           ← meters per grid cell (e.g. 0.1)
      width_meters:   float           ← total map width in meters
      height_meters:  float           ← total map height in meters
      grid_width:     int             ← number of grid columns
      grid_height:    int             ← number of grid rows
      origin_x:       float           ← world X of grid cell (0,0) in meters
      origin_y:       float           ← world Y of grid cell (0,0) in meters

    waypoints/
      start/
        wx: float                     ← world X in meters
        wy: float
      goal/
        wx: float
        wy: float

    path/
      total_steps: int
      steps/
        /{index}/                     ← "0", "1", "2", ...
          gx:      int
          gy:      int
          wx:      float
          wy:      float
          heading: float              ← degrees, ROS convention (0°=east, CCW positive)

    esp32_command/
      dispatch:    bool               ← set true by backend to trigger simulator
      mission_id:  string
      ack:         bool               ← set true by simulator on receipt

    feedback/
      current_step: int
      action:       string            ← "moving" | "turning" | "arrived" | "obstacle_detected" | "error"
      heading:      float
      battery:      int               ← 0–100
      updated_at:   ServerTimestamp
```

---

## Prerequisites

- **Flutter** SDK ≥ 3.0.0 (`flutter --version`)
- **Python** 3.11+
- A **Firebase project** with Realtime Database enabled
- Firebase service account credentials JSON file

---

## Configuration

### Firebase Credentials

Set two environment variables before starting the backend or simulator:

```bash
export FIREBASE_CREDENTIALS_PATH=/path/to/serviceAccountKey.json
export FIREBASE_DATABASE_URL=https://amr-system-nav-default-rtdb.firebaseio.com
```

On Windows (PowerShell):

```powershell
$env:FIREBASE_CREDENTIALS_PATH = "C:\path\to\serviceAccountKey.json"
$env:FIREBASE_DATABASE_URL = "https://amr-system-nav-default-rtdb.firebaseio.com"
```

The backend auto-detects the `Map_extraction/` directory relative to `backend/main.py`:

```python
MAP_DIR = Path(__file__).parent.parent / "Map_extraction"
```

No path configuration is needed as long as the repository structure is intact.

---

## Run Instructions

The backend and ESP32 simulator are **separate processes** and must be started independently in separate terminals.

### 1. Start the FastAPI Backend

```bash
cd backend
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

uvicorn main:app --reload
```

The backend loads `Map_extraction/inflated_grid.json` and `Map_extraction/costmap.json` at startup, derives all spatial parameters from the JSON metadata, and publishes `map_config` to Firebase. It exposes:
- `POST /plan-path` — run A* and dispatch the path
- `GET /map-config` — return the current map configuration

### 2. Start the ESP32 Simulator

In a **separate terminal**:

```bash
cd esp32_simulator
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

python main.py
```

The simulator polls Firebase every 200 ms for a dispatch command. When `esp32_command/dispatch == true`, it reads the planned path steps and replays them with realistic turn and move delays, writing feedback to Firebase after each step.

### 3. Run the Flutter App

```bash
cd app
flutter run
```

The app reads `map_config` from Firebase, renders `assets/map.svg`, and waits for the user to tap start and goal positions. After path planning completes, it animates the robot icon along the path in real time.

---

## Map Dimensions

No map dimensions are hardcoded anywhere in the system. All spatial parameters — resolution, width, height, origin — are derived at runtime from the JSON files in `Map_extraction/`:

- `inflated_grid.json` — used for A* path planning (obstacles inflated by robot radius)
- `costmap.json` — used for display/debug
- `map.svg` — rendered in the Flutter app (vector, scales to any screen DPI)
- `map.png` — raster fallback if SVG rendering fails

The backend reads these files via:

```python
MAP_DIR = Path(__file__).parent.parent / "Map_extraction"
grid, raw_meta = load_map(str(MAP_DIR / "inflated_grid.json"))
config = build_map_config(grid, raw_meta)
```

`build_map_config` derives all `MapConfig` fields from the numpy array shape and raw JSON metadata — no hardcoded values.

---

## Environment Variables

| Variable | Description | Example |
|---|---|---|
| `FIREBASE_CREDENTIALS_PATH` | Path to Firebase service account JSON | `/home/user/serviceAccountKey.json` |
| `FIREBASE_DATABASE_URL` | Firebase Realtime Database URL | `https://amr-system-nav-default-rtdb.firebaseio.com` |
