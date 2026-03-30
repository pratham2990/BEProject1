from flask import Flask, request, render_template, Response
import can
import cv2
import threading
import time

# Servo
import board
import busio
from adafruit_pca9685 import PCA9685

app = Flask(__name__)

# ---------------- CAN SETUP ----------------
bus = can.interface.Bus(channel='can0', bustype='socketcan')
control_data = [0, 0, 0, 0]

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
            bus.send(msg, timeout=0.01)
        except can.CanError:
            print("CAN buffer full")

        time.sleep(SEND_INTERVAL)

threading.Thread(target=can_sender, daemon=True).start()

# ---------------- CAMERA SETUP ----------------
camera = cv2.VideoCapture(0, cv2.CAP_V4L2)
camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
camera.set(3, 320)
camera.set(4, 240)
camera.set(5, 30)

frame_global = None

def camera_thread():
    global frame_global
    while True:
        success, frame = camera.read()
        if success:
            frame_global = frame

threading.Thread(target=camera_thread, daemon=True).start()

# ---------------- VIDEO STREAM ----------------
def generate_frames():
    global frame_global
    while True:
        if frame_global is None:
            continue

        _, buffer = cv2.imencode('.jpg', frame_global, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

# ---------------- SERVO SETUP ----------------
i2c = busio.I2C(board.SCL, board.SDA)
pca = PCA9685(i2c)
pca.frequency = 50  # 🔥 better stability

NUM_SERVOS = 5
SERVO_CHANNELS = [4, 8, 9, 12, 13]

current_positions = [375] * NUM_SERVOS

# Initialize servos
for i in range(NUM_SERVOS):
    pca.channels[SERVO_CHANNELS[i]].duty_cycle = current_positions[i] * 16

def map_angle_to_pwm(angle):
    return int(150 + (angle / 180.0) * (600 - 150))

# 🔥 IMPROVED SMOOTH MOTION
def move_servo_smooth(index, target_pwm):
    current_pwm = current_positions[index]

    # Deadband (ignore tiny movements)
    if abs(target_pwm - current_pwm) < 5:
        return

    diff = target_pwm - current_pwm
    steps = 30
    step_size = diff / steps

    for _ in range(steps):
        current_pwm += step_size
        pca.channels[SERVO_CHANNELS[index]].duty_cycle = int(current_pwm * 16)
        time.sleep(0.01)

    current_positions[index] = target_pwm

# ---------------- ROUTES ----------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video')
def video():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

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

@app.route('/servo', methods=['POST'])
def servo_control():
    data = request.form

    try:
        servo_id = int(data['id']) - 1
        angle = float(data['angle'])

        if servo_id >= NUM_SERVOS:
            return "Invalid servo"

        pwm_val = map_angle_to_pwm(angle)

        threading.Thread(
            target=move_servo_smooth,
            args=(servo_id, pwm_val),
            daemon=True
        ).start()

        return "OK"

    except Exception as e:
        print(e)
        return "Error"

# ---------------- MAIN ----------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)