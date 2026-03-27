from flask import Flask, request, render_template, Response
import can
import cv2
import threading
import time

app = Flask(__name__)

# ---------------- CAN SETUP ----------------
bus = can.interface.Bus(channel='can0', bustype='socketcan')

control_data = [0, 0, 0, 0]
last_sent_data = [0, 0, 0, 0]

# ---------------- CAN SENDER THREAD ----------------
def can_sender():
    global control_data, last_sent_data

    while True:
        # Send only if data changed
        if control_data != last_sent_data:

            msg = can.Message(
                arbitration_id=0x100,
                data=control_data,
                is_extended_id=False
            )

            try:
                bus.send(msg)
                print("send" , control_data)
                last_sent_data = control_data.copy()
            except can.CanError:
                print("CAN buffer full")

        time.sleep(0.05)  # small loop delay (20ms)

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

        ret, buffer = cv2.imencode('.jpg', frame_global, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

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

# ---------------- MAIN ----------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
