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

# ---------------- SERVO IMPORTS ----------------
import board
import busio

from adafruit_pca9685 import PCA9685

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

# ---------------- SERVO ----------------
i2c = busio.I2C(
    board.SCL,
    board.SDA
)

pca = PCA9685(i2c)

pca.frequency = 50

NUM_SERVOS = 5

SERVO_CHANNELS = [4, 8, 9, 12, 13]

current_positions = [375] * NUM_SERVOS

# Initialize servos
for i in range(NUM_SERVOS):

    pca.channels[
        SERVO_CHANNELS[i]
    ].duty_cycle = current_positions[i] * 16

# ---------------- DETECTION DATA ----------------
detection_data = {
    "label": "None",
    "confidence": 0
}

# ---------------- HELPER FUNCTIONS ----------------
def map_angle_to_pwm(angle):

    return int(
        150 + (angle / 180.0) * (600 - 150)
    )

# ---------------- SMOOTH SERVO MOTION ----------------
def move_servo_smooth(
    index,
    target_pwm
):

    global current_positions

    current_pwm = current_positions[index]

    # Deadband
    if abs(target_pwm - current_pwm) < 5:
        return

    diff = target_pwm - current_pwm

    steps = 20

    step_size = diff / steps

    for _ in range(steps):

        current_pwm += step_size

        pca.channels[
            SERVO_CHANNELS[index]
        ].duty_cycle = int(current_pwm * 16)

        time.sleep(0.01)

    current_positions[index] = target_pwm

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
            b'\r\n'
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

# ---------------- MOTOR CONTROL ----------------
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

# ---------------- SERVO CONTROL ----------------
@app.route('/servo', methods=['POST'])
def servo_control():

    data = request.form

    try:

        servo_id = int(data['id']) - 1

        angle = float(data['angle'])

        if servo_id >= NUM_SERVOS:

            return "Invalid Servo"

        pwm_val = map_angle_to_pwm(
            angle
        )

        threading.Thread(
            target=move_servo_smooth,
            args=(
                servo_id,
                pwm_val
            ),
            daemon=True
        ).start()

        return "OK"

    except Exception as e:

        print(e)

        return "ERROR"

# ---------------- MAIN ----------------
if __name__ == '__main__':

    app.run(
        host='0.0.0.0',
        port=5000,
        threaded=True
    )

