import sys
import os
import cv2
import tensorflow as tf
import tensorflow_hub as hub
import mediapipe as mp
import numpy as np

# Suppress Warnings
import warnings
warnings.filterwarnings("ignore")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# --- CONFIG ---
conf_target_file = "/Users/demoon/사진/sample2/P20160609_092820000_5AC775BA-50B3-4674-990F-3D2E2661D594.jpg"

print(f"Analyzing file: {conf_target_file}")

# 1. Load Image
try:
    img_array = np.fromfile(conf_target_file, np.uint8)
    img_cv = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    if img_cv is None:
        print("Error: Failed to load image (OpenCV)")
        sys.exit(1)
    img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
    print("Image loaded successfully.")
except Exception as e:
    print(f"Error loading image: {e}")
    sys.exit(1)

# 2. MediaPipe Detection
print("\n--- MediaPipe Detection ---")
mp_face_detection = mp.solutions.face_detection
with mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5) as face_detection:
    results = face_detection.process(img_rgb)
    if results.detections:
        print(f"Faces detected: {len(results.detections)}")
        for i, detection in enumerate(results.detections):
            score = detection.score[0]
            print(f"  Face {i+1}: Score = {score:.4f}")
    else:
        print("No faces detected with Model 1 (Long Range).")
        print("Trying Model 0 (Short Range)...")
        with mp_face_detection.FaceDetection(model_selection=0, min_detection_confidence=0.5) as face_detection_short:
             results_short = face_detection_short.process(img_rgb)
             if results_short.detections:
                 print(f"Faces detected with Model 0: {len(results_short.detections)}")
                 for i, detection in enumerate(results_short.detections):
                     score = detection.score[0]
                     print(f"  Face {i+1}: Score = {score:.4f}")
             else:
                 print("No faces detected with Model 0 either.")

# 3. MobileNet Context
print("\n--- MobileNet V3 Context ---")
try:
    path_cls = "https://tfhub.dev/google/imagenet/mobilenet_v3_small_100_224/classification/5"
    model = hub.load(path_cls)
    
    # Load Labels
    labels_path = "ImageNetLabels.txt"
    with open(labels_path, "r") as f:
        labels = [line.strip() for line in f.readlines()]
        
    img_tf = tf.image.convert_image_dtype(img_rgb, tf.float32)
    img_tf = tf.image.resize(img_tf, [224, 224])
    img_tf = tf.expand_dims(img_tf, 0)
    
    logits = model(img_tf)
    probs = tf.nn.softmax(logits)
    
    top_k_indices = tf.math.top_k(probs, k=10).indices.numpy()[0]
    top_k_probs = tf.math.top_k(probs, k=10).values.numpy()[0]
    
    print("Top 10 Predictions:")
    for i in range(10):
        idx = top_k_indices[i]
        label = labels[idx]
        prob = top_k_probs[i]
        print(f"  {i+1}. {label} ({prob:.4f})")
        
except Exception as e:
    print(f"MobileNet Error: {e}")
