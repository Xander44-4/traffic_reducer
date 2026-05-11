from flask import Flask, render_template, request, jsonify, Response
import pickle
import joblib
import numpy as np
import random
import os
from video_processor import TrafficCamera

app = Flask(__name__)

MODEL_PATH = r"C:\Users\Xande\important\The Predictors\Haklaton\The Predictors-traffic_reducer\traffic_reducer_dataset\modelo_entrenado\modelo_semaforo_ia.pkl"

LOCAL_VIDEO_PATH = os.path.join(os.path.dirname(__file__), "static", "traffic_dron_view.mp4")

def load_model():
    try:
        with open(MODEL_PATH, 'rb') as f:
            return pickle.load(f)
    except Exception:
        try:
            return joblib.load(MODEL_PATH)
        except Exception as e:
            print(f"[App] No se pudo cargar el modelo: {e}")
            return None

model = load_model()

YOUTUBE_URL = "https://www.youtube.com/live/1H0iTzv2jiQ"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_yolov8m_local = os.path.join(PROJECT_ROOT, "yolov8m.pt")
_yolov8s_local = os.path.join(PROJECT_ROOT, "yolov8s.pt")
if os.path.exists(_yolov8m_local):
    YOLO_MODEL_PATH = _yolov8m_local
elif os.path.exists(_yolov8s_local):
    YOLO_MODEL_PATH = _yolov8s_local
else:
    YOLO_MODEL_PATH = "yolov8m.pt"

LOCAL_VIDEO_EXISTS = bool(LOCAL_VIDEO_PATH and os.path.exists(LOCAL_VIDEO_PATH))
DEFAULT_MODE = 'idle'
LOCAL_VIDEO_SPEED = 0.5

print(f"[App] Modelo YOLO: {YOLO_MODEL_PATH}")
print(f"[App] Video local: {LOCAL_VIDEO_PATH} ({'OK' if LOCAL_VIDEO_EXISTS else 'NO ENCONTRADO'})")
print(f"[App] Modo por defecto: {DEFAULT_MODE}")

camera = TrafficCamera(
    YOUTUBE_URL,
    model_path=YOLO_MODEL_PATH,
    local_video_path=LOCAL_VIDEO_PATH if LOCAL_VIDEO_EXISTS else None,
    default_mode=DEFAULT_MODE,
    local_speed=LOCAL_VIDEO_SPEED,
)
camera.start()

@app.route('/')
def home():
    return render_template('index.html')

def generate_frames():
    while True:
        frame_bytes = camera.get_frame()
        if frame_bytes:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/set_source', methods=['POST'])
def set_source():
    try:
        data = request.json
        mode = data.get('mode', 'youtube')
        if mode not in ('youtube', 'local'):
            return jsonify({'error': 'Modo inválido'}), 400
        if mode == 'local' and not LOCAL_VIDEO_EXISTS:
            return jsonify({'error': 'Video local no encontrado en disco'}), 400
        camera.set_mode(mode)
        return jsonify({'mode': camera.mode})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/set_speed', methods=['POST'])
def set_speed():
    try:
        data = request.json
        speed = float(data.get('speed', 1.0))
        applied = camera.set_local_speed(speed)
        return jsonify({'speed': applied})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/source_status')
def source_status():
    return jsonify({
        'mode': camera.mode,
        'has_local': LOCAL_VIDEO_EXISTS
    })

@app.route('/stats')
def stats():
    s = camera.get_counts()
    counts = [int(s.get('norte', 0)), int(s.get('sur', 0)),
              int(s.get('este', 0)),  int(s.get('oeste', 0))]
    names = ['NORTE', 'SUR', 'ESTE', 'OESTE']
    priority_idx = int(np.argmax(counts)) if sum(counts) > 0 else -1
    priority = names[priority_idx] if priority_idx >= 0 else '--'
    return jsonify({
        'norte': counts[0], 'sur': counts[1], 'este': counts[2], 'oeste': counts[3],
        'pedestrians': int(s.get('pedestrians', 0)),
        'emergency':   bool(s.get('emergency', False)),
        'phase': s.get('phase', 'INIT'),
        'priority': priority,
        'priority_idx': priority_idx,
        'mode': camera.mode,
    })

@app.route('/predict', methods=['POST'])
def predict():
    if not model:
        return jsonify({'error': 'Modelo no disponible'}), 500

    try:
        data = request.json
        use_live = data.get('live_mode', False)

        if use_live:
            counts = camera.get_counts()
            norte = float(counts['norte'])
            sur   = float(counts['sur'])
            este  = float(counts['este'])
            oeste = float(counts['oeste'])
        else:
            norte = float(data.get('norte', 0))
            sur   = float(data.get('sur',   0))
            este  = float(data.get('este',  0))
            oeste = float(data.get('oeste', 0))

        traffic_values = [norte, sur, este, oeste]
        result = int(np.argmax(traffic_values)) if sum(traffic_values) > 0 else 0

        if use_live:
            camera.set_phase(result)

        return jsonify({
            'prediction': result,
            'traffic_data': {
                'norte': norte, 'sur': sur, 'este': este, 'oeste': oeste
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/simulate', methods=['GET'])
def simulate():
    return jsonify({
        'norte': random.randint(0, 80),
        'sur':   random.randint(0, 80),
        'este':  random.randint(0, 80),
        'oeste': random.randint(0, 80)
    })

if __name__ == '__main__':
    print("Iniciando Traffic Reducer Server...")
    print("http://127.0.0.1:5000")
    app.run(debug=True, port=5000, use_reloader=False)
