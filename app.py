from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO
import yaml
import subprocess
import threading
import os
import json
import csv
import statistics

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gems-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELER_EXE = os.path.join(BASE_DIR, "antares-9.3.2-Ubuntu-22.04", "bin", "antares-modeler")

simulation_process = None
simulation_running = False


def get_study_paths(study_id):
    study_dir = os.path.join(BASE_DIR, study_id)
    return {
        'dir':        study_dir,
        'lib_dir':    os.path.join(study_dir, "input", "model-libraries"),
        'system':     os.path.join(study_dir, "input", "system.yml"),
        'params':     os.path.join(study_dir, "parameters.yml"),
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
    return study_id, None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/studies')
def list_studies():
    studies = []
    for name in sorted(os.listdir(BASE_DIR)):
        path = os.path.join(BASE_DIR, name)
        if os.path.isdir(path) and os.path.exists(os.path.join(path, 'parameters.yml')):
            studies.append({'id': name, 'name': name})
    return jsonify(studies)


@app.route('/api/studies/<study_id>', methods=['DELETE'])
def delete_study(study_id):
    import shutil
    study_dir = os.path.join(BASE_DIR, study_id)
    # Safety: must be a direct child of BASE_DIR and have parameters.yml
    if not os.path.isdir(study_dir) or not os.path.exists(os.path.join(study_dir, 'parameters.yml')):
        return jsonify({'error': 'Study not found'}), 404
    # Prevent path traversal
    if os.path.realpath(study_dir) != os.path.realpath(os.path.join(BASE_DIR, study_id)):
        return jsonify({'error': 'Invalid study path'}), 400
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
    if not re.match(r'^[\w\-. ]+$', name):
        return jsonify({'error': 'Name may only contain letters, digits, spaces, hyphens, underscores and dots'}), 400
    study_dir = os.path.join(BASE_DIR, name)
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
    path  = os.path.join(paths['lib_dir'], filename)
    if not os.path.isfile(path):
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
    os.makedirs(paths['lib_dir'], exist_ok=True)
    path = os.path.join(paths['lib_dir'], filename)
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
        data_series = sorted([
            os.path.splitext(fn)[0]
            for fn in os.listdir(paths['data_series'])
            if fn.endswith('.csv')
        ])

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


@app.route('/api/simulate', methods=['POST'])
def run_simulation():
    global simulation_process, simulation_running

    if simulation_running:
        return jsonify({'error': 'Simulation already running'}), 400

    study_id, err = require_study('json')
    if err: return err
    paths = get_study_paths(study_id)

    if not os.path.exists(MODELER_EXE):
        return jsonify({'error': f'Modeler not found: {MODELER_EXE}'}), 404

    def run():
        global simulation_process, simulation_running
        simulation_running = True
        socketio.emit('sim_start', {'study': study_id})
        try:
            cmd = [MODELER_EXE, paths['dir']]
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
    global simulation_process, simulation_running
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
    output_dir = os.path.join(BASE_DIR, study_id, 'output')
    if not os.path.isdir(output_dir):
        return jsonify([])
    files = sorted(
        [f for f in os.listdir(output_dir) if f.startswith('simulation_table') and f.endswith('.csv')],
        reverse=True
    )
    return jsonify(files)


@app.route('/api/results/meta')
def results_meta():
    study_id, err = require_study()
    if err: return err
    filename = request.args.get('file')
    if not filename:
        return jsonify({'error': 'file required'}), 400
    path = os.path.join(BASE_DIR, study_id, 'output', filename)
    if not os.path.isfile(path):
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
    path = os.path.join(BASE_DIR, study_id, 'output', filename)
    if not os.path.isfile(path):
        return jsonify({'error': 'file not found'}), 404

    times, values = [], []
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            if row['component'] != component or row['output'] != output or row['scenario_index'] != scenario:
                continue
            t, v = row['absolute_time_index'], row['value']
            if t == 'None' or v == 'None':
                continue
            times.append(int(t))
            values.append(float(v))

    paired = sorted(zip(times, values))
    times  = [p[0] for p in paired]
    values = [p[1] for p in paired]
    stats  = {'min': min(values), 'max': max(values), 'mean': statistics.mean(values), 'sum': sum(values)} if values else {}

    return jsonify({'times': times, 'values': values, 'stats': stats})


@app.route('/api/timeseries/list')
def list_timeseries():
    study_id, err = require_study()
    if err: return err
    paths = get_study_paths(study_id)
    if not os.path.isdir(paths['data_series']):
        return jsonify([])
    files = sorted([os.path.splitext(f)[0] for f in os.listdir(paths['data_series']) if f.endswith('.csv')])
    return jsonify(files)


@app.route('/api/timeseries')
def get_timeseries():
    study_id, err = require_study()
    if err: return err
    filename = request.args.get('file')
    if not filename:
        return jsonify({'error': 'file required'}), 400
    paths = get_study_paths(study_id)
    path  = os.path.join(paths['data_series'], filename + '.csv')
    if not os.path.isfile(path):
        return jsonify({'error': 'file not found'}), 404
    rows = []
    with open(path, newline='') as f:
        for row in csv.reader(f):
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
    path  = os.path.join(paths['data_series'], filename + '.csv')
    if not os.path.isfile(path):
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
    path  = os.path.join(paths['lib_dir'], filename)
    if not os.path.isfile(path):
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
    path  = os.path.join(paths['data_series'], filename + '.csv')
    with open(path, 'w', newline='') as f:
        csv.writer(f).writerows(rows)
    return jsonify({'status': 'ok'})


@app.route('/api/results/download')
def download_result():
    study_id, err = require_study()
    if err: return err
    filename = request.args.get('file')
    if not filename:
        return jsonify({'error': 'file required'}), 400
    output_dir = os.path.join(BASE_DIR, study_id, 'output')
    return send_from_directory(output_dir, filename, as_attachment=True)


if __name__ == '__main__':
    print(f"GEMS Power System Editor")
    print(f"Modeler: {MODELER_EXE}")
    print(f"Open http://localhost:5000")
    socketio.run(app, debug=False, host='0.0.0.0', port=5000, use_reloader=False, allow_unsafe_werkzeug=True)
