import cv2
from ultralytics import YOLO

model = YOLO("best.pt")

cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    results = model(frame, conf=0.8)

    annotated = results[0].plot()

    if len(results[0].boxes) > 0:
        for box in results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            # 🎯 Center of object
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)

            # Draw center
            cv2.circle(annotated, (cx, cy), 5, (0, 0, 255), -1)
            # 📝 Put coordinates text on frame
            text = f"X:{cx} Y:{cy}"
            cv2.putText(annotated, text, (cx + 10, cy - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (0, 255, 0), 2)

            print(f"Bottle at: X={cx}, Y={cy}")

    cv2.imshow("Bottle Detection", annotated)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
