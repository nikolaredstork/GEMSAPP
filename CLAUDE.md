# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
python3 -m venv venv
source venv/bin/activate
pip install flask flask-socketio pyyaml
python app.py          # opens at http://localhost:5000
```

Kill a running instance:

```bash
kill $(lsof -t -i :5000)
```

## Directory Layout

```text
app.py                 # Flask backend — all API routes and simulation logic
templates/index.html   # Single-file SPA — all HTML, CSS, and JS inline
Studies/               # User studies (gitignored — not in repo)
Solver/                # Antares Simulator binaries (gitignored — not in repo)
versions/              # antares-simulator.txt — pinned version tracked by Renovate
docs/                  # Developer notes (pypsa_to_gems_parameters.md)
```

## Architecture

**Backend (`app.py`)** is a flat Flask + Flask-SocketIO server (~590 lines, no database). Key globals:

- `STUDIES_DIR = BASE_DIR/Studies` — where studies live
- `SOLVERS_DIR = BASE_DIR/Solver` — where Antares binaries live
- `simulation_process / simulation_running` — single global simulation slot (one study at a time)

`get_available_simulators()` scans `Solver/` for any `antares-*/bin/antares-modeler`. To add a new solver version, drop its extracted directory into `Solver/` — it appears in the UI automatically.

**Frontend (`templates/index.html`)** is a single-file SPA (~3100 lines, vanilla JS, no build step). Libraries loaded from CDN:

- **vis-network** — drag-and-drop system topology editor
- **Socket.IO** — streams simulation log lines in real time
- **Chart.js + chartjs-plugin-zoom** — result time-series plots

**Simulation flow**: clicking ▶ Run opens a simulator version picker → POSTs `{study, simulator}` to `/api/simulate` → server spawns `antares-modeler <study_dir>` in a daemon thread → stdout streamed line-by-line via `socketio.emit('sim_output', ...)` → `sim_end` event signals completion.

## Study Format

```text
Studies/MyStudy/
├── parameters.yml              # Solver config: first/last-time-step, solver, solver-parameters
├── input/
│   ├── system.yml              # Component list + connections (references library model IDs)
│   ├── .layout.json            # vis-network node positions (written by UI)
│   ├── model-libraries/*.yml   # GEMS model library files
│   └── data-series/*.csv       # Time-series inputs (one value per row, one column per scenario)
└── output/
    └── simulation_table--YYYYMMDD-HHMM.csv   # Results written by antares-modeler
```

**`system.yml`** references models as `<library_id>.<model_id>` (e.g. `pypsa_models.bus`). Parameter `value` can be a scalar or the stem of a `data-series/` CSV filename when `time-dependent: true`.

**Result CSV columns:** `component, output, scenario_index, absolute_time_index, value`. The objective value appears as a special row with `component=None, output=OBJECTIVE_VALUE`.

## Model Library YAML

Libraries follow the GEMS schema. Key sections per model: `parameters`, `variables`, `ports`, `port-field-definitions`, `constraints`, `binding-constraints`, `objective-contributions`, `extra-outputs`.

**Critical rule**: `sum_connections(port.field)` (PortFieldSumNode) is only valid in `binding-constraints` and `extra-outputs`, **not** in `constraints`. Antares ≥ 9.3.7 enforces this strictly; earlier versions silently accepted it.

`normalize_library()` in `app.py` enforces canonical YAML key ordering when saving library files through the UI — do not reorder keys manually in ways that deviate from the schema.

## CI

- **`check-antares-update.yml`** — runs daily, compares `versions/antares-simulator.txt` against latest GitHub release, opens an issue if a new version is available.
- **`validate-antares.yml`** — fires on PRs that touch `versions/antares-simulator.txt` (Renovate bot only).
- No automated tests exist in this repository.

## Antares Version Tracking

`versions/antares-simulator.txt` contains `ANTARES_SIMULATOR_VERSION=X.Y.Z`. Update this file when adopting a new binary; Renovate monitors it.
