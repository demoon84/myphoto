import os
import cv2
import mediapipe as mp
import time

# Initialize MediaPipe Face Detection
mp_face_detection = mp.solutions.face_detection
mp_drawing = mp.solutions.drawing_utils

DETECTION_CONFIDENCE = 0.5

def run_test(folders):
    # Initialize detector
    with mp_face_detection.FaceDetection(
        model_selection=1, # 0: Short range (2m), 1: Full range (5m) - Using 1 for better recall
        min_detection_confidence=DETECTION_CONFIDENCE
    ) as face_detection:
        
        for name, path in folders.items():
            print(f"\n--- Testing {name} ({path}) ---")
            if not os.path.exists(path):
                print("Path not found.")
                continue

            files = [f for f in os.listdir(path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.heic'))]
            detected_count = 0
            
            for filename in files:
                filepath = os.path.join(path, filename)
                
                # Encode file path for cv2 (Korean path support)
                img_array = np.fromfile(filepath, np.uint8)
                image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                
                if image is None:
                    # Try pil fallback if cv2 fails on weird encoding
                    continue

                # Convert BGR to RGB
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                
                # Process
                results = face_detection.process(image)
                
                if results.detections:
                    detected_count += 1
                    # print(f"[Detected] {filename} (Score: {results.detections[0].score[0]:.2f})")
                else:
                    if name == "People":
                        print(f"[MISS] {filename}")
                    pass

            print(f"Result: {detected_count}/{len(files)} detected as People")

import numpy as np

folders = {
    "People (Sample)": "/Users/demoon/사진/sample",
    "Misc (Sample4)": "/Users/demoon/사진/sample4",
    "Food (Sample3)": "/Users/demoon/사진/sample3"
}

run_test(folders)
