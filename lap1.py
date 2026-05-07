import cv2
import threading
import requests
import time

from ultralytics import YOLO

# ---------------- MODEL ----------------
model = YOLO("best.pt")

# ---------------- STREAM ----------------
stream_url = "http://100.118.238.44:5000/video"

frame = None

def capture_frames():

    global frame

    cap = cv2.VideoCapture(stream_url)

    while True:

        ret, img = cap.read()

        if ret:
            frame = img

threading.Thread(
    target=capture_frames,
    daemon=True
).start()

last_sent = 0

# ---------------- MAIN LOOP ----------------
while True:

    if frame is None:
        continue

    img = frame.copy()

    # Resize for speed
    img_small = cv2.resize(img, (320, 240))

    # YOLO inference
    results = model(img_small)

    for r in results:

        for box in r.boxes:

            conf = float(box.conf[0])

            # Only detections >60%
            if conf < 0.6:
                continue

            cls = int(box.cls[0])

            label = model.names[cls]

            # Box coords
            x1, y1, x2, y2 = map(
                int,
                box.xyxy[0]
            )

            # Object center
            center_x = (x1 + x2) // 2

            # Position logic
            if center_x < 106:
                position = "LEFT"

            elif center_x < 213:
                position = "CENTER"

            else:
                position = "RIGHT"

            # Scale back to original frame
            h_orig, w_orig, _ = img.shape

            h_small, w_small, _ = img_small.shape

            scale_x = w_orig / w_small
            scale_y = h_orig / h_small

            x1 = int(x1 * scale_x)
            y1 = int(y1 * scale_y)
            x2 = int(x2 * scale_x)
            y2 = int(y2 * scale_y)

            # Draw rectangle
            cv2.rectangle(
                img,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                2
            )

            # Draw label bg
            cv2.rectangle(
                img,
                (x1, y1 - 30),
                (x1 + 260, y1),
                (0, 255, 0),
                -1
            )

            text = f"{label} {conf:.2f} {position}"

            # Draw text
            cv2.putText(
                img,
                text,
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 0),
                2
            )

            # Send detection to Pi
            if time.time() - last_sent > 0.5:

                requests.post(

                    "http://100.118.238.44:5000/detection",

                    json={
                        "label": label,
                        "confidence": conf,
                        "position": position
                    }
                )

                last_sent = time.time()

    cv2.imshow("Detection", img)

    if cv2.waitKey(1) == 27:
        break

cv2.destroyAllWindows()