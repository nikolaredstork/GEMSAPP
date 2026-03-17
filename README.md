# GEMSAPP

A web application for editing and simulating power systems, built on a Flask backend and vis-network frontend. Uses Antares Modeler as the simulation engine.

## Requirements

- Python 3.9+
- Antares Modeler binary (not included in the repository)

## Installation

### 1. Clone the repository

```bash
git clone git@github.com:nikolaredstork/GEMSAPP.git
cd GEMSAPP
```

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install flask flask-socketio pyyaml
```

### 3. Set up Antares Modeler

Download and extract the Antares binary package into the project root so that the path is:

```
GEMSAPP/antares-9.3.2-Ubuntu-22.04/bin/antares-modeler
```

### 4. Prepare a study

At least one study must exist in the project root. Study structure:

```
MyStudy/
├── parameters.yml
├── input/
│   ├── system.yml
│   ├── model-libraries/
│   └── data-series/
└── output/
```

New studies can also be created directly through the web interface.

## Running

```bash
source venv/bin/activate
python app.py
```

Open your browser at [http://localhost:5000](http://localhost:5000).

## Usage

- **Studies** — create, load, or delete studies from the dropdown menu
- **Editor** — add components and connections to the system visually (drag & drop)
- **Model libraries** — import and edit YAML model library files
- **Time series** — upload CSV files with input data
- **Simulation** — run Antares Modeler and monitor the log in real time
- **Results** — browse and download output CSV files
