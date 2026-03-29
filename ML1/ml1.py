import cv2
from ultralytics import YOLO

model = YOLO("best.pt")

cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # 🔥 Apply confidence threshold
    results = model(frame, conf=0.8)

    annotated = results[0].plot()
    cv2.imshow("Bottle Detection", annotated)

    # Only trigger if confident detection exists
    if len(results[0].boxes) > 0:
        print("Bottle detected (high confidence) 🚀")

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()