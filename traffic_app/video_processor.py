import os
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = (
    'loglevel;quiet|rtsp_transport;tcp|http_persistent;0|'
    'reconnect;1|reconnect_streamed;1|reconnect_delay_max;5|'
    'fflags;nobuffer|flags;low_delay|probesize;32|analyzeduration;0|'
    'timeout;60000000|rw_timeout;60000000|'
    'user_agent;Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
)
os.environ['OPENCV_FFMPEG_OPEN_TIMEOUT'] = '60000'
os.environ['OPENCV_FFMPEG_READ_TIMEOUT'] = '60000'
os.environ['OPENCV_LOG_LEVEL'] = 'OFF'

import cv2
import shutil
import yt_dlp
import imageio_ffmpeg
from ultralytics import YOLO
import threading
import time
import subprocess
import numpy as np
from concurrent.futures import ThreadPoolExecutor

FFMPEG_BIN = imageio_ffmpeg.get_ffmpeg_exe()
PHASE_LABELS = {0: "NORTE", 1: "SUR", 2: "ESTE", 3: "OESTE"}

def _detect_node():
    node = shutil.which('node')
    if node:
        return node
    for p in (r'C:\Program Files\nodejs\node.exe',
              r'C:\Program Files (x86)\nodejs\node.exe'):
            if os.path.exists(p):
                return p
    return None

NODE_PATH = _detect_node()
JS_RUNTIMES = {'node': {'path': NODE_PATH}} if NODE_PATH else {}

YT_WIDTH, YT_HEIGHT = 854, 480
YT_FRAME_BYTES = YT_WIDTH * YT_HEIGHT * 3
YT_TARGET_FPS = 25


class TrafficCamera:
    def __init__(self, youtube_url, model_path='yolov8m.pt', local_video_path=None, default_mode='idle',
                 conf=0.25, iou=0.5, max_det=300, local_speed=1.0):
        self.youtube_url = youtube_url
        self.local_video_path = local_video_path
        self.model = YOLO(model_path)
        self.conf = conf
        self.iou = iou
        self.max_det = max_det
        self.local_speed = max(0.05, float(local_speed))

        self.cap = None
        self.yt_proc = None
        self.lock = threading.Lock()
        self.mode = default_mode if default_mode in ('idle', 'youtube', 'local') else 'idle'
        self.stream_error = None
        self._yt_cooldown_until = 0
        self._yt_consecutive_failures = 0

        self.traffic_state = {
            'norte': 0, 'sur': 0, 'este': 0, 'oeste': 0,
            'pedestrians': 0,
            'emergency': False,
            'phase': 'INIT',
            'frame': self._placeholder_frame("Selecciona una fuente para comenzar")
        }

        self.zones = {
            'norte': np.array([[0.00, 0.00], [0.43, 0.05], [0.43, 0.58], [0.27, 0.65]]),
            'este':  np.array([[0.47, 0.07], [1.00, 0.17], [1.00, 0.40], [0.57, 0.55]]),
            'sur':   np.array([[0.53, 0.55], [0.96, 0.42], [0.99, 0.94], [0.63, 1.00]]),
            'oeste': np.array([[0.00, 0.73], [0.55, 0.70], [0.43, 1.00], [0.00, 1.00]]),
        }

        self.zone_colors = {
            'norte': (255, 180, 60),
            'sur':   (60, 200, 255),
            'este':  (90, 230, 130),
            'oeste': (200, 120, 255),
        }

        self.current_phase = "INIT"
        self.running = False
        self.thread = threading.Thread(target=self._process_stream, daemon=True)

        self.executor = ThreadPoolExecutor(max_workers=1)
        self.pending_yolo = None
        self.last_yolo_data = None
        self.yolo_cache = {}

    def _placeholder_frame(self, message="Sin transmisión disponible"):
        frame = np.zeros((480, 854, 3), dtype=np.uint8)
        frame[:] = (28, 28, 30)
        cv2.putText(frame, message, (180, 230),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (160, 160, 165), 2)
        cv2.putText(frame, "Traffic Reducer", (320, 290),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (80, 80, 85), 1)
        _, buf = cv2.imencode('.jpg', frame)
        return buf.tobytes()

    def set_phase(self, phase_id):
        label = PHASE_LABELS.get(phase_id, f"PHASE-{phase_id}")
        self.current_phase = label
        with self.lock:
            self.traffic_state['phase'] = label

    def set_local_speed(self, speed):
        speed = max(0.05, float(speed))
        with self.lock:
            self.local_speed = speed
            if hasattr(self, '_local_fps'):
                self._local_frame_interval = (1.0 / self._local_fps) / self.local_speed
                self._local_next_frame_time = time.perf_counter()
        return self.local_speed

    def set_mode(self, mode):
        if mode not in ('idle', 'youtube', 'local'):
            return
        with self.lock:
            if self.mode == mode:
                return
            self.mode = mode
            self._close_sources()
            labels = {
                'idle': "Selecciona una fuente para comenzar",
                'youtube': "Conectando al stream en vivo...",
                'local': "Cargando video local...",
            }
            self.traffic_state['frame'] = self._placeholder_frame(labels[mode])
            if mode == 'youtube':
                self._yt_cooldown_until = 0
                self._yt_consecutive_failures = 0
            self.last_yolo_data = None
            self.yolo_cache = {}

    def _close_sources(self):
        if self.cap:
            try: self.cap.release()
            except Exception: pass
            self.cap = None
        if self.yt_proc:
            try:
                self.yt_proc.kill()
                self.yt_proc.wait(timeout=2)
            except Exception:
                pass
            self.yt_proc = None

    def start(self):
        self.running = True
        self.thread.start()

    def _get_stream_url(self):
        if time.time() < self._yt_cooldown_until:
            return None

        clients_to_try = [['android'], ['tv_simply'], ['web'], ['mweb'], ['tv'], ['android_vr']]
        last_err = None

        for client in clients_to_try:
            ydl_opts = {
                'format': 'best[height<=480][protocol^=m3u8]/best[protocol^=m3u8]/best',
                'quiet': True, 'no_warnings': True, 'noplaylist': True, 'force_ipv4': True,
                'extractor_args': {'youtube': {'player_client': client}},
            }
            if JS_RUNTIMES:
                ydl_opts['js_runtimes'] = JS_RUNTIMES
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(self.youtube_url, download=False)
                    url = info.get('url')
                    if not url:
                        for f in info.get('formats') or []:
                            if f.get('url'):
                                url = f['url']
                                break
                    if url:
                        print(f"[TrafficCamera] URL obtenida con cliente {client[0]}", flush=True)
                        return url
            except Exception as e:
                last_err = e
                continue

        self.stream_error = str(last_err)
        self._yt_cooldown_until = time.time() + 60
        print(f"[TrafficCamera] Todos los clientes fallaron (cooldown 60s): {last_err}", flush=True)
        return None

    def _open_local(self):
        if not self.local_video_path or not os.path.exists(self.local_video_path):
            with self.lock:
                self.traffic_state['frame'] = self._placeholder_frame("Video local no encontrado")
            time.sleep(2)
            return False

        cap = cv2.VideoCapture(self.local_video_path)
        if not cap.isOpened():
            cap.release()
            with self.lock:
                self.traffic_state['frame'] = self._placeholder_frame("No se pudo abrir el video local")
            time.sleep(2)
            return False

        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        self._local_fps = fps if 5 < fps < 120 else 30.0
        self._local_frame_interval = (1.0 / self._local_fps) / self.local_speed
        self._local_next_frame_time = time.perf_counter()
        print(f"[TrafficCamera] Video local abierto ({self._local_fps:.1f} FPS, speed x{self.local_speed:.2f})", flush=True)
        self.cap = cap
        return True

    def _open_youtube(self):
        stream_url = self._get_stream_url()
        if not stream_url:
            self._yt_consecutive_failures += 1
            msg = "Stream no disponible — reintentando..."
            if self._yt_consecutive_failures >= 3 and self.local_video_path and os.path.exists(self.local_video_path):
                msg = "YouTube no responde — cambia a Video local"
            with self.lock:
                self.traffic_state['frame'] = self._placeholder_frame(msg)
            time.sleep(5)
            return False

        cmd = [
            FFMPEG_BIN,
            '-hide_banner', '-loglevel', 'warning',
            '-fflags', 'nobuffer',
            '-flags', 'low_delay',
            '-http_persistent', '0',
            '-reconnect', '1',
            '-reconnect_streamed', '1',
            '-reconnect_delay_max', '5',
            '-rw_timeout', '15000000',
            '-user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            '-i', stream_url,
            '-an',
            '-f', 'rawvideo',
            '-pix_fmt', 'bgr24',
            '-vf', f'fps={YT_TARGET_FPS},scale={YT_WIDTH}:{YT_HEIGHT}',
            '-'
        ]

        try:
            self.yt_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=YT_FRAME_BYTES * 4,
            )
        except Exception as e:
            self._yt_consecutive_failures += 1
            print(f"[TrafficCamera] Error lanzando ffmpeg: {e}", flush=True)
            with self.lock:
                self.traffic_state['frame'] = self._placeholder_frame("No se pudo abrir el stream")
            time.sleep(5)
            return False

        def _drain_stderr(proc):
            try:
                for line in iter(proc.stderr.readline, b''):
                    if not line:
                        break
                    msg = line.decode('utf-8', errors='replace').rstrip()
                    if msg:
                        print(f"[ffmpeg] {msg}", flush=True)
            except Exception:
                pass

        threading.Thread(target=_drain_stderr, args=(self.yt_proc,), daemon=True).start()

        self._yt_consecutive_failures = 0
        self._yt_first_frame_received = False
        self._yt_open_time = time.time()
        print("[TrafficCamera] Stream YouTube abierto (ffmpeg pipe) — esperando primer frame...", flush=True)
        return True

    def _read_youtube_frame(self):
        if not self.yt_proc or self.yt_proc.poll() is not None:
            return False, None
        try:
            raw = self.yt_proc.stdout.read(YT_FRAME_BYTES)
            if len(raw) != YT_FRAME_BYTES:
                return False, None
            frame = np.frombuffer(raw, dtype=np.uint8).reshape((YT_HEIGHT, YT_WIDTH, 3))
            return True, frame.copy()
        except Exception:
            return False, None

    def _looks_like_emergency(self, frame, x1, y1, x2, y2, cls_id):
        h, w, _ = frame.shape
        x1 = max(0, int(x1)); y1 = max(0, int(y1))
        x2 = min(w, int(x2)); y2 = min(h, int(y2))
        if x2 <= x1 or y2 <= y1:
            return False

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return False

        area = (x2 - x1) * (y2 - y1)
        if cls_id == 7 and area < 8000:
            return False
        if cls_id == 5 and area < 12000:
            return False

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        total = crop.shape[0] * crop.shape[1]

        red1 = cv2.inRange(hsv, (0, 130, 110), (10, 255, 255))
        red2 = cv2.inRange(hsv, (170, 130, 110), (180, 255, 255))
        red_ratio = float(np.count_nonzero(red1 | red2)) / total

        yellow = cv2.inRange(hsv, (18, 130, 130), (35, 255, 255))
        yellow_ratio = float(np.count_nonzero(yellow)) / total

        blue = cv2.inRange(hsv, (95, 150, 100), (130, 255, 255))
        blue_ratio = float(np.count_nonzero(blue)) / total

        if red_ratio > 0.18 or yellow_ratio > 0.22:
            return True
        if red_ratio > 0.07 and blue_ratio > 0.05:
            return True
        return False

    def _run_yolo(self, frame, mode):
        h, w = frame.shape[:2]
        infer_sz = 640
        results = self.model(
            frame,
            verbose=False,
            classes=[0, 2, 3, 5, 7],
            conf=self.conf,
            iou=self.iou,
            imgsz=infer_sz,
            max_det=self.max_det,
            agnostic_nms=True,
        )

        counts = {'norte': 0, 'sur': 0, 'este': 0, 'oeste': 0}
        pedestrian_count = 0
        emergency_detected = False
        boxes = []

        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                cls_id = int(box.cls[0].cpu().numpy())

                if cls_id == 0:
                    pedestrian_count += 1
                    boxes.append(('ped', float(x1), float(y1), float(x2), float(y2)))
                    continue

                is_emergency = (
                    cls_id in [5, 7] and
                    self._looks_like_emergency(frame, x1, y1, x2, y2, cls_id)
                )
                if is_emergency:
                    emergency_detected = True
                    boxes.append(('emergency', float(x1), float(y1), float(x2), float(y2)))
                    continue

                matched_zone = None
                for zone_name, poly in self.zones.items():
                    if cv2.pointPolygonTest(
                        (poly * [w, h]).astype(np.int32), (cx, cy), False
                    ) >= 0:
                        counts[zone_name] += 1
                        matched_zone = zone_name
                        break

                boxes.append((matched_zone or 'other', float(x1), float(y1), float(x2), float(y2)))

        return {
            'counts': counts,
            'pedestrians': pedestrian_count,
            'emergency': emergency_detected,
            'boxes': boxes,
            'frame_size': (w, h),
        }

    def _draw_overlay(self, frame, data):
        h, w = frame.shape[:2]

        for zone_name, poly in self.zones.items():
            pts = (poly * [w, h]).astype(np.int32)
            color = self.zone_colors[zone_name]
            cv2.polylines(frame, [pts], True, color, 2)

        if data is None:
            return frame

        ow, oh = data['frame_size']
        sx, sy = w / ow, h / oh

        for kind, x1, y1, x2, y2 in data['boxes']:
            x1, y1, x2, y2 = int(x1 * sx), int(y1 * sy), int(x2 * sx), int(y2 * sy)
            if kind == 'ped':
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 200, 0), 2)
            elif kind == 'emergency':
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 50, 255), 3)
            elif kind in self.zone_colors:
                cv2.rectangle(frame, (x1, y1), (x2, y2), self.zone_colors[kind], 2)
            else:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (130, 130, 130), 1)

        return frame

    def _collect_yolo_result(self):
        if self.pending_yolo is None or not self.pending_yolo.done():
            return
        try:
            data = self.pending_yolo.result()
            self.last_yolo_data = data
            with self.lock:
                self.traffic_state.update(data['counts'])
                self.traffic_state['pedestrians'] = data['pedestrians']
                self.traffic_state['emergency']   = data['emergency']
                self.traffic_state['phase']       = self.current_phase
        except Exception as e:
            print(f"[TrafficCamera] YOLO error: {e}", flush=True)
        self.pending_yolo = None

    def _process_stream(self):
        last_frame_idx = -1
        while self.running:
            try:
                mode = self.mode

                if mode == 'idle':
                    self._close_sources()
                    time.sleep(0.3)
                    continue

                if mode == 'local':
                    if self.cap is None or not self.cap.isOpened():
                        if not self._open_local():
                            continue
                elif mode == 'youtube':
                    if self.yt_proc is None or self.yt_proc.poll() is not None:
                        if not self._open_youtube():
                            continue

                if mode != self.mode:
                    self._close_sources()
                    continue

                if mode == 'local':
                    now = time.perf_counter()
                    wait = self._local_next_frame_time - now
                    if wait > 0:
                        time.sleep(min(wait, 0.1))
                        continue
                    self._local_next_frame_time += self._local_frame_interval
                    if self._local_next_frame_time < now - 0.5:
                        self._local_next_frame_time = now + self._local_frame_interval

                    success, frame = self.cap.read()
                    if not success:
                        self.cap.release()
                        self.cap = cv2.VideoCapture(self.local_video_path)
                        if not self.cap.isOpened():
                            self.cap = None
                            time.sleep(1)
                        last_frame_idx = -1
                        self._local_next_frame_time = time.perf_counter()
                        continue
                    cur_idx = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
                else:
                    success, frame = self._read_youtube_frame()
                    if not success:
                        self._close_sources()
                        self._yt_consecutive_failures += 1
                        time.sleep(1)
                        continue
                    cur_idx = -1

                self._collect_yolo_result()

                if self.pending_yolo is None:
                    if mode == 'local' and cur_idx in self.yolo_cache:
                        self.last_yolo_data = self.yolo_cache[cur_idx]
                    else:
                        frame_for_yolo = frame.copy()
                        cache_idx = cur_idx if mode == 'local' else None
                        def _job(f=frame_for_yolo, m=mode, ci=cache_idx):
                            data = self._run_yolo(f, m)
                            if ci is not None:
                                self.yolo_cache[ci] = data
                            return data
                        self.pending_yolo = self.executor.submit(_job)

                display = self._draw_overlay(frame, self.last_yolo_data)

                jpeg_q = 82 if mode == 'local' else 78
                _, buffer = cv2.imencode('.jpg', display, [cv2.IMWRITE_JPEG_QUALITY, jpeg_q])
                with self.lock:
                    self.traffic_state['frame'] = buffer.tobytes()

                last_frame_idx = cur_idx

            except Exception as e:
                print(f"[TrafficCamera] Error en el loop: {e}", flush=True)
                self._close_sources()
                with self.lock:
                    self.traffic_state['frame'] = self._placeholder_frame("Error de stream")
                time.sleep(3)

    def get_frame(self):
        with self.lock:
            return self.traffic_state['frame']

    def get_counts(self):
        with self.lock:
            return self.traffic_state.copy()
