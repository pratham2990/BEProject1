from flask import Flask
from flask import render_template
from flask import Response
from flask import jsonify
from flask import request

from ultralytics import YOLO
from picamera2 import Picamera2

import cv2
import time
import can
import threading

# ---------------- APP ----------------
app = Flask(__name__)

# ---------------- MODEL ----------------
model = YOLO("best.pt")

# ---------------- CAMERA ----------------
picam2 = Picamera2()

config = picam2.create_preview_configuration(
    main={"size": (640, 480)}
)

picam2.configure(config)
picam2.start()

# ---------------- CAN ----------------
bus = can.interface.Bus(
    channel='can0',
    bustype='socketcan'
)

# ls, ld, rs, rd
control_data = [0, 0, 0, 0]

# ---------------- DETECTION DATA ----------------
detection_data = {
    "label": "None",
    "confidence": 0
}

# ---------------- CAN SENDER THREAD ----------------
def can_sender():

    global control_data

    SEND_INTERVAL = 0.02  # 50Hz

    while True:

        msg = can.Message(
            arbitration_id=0x100,
            data=control_data,
            is_extended_id=False
        )

        try:

            bus.send(msg)

        except can.CanError:

            print("CAN send failed")

        time.sleep(SEND_INTERVAL)

threading.Thread(
    target=can_sender,
    daemon=True
).start()

# ---------------- VIDEO STREAM ----------------
def generate_frames():

    global detection_data

    while True:

        # Capture frame
        frame = picam2.capture_array()

        # FIX COLORS
        frame = cv2.cvtColor(
            frame,
            cv2.COLOR_RGB2BGR
        )

        # YOLO detection
        results = model.predict(
            frame,
            imgsz=320,
            conf=0.5,
            verbose=False
        )

        found = False

        # Process detections
        for r in results:

            boxes = r.boxes

            for box in boxes:

                found = True

                cls = int(box.cls[0])

                conf = float(box.conf[0])

                label = model.names[cls]

                detection_data = {
                    "label": label,
                    "confidence": round(conf, 2)
                }

        if not found:

            detection_data = {
                "label": "None",
                "confidence": 0
            }

        # Draw detections
        annotated = results[0].plot()

        # Encode frame
        _, buffer = cv2.imencode(
            '.jpg',
            annotated
        )

        frame_bytes = buffer.tobytes()

        # Stream frame
        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n'
            + frame_bytes +
            + b'\r\n'
        )

# ---------------- ROUTES ----------------
@app.route('/')
def index():

    return render_template(
        'index.html'
    )

@app.route('/video_feed')
def video_feed():

    return Response(
        generate_frames(),
        mimetype=
        'multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/get_detection')
def get_detection():

    return jsonify(detection_data)

# ---------------- MOVEMENT CONTROL ----------------
@app.route('/control', methods=['POST'])
def control():

    global control_data

    data = request.form

    control_data = [

        int(data['ls']),
        int(data['ld']),
        int(data['rs']),
        int(data['rd'])
    ]

    return "OK"

# ---------------- MAIN ----------------
if __name__ == '__main__':

    app.run(
        host='0.0.0.0',
        port=5000,
        threaded=True
    )
