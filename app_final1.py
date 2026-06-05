from flask import Flask
from flask import render_template
from flask import Response
from flask import jsonify
from flask import request

from ultralytics import YOLO

import cv2
import time
import threading

# =========================================================
# GPIO MOTOR
# =========================================================
from gpiozero import Motor

# =========================================================
# SERVO IMPORTS
# =========================================================
import board
import busio

from adafruit_pca9685 import PCA9685

# =========================================================
# APP
# =========================================================
app = Flask(__name__)

# =========================================================
# MODEL
# =========================================================
model = YOLO("best.pt")

# =========================================================
# USB CAMERA
# =========================================================
camera = cv2.VideoCapture(
    0,
    cv2.CAP_V4L2
)

camera.set(
    cv2.CAP_PROP_BUFFERSIZE,
    1
)

camera.set(
    cv2.CAP_PROP_FRAME_WIDTH,
    320
)

camera.set(
    cv2.CAP_PROP_FRAME_HEIGHT,
    240
)

camera.set(
    cv2.CAP_PROP_FPS,
    30
)

# =========================================================
# FRAME BUFFERS
# =========================================================
frame_global = None

annotated_global = None

# =========================================================
# ROBOT MODE
# =========================================================
auto_mode = False

# =========================================================
# MOTOR SETUP (L298N)
# =========================================================
left_motor = Motor(
    forward=17,
    backward=27,
    enable=18
)

right_motor = Motor(
    forward=22,
    backward=23,
    enable=19
)

# =========================================================
# MOTOR FUNCTIONS
# =========================================================
def stop_robot():

    left_motor.stop()
    right_motor.stop()

def move_forward(speed=0.6):

    left_motor.forward(speed)
    right_motor.forward(speed)

def move_backward(speed=0.6):

    left_motor.backward(speed)
    right_motor.backward(speed)

def turn_left(speed=0.5):

    left_motor.forward(speed)
    right_motor.backward(speed)

def turn_right(speed=0.5):

    left_motor.backward(speed)
    right_motor.forward(speed)

# =========================================================
# SERVO SETUP
# =========================================================
i2c = busio.I2C(
    board.SCL,
    board.SDA
)

pca = PCA9685(i2c)

pca.frequency = 50

NUM_SERVOS = 5

SERVO_CHANNELS = [4, 8, 9, 12, 13]

current_positions = [375] * NUM_SERVOS
servo_angles = [90, 90, 90, 90, 90]

for i in range(NUM_SERVOS):

    pca.channels[
        SERVO_CHANNELS[i]
    ].duty_cycle = current_positions[i] * 16

# =========================================================
# DETECTION DATA
# =========================================================
detection_data = {

    "label": "None",

    "confidence": 0,

    "x": 0,
    "y": 0,

    "width": 0,
    "height": 0,

    "position": "NONE",

    "fps": 0,

    "robot_status": "MANUAL MODE"
}

# =========================================================
# HELPER FUNCTIONS
# =========================================================
def map_angle_to_pwm(angle):

    return int(
        150 + (angle / 180.0) * (600 - 150)
    )

# =========================================================
# SERVO MOTION
# =========================================================
def move_servo_smooth(
    index,
    target_pwm
):

    global current_positions

    current_pwm = current_positions[index]

    if abs(
        target_pwm -
        current_pwm
    ) < 5:

        return

    diff = (
        target_pwm -
        current_pwm
    )

    steps = 20

    step_size = diff / steps

    for _ in range(steps):

        current_pwm += step_size

        pca.channels[
            SERVO_CHANNELS[index]
        ].duty_cycle = int(
            current_pwm * 16
        )

        time.sleep(0.01)

    current_positions[index] = target_pwm

# =========================================================
# CAMERA THREAD
# =========================================================
def camera_loop():

    global frame_global

    while True:

        success, frame = camera.read()

        if success:

            frame_global = frame

        else:

            print(
                "Camera Read Failed"
            )

            time.sleep(0.1)

threading.Thread(
    target=camera_loop,
    daemon=True
).start()

# =========================================================
# DETECTION THREAD
# =========================================================
def detection_loop():

    global frame_global
    global annotated_global
    global detection_data

    prev_time = time.time()

    while True:

        if frame_global is None:

            time.sleep(0.01)
            continue

        frame = frame_global.copy()

        # Faster YOLO
        results = model.predict(
            frame,
            imgsz=256,
            conf=0.45,
            verbose=False
        )

        found = False

        for r in results:

            for box in r.boxes:

                found = True

                cls = int(box.cls[0])

                conf = float(box.conf[0])

                label = model.names[cls]

                x1, y1, x2, y2 = box.xyxy[0]

                x_center = int((x1 + x2) / 2)
                y_center = int((y1 + y2) / 2)

                width = int(x2 - x1)
                height = int(y2 - y1)

                if x_center < 110:

                    position = "LEFT"

                elif x_center > 210:

                    position = "RIGHT"

                else:

                    position = "CENTER"

                curr_time = time.time()

                fps = int(
                    1 / max(
                        curr_time - prev_time,
                        0.0001
                    )
                )

                prev_time = curr_time

                detection_data.update({

                    "label": label,

                    "confidence": round(
                        conf,
                        2
                    ),

                    "x": x_center,
                    "y": y_center,

                    "width": width,
                    "height": height,

                    "position": position,

                    "fps": fps
                })

        if not found:

            detection_data.update({

                "label": "None",

                "confidence": 0,

                "x": 0,
                "y": 0,

                "width": 0,
                "height": 0,

                "position": "NONE"
            })

        annotated = results[0].plot()

        cv2.line(
            annotated,
            (160, 0),
            (160, 240),
            (0, 255, 0),
            2
        )

        cv2.line(
            annotated,
            (110, 0),
            (110, 240),
            (255, 0, 0),
            1
        )

        cv2.line(
            annotated,
            (210, 0),
            (210, 240),
            (255, 0, 0),
            1
        )

        cv2.putText(
            annotated,
            f"FPS:{detection_data['fps']}",
            (10, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0,255,0),
            2
        )

        cv2.putText(
            annotated,
            detection_data[
                "robot_status"
            ],
            (10, 45),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0,255,255),
            2
        )

        annotated_global = annotated

threading.Thread(
    target=detection_loop,
    daemon=True
).start()

# =========================================================
# AUTO FOLLOW
# =========================================================
def auto_follow_loop():

    global auto_mode
    global detection_data

    while True:

        if auto_mode:

            position = detection_data[
                "position"
            ]

            width = detection_data[
                "width"
            ]

            if position == "LEFT":

                detection_data[
                    "robot_status"
                ] = "TURNING LEFT"

                turn_left(0.45)

            elif position == "RIGHT":

                detection_data[
                    "robot_status"
                ] = "TURNING RIGHT"

                turn_right(0.45)

            elif position == "CENTER":

                if width < 120:

                    detection_data[
                        "robot_status"
                    ] = "MOVING TO BOTTLE"

                    move_forward(0.55)

                else:

                    detection_data[
                        "robot_status"
                    ] = "BOTTLE REACHED"

                    stop_robot()

            else:

                detection_data[
                    "robot_status"
                ] = "SEARCHING"

                stop_robot()

        else:

            detection_data[
                "robot_status"
            ] = "MANUAL MODE"

        time.sleep(0.03)

threading.Thread(
    target=auto_follow_loop,
    daemon=True
).start()

# =========================================================
# VIDEO STREAM
# =========================================================
def generate_frames():

    global annotated_global

    while True:

        if annotated_global is None:

            time.sleep(0.01)
            continue

        _, buffer = cv2.imencode(

            '.jpg',

            annotated_global,

            [
                int(
                    cv2.IMWRITE_JPEG_QUALITY
                ),
                60
            ]
        )

        frame_bytes = buffer.tobytes()

        yield (

            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n'

            + frame_bytes +

            b'\r\n'
        )

# =========================================================
# ROUTES
# =========================================================
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

    return jsonify(
        detection_data
    )

# =========================================================
# MANUAL MOTOR CONTROL
# =========================================================
@app.route(
    '/control',
    methods=['POST']
)
def control():

    global auto_mode

    if auto_mode:

        return "AUTO MODE"

    data = request.form

    ls = int(data['ls'])
    ld = int(data['ld'])

    rs = int(data['rs'])
    rd = int(data['rd'])

    # LEFT
    if ls == 1:

        left_motor.stop()

    else:

        if ld == 0:

            left_motor.forward(
                ls / 255
            )

        else:

            left_motor.backward(
                ls / 255
            )

    # RIGHT
    if rs == 1:

        right_motor.stop()

    else:

        if rd == 0:

            right_motor.forward(
                rs / 255
            )

        else:

            right_motor.backward(
                rs / 255
            )

    return "OK"

# =========================================================
# AUTO MODE
# =========================================================
@app.route(
    '/toggle_auto',
    methods=['POST']
)
def toggle_auto():

    global auto_mode

    auto_mode = not auto_mode

    stop_robot()

    return jsonify({

        "auto_mode":
        auto_mode
    })

# =========================================================
# SERVO
# =========================================================
@app.route(
    '/servo',
    methods=['POST']
)
def servo_control():
    global servo_angles
    data = request.form

    try:

        servo_id = int(
            data['id']
        ) - 1

        angle = float(data['angle'])
        

        servo_angles[servo_id] = angle

        if servo_id >= NUM_SERVOS:

            return "Invalid"

        pwm_val = map_angle_to_pwm(
            angle
        )

        threading.Thread(

            target=
            move_servo_smooth,

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

# =========================================================
# SERVO STATUS
# =========================================================
@app.route('/get_servos')
def get_servos():

    return jsonify({

        "servo1": round(servo_angles[0], 1),

        "servo2": round(servo_angles[1], 1),

        "servo3": round(servo_angles[2], 1),

        "servo4": round(servo_angles[3], 1),

        "servo5": round(servo_angles[4], 1)
    })

# =========================================================
# MAIN
# =========================================================
if __name__ == '__main__':

    app.run(

        host='0.0.0.0',

        port=5000,

        threaded=True
    )

