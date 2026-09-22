from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO
import yaml
import subprocess
import threading
import os
import glob
import json
import csv
import statistics
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('GEMSAPP_SECRET_KEY') or secrets.token_hex(32)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
STUDIES_DIR = os.path.join(BASE_DIR, 'Studies')
SOLVERS_DIR = os.path.join(BASE_DIR, 'Solver')

simulation_process = None
simulation_running = False

def get_available_simulators():
    """Scan SOLVERS_DIR for antares simulator installations (directories containing bin/antares-modeler)."""
    import re
    simulators = []
    try:
        entries = sorted(os.listdir(SOLVERS_DIR))
    except OSError:
        return simulators
    for name in entries:
        if not name.startswith('antares-'):
            continue
        modeler = os.path.join(SOLVERS_DIR, name, 'bin', 'antares-modeler')
        if not os.path.isfile(modeler):
            continue
        # Extract a human-readable version label from the directory name
        # e.g. "antares-9.3.7-Ubuntu-22.04" -> version "9.3.7", platform "Ubuntu 22.04"
        label = name[len('antares-'):]
        m = re.match(r'^([\d.]+)-(.+)$', label)
        version = m.group(1) if m else label
        platform = m.group(2).replace('-', ' ') if m else ''
        simulators.append({
            'id':       name,
            'version':  version,
            'platform': platform,
            'label':    f'{version} ({platform})' if platform else version,
            'modeler':  modeler,
        })
    return simulators


def _is_safe_component(name):
    """Reject empty, absolute, or traversal-containing path segments."""
    if not name or os.path.isabs(name):
        return False
    return all(part not in ('', '.', '..') for part in name.replace('\\', '/').split('/'))


def safe_join(base_dir, *parts):
    """Join base_dir with parts, returning None if the result would escape base_dir."""
    if not all(_is_safe_component(p) for p in parts):
        return None
    candidate = os.path.realpath(os.path.join(base_dir, *parts))
    base = os.path.realpath(base_dir)
    if candidate != base and not candidate.startswith(base + os.sep):
        return None
    return candidate


# antares-modeler accepts either extension for a data-series file (DataSeriesRepoImporter::
# hasRightExtension in the Antares_Simulator source checks for both), but always parses the
# content as TAB-delimited regardless of which one is used -- comma-delimited content throws,
# which is caught by a blanket handler that silently empties the *entire* data-series repo for
# the study, not just the one bad file. So GEMSAPP must read/write tab-delimited too.
DATA_SERIES_EXTENSIONS = ('.tsv', '.csv')


def find_data_series_path(data_dir, name):
    """Return the path to `name`'s data-series file, trying each accepted extension."""
    for ext in DATA_SERIES_EXTENSIONS:
        candidate = safe_join(data_dir, name + ext)
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def get_study_paths(study_id):
    study_dir = os.path.join(STUDIES_DIR, study_id)
    return {
        'dir':        study_dir,
        'lib_dir':    os.path.join(study_dir, "input", "model-libraries"),
        'system':     os.path.join(study_dir, "input", "system.yml"),
        'params':     os.path.join(study_dir, "parameters.yml"),
        'optim_config':os.path.join(study_dir, "input", "optim-config.yml"),
        'layout':     os.path.join(study_dir, "input", ".layout.json"),
        'data_series':os.path.join(study_dir, "input", "data-series"),
    }


def normalize_library(lib_data):
    """Rebuild the library dict with canonical key ordering so PyYAML outputs clean YAML."""
    if not lib_data or 'library' not in lib_data:
        return lib_data
    src = lib_data['library']

    def order(d, keys):
        """Return a new dict with the given keys first, then any remaining keys."""
        out = {}
        for k in keys:
            if k in d:
                out[k] = d[k]
        for k, v in d.items():
            if k not in out:
                out[k] = v
        return out

    def norm_list(items, first_keys):
        return [order(item, first_keys) for item in (items or [])]

    port_types = []
    for pt in src.get('port-types', []):
        npt = order(pt, ['id', 'description', 'fields', 'area-connection'])
        port_types.append(npt)

    models = []
    for m in src.get('models', []):
        nm = order(m, ['id', 'description', 'parameters', 'variables', 'ports',
                        'port-field-definitions', 'constraints', 'binding-constraints',
                        'objective-contributions', 'extra-outputs'])
        if 'parameters' in nm:
            nm['parameters'] = norm_list(nm['parameters'],
                                         ['id', 'time-dependent', 'scenario-dependent'])
        if 'variables' in nm:
            nm['variables'] = norm_list(nm['variables'],
                                        ['id', 'lower-bound', 'upper-bound', 'variable-type'])
        if 'ports' in nm:
            nm['ports'] = norm_list(nm['ports'], ['id', 'type'])
        if 'port-field-definitions' in nm:
            nm['port-field-definitions'] = norm_list(nm['port-field-definitions'],
                                                     ['port', 'field', 'definition'])
        for key in ('constraints', 'binding-constraints',
                    'objective-contributions', 'extra-outputs'):
            if key in nm:
                nm[key] = norm_list(nm[key], ['id', 'expression', 'lower-bound', 'upper-bound'])
        models.append(nm)

    lib = order(src, ['id', 'description', 'port-types', 'models'])
    lib['port-types'] = port_types
    lib['models'] = models
    return {'library': lib}


def load_all_libraries(lib_dir):
    """Return dict {lib_id: {file, data}} for all YAML files in lib_dir."""
    libraries = {}
    if not os.path.isdir(lib_dir):
        return libraries
    for fname in sorted(os.listdir(lib_dir)):
        if not (fname.endswith('.yml') or fname.endswith('.yaml')):
            continue
        try:
            with open(os.path.join(lib_dir, fname)) as f:
                data = yaml.safe_load(f)
            if data and 'library' in data:
                lib_id = data['library']['id']
                libraries[lib_id] = {'file': fname, 'data': data}
        except Exception:
            pass
    return libraries


def require_study(source='args'):
    """Extract and validate study_id from request. Returns (study_id, None) or (None, error_response)."""
    if source == 'args':
        study_id = request.args.get('study', '').strip()
    else:
        study_id = (request.json or {}).get('study', '').strip()
    if not study_id:
        return None, (jsonify({'error': 'study parameter is required'}), 400)
    if not _is_safe_component(study_id):
        return None, (jsonify({'error': 'Invalid study parameter'}), 400)
    return study_id, None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/studies')
def list_studies():
    studies = []
    os.makedirs(STUDIES_DIR, exist_ok=True)
    for name in sorted(os.listdir(STUDIES_DIR)):
        path = os.path.join(STUDIES_DIR, name)
        if os.path.isdir(path) and os.path.exists(os.path.join(path, 'parameters.yml')):
            studies.append({'id': name, 'name': name})
    return jsonify(studies)


@app.route('/api/studies/<study_id>', methods=['DELETE'])
def delete_study(study_id):
    import shutil
    study_dir = safe_join(STUDIES_DIR, study_id)
    # Safety: must resolve to a direct child of STUDIES_DIR and have parameters.yml
    if not study_dir or not os.path.isdir(study_dir) or not os.path.exists(os.path.join(study_dir, 'parameters.yml')):
        return jsonify({'error': 'Study not found'}), 404
    shutil.rmtree(study_dir)
    return jsonify({'status': 'ok'})


@app.route('/api/studies', methods=['POST'])
def create_study():
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Study name is required'}), 400
    # Basic filename safety
    import re
    if not re.match(r'^[\w\-. ]+$', name) or not _is_safe_component(name):
        return jsonify({'error': 'Name may only contain letters, digits, spaces, hyphens, underscores and dots'}), 400
    os.makedirs(STUDIES_DIR, exist_ok=True)
    study_dir = os.path.join(STUDIES_DIR, name)
    if os.path.exists(study_dir):
        return jsonify({'error': f'Study "{name}" already exists'}), 409

    # Create directory structure
    os.makedirs(os.path.join(study_dir, 'input', 'model-libraries'), exist_ok=True)
    os.makedirs(os.path.join(study_dir, 'input', 'data-series'),     exist_ok=True)
    os.makedirs(os.path.join(study_dir, 'output'),                    exist_ok=True)

    # parameters.yml
    params = {
        'first-time-step': int(data.get('first-time-step', 0)),
        'last-time-step':  int(data.get('last-time-step',  167)),
        'no-output':       False,
        'solver':          data.get('solver', 'coin'),
        'solver-logs':     False,
    }
    with open(os.path.join(study_dir, 'parameters.yml'), 'w') as f:
        yaml.dump(params, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # system.yml
    system = {'system': {'id': 'system', 'components': [], 'connections': []}}
    with open(os.path.join(study_dir, 'input', 'system.yml'), 'w') as f:
        yaml.dump(system, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    return jsonify({'status': 'ok', 'id': name})


@app.route('/api/models')
def get_models():
    study_id, err = require_study()
    if err: return err
    paths = get_study_paths(study_id)
    return jsonify({'libraries': load_all_libraries(paths['lib_dir'])})


@app.route('/api/libraries')
def list_libraries():
    study_id, err = require_study()
    if err: return err
    paths   = get_study_paths(study_id)
    lib_dir = paths['lib_dir']
    if not os.path.isdir(lib_dir):
        return jsonify([])
    files = sorted(f for f in os.listdir(lib_dir) if f.endswith('.yml') or f.endswith('.yaml'))
    return jsonify(files)


@app.route('/api/library')
def get_library():
    study_id, err = require_study()
    if err: return err
    filename = request.args.get('file')
    if not filename:
        return jsonify({'error': 'file required'}), 400
    paths = get_study_paths(study_id)
    path  = safe_join(paths['lib_dir'], filename)
    if not path or not os.path.isfile(path):
        return jsonify({'error': 'not found'}), 404
    with open(path) as f:
        data = yaml.safe_load(f)
    return jsonify({'file': filename, 'data': data})


@app.route('/api/library', methods=['POST'])
def save_library():
    study_id, err = require_study('json')
    if err: return err
    req      = request.json
    filename = req.get('file')
    lib_data = req.get('data')
    if not filename or not lib_data:
        return jsonify({'error': 'file and data required'}), 400
    paths = get_study_paths(study_id)
    path = safe_join(paths['lib_dir'], filename)
    if not path:
        return jsonify({'error': 'Invalid file parameter'}), 400
    os.makedirs(paths['lib_dir'], exist_ok=True)
    with open(path, 'w') as f:
        yaml.dump(normalize_library(lib_data), f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return jsonify({'status': 'ok'})


@app.route('/api/system')
def get_system():
    study_id, err = require_study()
    if err: return err
    paths = get_study_paths(study_id)

    with open(paths['system'], 'r') as f:
        system_data = yaml.safe_load(f)

    layout = {}
    if os.path.exists(paths['layout']):
        with open(paths['layout'], 'r') as f:
            layout = json.load(f)

    data_series = []
    if os.path.exists(paths['data_series']):
        data_series = sorted({
            os.path.splitext(fn)[0]
            for fn in os.listdir(paths['data_series'])
            if fn.endswith(DATA_SERIES_EXTENSIONS)
        })

    with open(paths['params'], 'r') as f:
        params = yaml.safe_load(f)

    return jsonify({
        'system': system_data,
        'layout': layout,
        'data_series': data_series,
        'params': params,
    })


@app.route('/api/system', methods=['POST'])
def save_system():
    study_id, err = require_study('json')
    if err: return err
    data  = request.json
    paths = get_study_paths(study_id)

    with open(paths['system'], 'w') as f:
        yaml.dump(data['system'], f, default_flow_style=False,
                  sort_keys=False, allow_unicode=True)

    if 'layout' in data:
        with open(paths['layout'], 'w') as f:
            json.dump(data['layout'], f, indent=2)

    if 'params' in data:
        with open(paths['params'], 'w') as f:
            yaml.dump(data['params'], f, default_flow_style=False,
                      sort_keys=False, allow_unicode=True)

    return jsonify({'status': 'ok'})


@app.route('/api/simulators')
def list_simulators():
    return jsonify(get_available_simulators())


# antares-modeler solvers (from OrtoolsUtils::mpSolverMap in Antares_Simulator source).
# "sirius" and "pdlp" are LP-only and will fail antares-modeler at run time on a MIP study
# (e.g. any committable generator/link) -- left selectable since GEMSAPP can't tell in
# advance whether a study needs MIP.
KNOWN_SOLVERS = ['highs', 'coin', 'xpress', 'scip', 'glpk', 'gurobi', 'sirius', 'pdlp']


@app.route('/api/parameters')
def get_parameters():
    study_id, err = require_study()
    if err: return err
    paths = get_study_paths(study_id)
    if not os.path.isfile(paths['params']):
        return jsonify({'error': 'parameters.yml not found'}), 404
    with open(paths['params']) as f:
        params = yaml.safe_load(f) or {}
    return jsonify(params)


@app.route('/api/parameters', methods=['POST'])
def save_parameters():
    study_id, err = require_study('json')
    if err: return err
    req   = request.json or {}
    paths = get_study_paths(study_id)

    try:
        first_ts = int(req.get('first-time-step', 0))
        last_ts  = int(req.get('last-time-step', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'first-time-step and last-time-step must be integers'}), 400
    if first_ts < 0 or last_ts < first_ts:
        return jsonify({'error': 'last-time-step must be >= first-time-step >= 0'}), 400

    solver = str(req.get('solver', 'coin')).strip().lower()
    if solver not in KNOWN_SOLVERS:
        return jsonify({'error': f'Unknown solver "{solver}". Expected one of: {", ".join(KNOWN_SOLVERS)}'}), 400

    params = {
        'first-time-step':   first_ts,
        'last-time-step':    last_ts,
        'no-output':         bool(req.get('no-output', False)),
        'solver':            solver,
        'solver-logs':       bool(req.get('solver-logs', False)),
        'solver-parameters': str(req.get('solver-parameters', '')),
        'export-mps':        bool(req.get('export-mps', False)),
    }
    os.makedirs(paths['dir'], exist_ok=True)
    with open(paths['params'], 'w') as f:
        yaml.dump(params, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return jsonify({'status': 'ok'})


# optim-config.yml controls Benders-decomposition model splitting for investment/Xpansion
# studies (resolution-mode, per-model variable/objective-contribution locations, and
# out-of-bounds-processing). Its schema is a nested, open-ended structure, so it's edited
# as raw YAML here rather than through a bespoke form -- GEMSAPP just guarantees it parses
# as a YAML mapping before writing it.
@app.route('/api/optim-config')
def get_optim_config():
    study_id, err = require_study()
    if err: return err
    paths = get_study_paths(study_id)
    if not os.path.isfile(paths['optim_config']):
        return jsonify({'exists': False, 'content': ''})
    with open(paths['optim_config']) as f:
        content = f.read()
    return jsonify({'exists': True, 'content': content})


@app.route('/api/optim-config', methods=['POST'])
def save_optim_config():
    study_id, err = require_study('json')
    if err: return err
    req     = request.json or {}
    content = req.get('content', '')
    if not isinstance(content, str) or not content.strip():
        return jsonify({'error': 'content is required'}), 400
    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError as e:
        return jsonify({'error': f'Invalid YAML: {e}'}), 400
    if not isinstance(parsed, dict):
        return jsonify({'error': 'optim-config.yml must be a YAML mapping at the top level'}), 400

    paths = get_study_paths(study_id)
    os.makedirs(os.path.dirname(paths['optim_config']), exist_ok=True)
    with open(paths['optim_config'], 'w') as f:
        f.write(content)
    return jsonify({'status': 'ok'})


@app.route('/api/optim-config', methods=['DELETE'])
def delete_optim_config():
    study_id, err = require_study('json')
    if err: return err
    paths = get_study_paths(study_id)
    if os.path.isfile(paths['optim_config']):
        os.remove(paths['optim_config'])
    return jsonify({'status': 'ok'})


@app.route('/api/simulate', methods=['POST'])
def run_simulation():
    if simulation_running:
        return jsonify({'error': 'Simulation already running'}), 400

    study_id, err = require_study('json')
    if err: return err
    paths = get_study_paths(study_id)

    # Resolve which modeler to use
    simulator_id = (request.json or {}).get('simulator', '').strip()
    if simulator_id:
        modeler_exe = os.path.join(SOLVERS_DIR, simulator_id, 'bin', 'antares-modeler')
    else:
        sims = get_available_simulators()
        if not sims:
            return jsonify({'error': 'No Antares Simulator installation found in the GEMSAPP directory'}), 404
        modeler_exe = sims[-1]['modeler']  # default: latest (last alphabetically)

    if not os.path.isfile(modeler_exe):
        return jsonify({'error': f'Modeler not found: {modeler_exe}'}), 404

    def run():
        global simulation_process, simulation_running
        simulation_running = True
        socketio.emit('sim_start', {'study': study_id})
        try:
            cmd = [modeler_exe, paths['dir']]
            simulation_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=paths['dir'],
            )
            for line in iter(simulation_process.stdout.readline, ''):
                if not simulation_running:
                    break
                socketio.emit('sim_output', {'line': line.rstrip()})
            simulation_process.stdout.close()
            simulation_process.wait()
            code = simulation_process.returncode
            socketio.emit('sim_end', {
                'exit_code': code,
                'success': code == 0,
                'message': 'Simulation completed successfully' if code == 0 else f'Simulation exited with code {code}',
            })
        except Exception as e:
            socketio.emit('sim_error', {'error': str(e)})
        finally:
            simulation_running = False
            simulation_process = None

    threading.Thread(target=run, daemon=True).start()
    return jsonify({'status': 'started'})


@app.route('/api/simulate/stop', methods=['POST'])
def stop_simulation():
    global simulation_running
    if simulation_process:
        simulation_process.terminate()
        simulation_running = False
        return jsonify({'status': 'stopped'})
    return jsonify({'error': 'No simulation running'}), 400


@app.route('/api/simulate/status')
def sim_status():
    return jsonify({'running': simulation_running})


# ── RESULTS ──────────────────────────────────────────────────────────────────

@app.route('/api/results')
def list_results():
    study_id, err = require_study()
    if err: return err
    output_dir = os.path.join(STUDIES_DIR, study_id, 'output')
    if not os.path.isdir(output_dir):
        return jsonify([])
    # antares-modeler writes each run into its own output/<timestamp>/ subfolder; older/manual
    # results may sit flat in output/ directly. Look in both, newest run first.
    matches = glob.glob(os.path.join(output_dir, '**', 'simulation_table*.csv'), recursive=True)
    files = sorted(
        (os.path.relpath(m, output_dir).replace(os.sep, '/') for m in matches),
        key=lambda f: os.path.getmtime(os.path.join(output_dir, f)),
        reverse=True,
    )
    return jsonify(files)


@app.route('/api/results/debug-files')
def results_debug_files():
    """Sibling .mps / structure.txt files antares-modeler writes next to a run's
    simulation_table.csv when parameters.yml sets export-mps: true."""
    study_id, err = require_study()
    if err: return err
    filename = request.args.get('file')
    if not filename:
        return jsonify({'error': 'file required'}), 400
    output_dir = os.path.join(STUDIES_DIR, study_id, 'output')
    run_dir = safe_join(output_dir, os.path.dirname(filename)) if os.path.dirname(filename) else output_dir
    if not run_dir or not os.path.isdir(run_dir):
        return jsonify([])
    debug_files = sorted(
        f for f in os.listdir(run_dir) if f.endswith('.mps') or f == 'structure.txt'
    )
    prefix = os.path.dirname(filename)
    paths = [f'{prefix}/{f}' if prefix else f for f in debug_files]
    return jsonify(paths)


@app.route('/api/results/meta')
def results_meta():
    study_id, err = require_study()
    if err: return err
    filename = request.args.get('file')
    if not filename:
        return jsonify({'error': 'file required'}), 400
    path = safe_join(os.path.join(STUDIES_DIR, study_id, 'output'), filename)
    if not path or not os.path.isfile(path):
        return jsonify({'error': 'file not found'}), 404

    components = {}
    scenarios  = set()
    objective  = None
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            comp = row['component']
            out  = row['output']
            if comp == 'None' and out == 'OBJECTIVE_VALUE':
                objective = float(row['value'])
                continue
            if row['scenario_index'] != 'None':
                scenarios.add(row['scenario_index'])
            components.setdefault(comp, set()).add(out)

    return jsonify({
        'components': {k: sorted(v) for k, v in sorted(components.items())},
        'scenarios':  sorted(scenarios),
        'objective':  objective,
    })


@app.route('/api/results/series')
def results_series():
    study_id, err = require_study()
    if err: return err
    filename  = request.args.get('file')
    component = request.args.get('component')
    output    = request.args.get('output')
    scenario  = request.args.get('scenario', '0')

    if not all([filename, component, output]):
        return jsonify({'error': 'file, component and output required'}), 400
    path = safe_join(os.path.join(STUDIES_DIR, study_id, 'output'), filename)
    if not path or not os.path.isfile(path):
        return jsonify({'error': 'file not found'}), 404

    times, values, scalar_val = [], [], None
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            if row['component'] != component or row['output'] != output:
                continue
            t, v = row['absolute_time_index'], row['value']
            # time-independent rows have scenario_index=None in the CSV — include them regardless of scenario filter
            if t != 'None' and row['scenario_index'] != scenario:
                continue
            if v == 'None':
                continue
            if t == 'None':
                scalar_val = float(v)
            else:
                times.append(int(t))
                values.append(float(v))

    if scalar_val is not None and not times:
        return jsonify({'scalar': True, 'value': scalar_val, 'times': [], 'values': [], 'stats': {'scalar': scalar_val}})

    paired = sorted(zip(times, values))
    times  = [p[0] for p in paired]
    values = [p[1] for p in paired]
    stats  = {'min': min(values), 'max': max(values), 'mean': statistics.mean(values), 'sum': sum(values)} if values else {}

    return jsonify({'scalar': False, 'times': times, 'values': values, 'stats': stats})


@app.route('/api/timeseries/list')
def list_timeseries():
    study_id, err = require_study()
    if err: return err
    paths = get_study_paths(study_id)
    if not os.path.isdir(paths['data_series']):
        return jsonify([])
    files = sorted({
        os.path.splitext(f)[0] for f in os.listdir(paths['data_series']) if f.endswith(DATA_SERIES_EXTENSIONS)
    })
    return jsonify(files)


@app.route('/api/timeseries')
def get_timeseries():
    study_id, err = require_study()
    if err: return err
    filename = request.args.get('file')
    if not filename:
        return jsonify({'error': 'file required'}), 400
    paths = get_study_paths(study_id)
    path  = find_data_series_path(paths['data_series'], filename)
    if not path:
        return jsonify({'error': 'file not found'}), 404
    rows = []
    with open(path, newline='') as f:
        for row in csv.reader(f, delimiter='\t'):
            rows.append(row)
    return jsonify({'file': filename, 'rows': rows})


@app.route('/api/timeseries', methods=['DELETE'])
def delete_timeseries():
    study_id, err = require_study('json')
    if err: return err
    data     = request.json
    filename = data.get('file')
    if not filename:
        return jsonify({'error': 'file required'}), 400
    paths = get_study_paths(study_id)
    path  = find_data_series_path(paths['data_series'], filename)
    if not path:
        return jsonify({'error': 'not found'}), 404
    os.remove(path)
    return jsonify({'status': 'ok'})


@app.route('/api/library', methods=['DELETE'])
def delete_library():
    study_id, err = require_study('json')
    if err: return err
    data     = request.json
    filename = data.get('file')
    if not filename:
        return jsonify({'error': 'file required'}), 400
    paths = get_study_paths(study_id)
    path  = safe_join(paths['lib_dir'], filename)
    if not path or not os.path.isfile(path):
        return jsonify({'error': 'not found'}), 404
    os.remove(path)
    return jsonify({'status': 'ok'})


@app.route('/api/timeseries', methods=['POST'])
def save_timeseries():
    study_id, err = require_study('json')
    if err: return err
    data     = request.json
    filename = data.get('file')
    rows     = data.get('rows', [])
    if not filename:
        return jsonify({'error': 'file required'}), 400
    paths = get_study_paths(study_id)
    # Overwrite the existing file's extension if there is one; new series default to .tsv,
    # since antares-modeler always reads data-series content as tab-delimited regardless of
    # which of .csv/.tsv the file is named -- comma-delimited content breaks the whole study
    # (see DATA_SERIES_EXTENSIONS comment above).
    path = find_data_series_path(paths['data_series'], filename) \
        or safe_join(paths['data_series'], filename + '.tsv')
    if not path:
        return jsonify({'error': 'Invalid file parameter'}), 400
    os.makedirs(paths['data_series'], exist_ok=True)
    with open(path, 'w', newline='') as f:
        csv.writer(f, delimiter='\t').writerows(rows)
    return jsonify({'status': 'ok'})


@app.route('/api/results/download')
def download_result():
    study_id, err = require_study()
    if err: return err
    filename = request.args.get('file')
    if not filename:
        return jsonify({'error': 'file required'}), 400
    output_dir = os.path.join(STUDIES_DIR, study_id, 'output')
    return send_from_directory(output_dir, filename, as_attachment=True)


if __name__ == '__main__':
    print("GEMS Power System Editor")
    sims = get_available_simulators()
    if sims:
        print(f"Found {len(sims)} Antares Simulator(s):")
        for s in sims:
            print(f"  {s['label']:40s}  {s['modeler']}")
    else:
        print("WARNING: No Antares Simulator found in GEMSAPP directory")
    print("Open http://localhost:5000")
    socketio.run(app, debug=False, host='0.0.0.0', port=5000, use_reloader=False, allow_unsafe_werkzeug=True)
