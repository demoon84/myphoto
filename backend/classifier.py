import warnings
import sys
import os
import traceback

# ABSOLUTE FIRST: Suppress all urllib3 warnings BEFORE any other imports
warnings.filterwarnings("ignore", message=".*NotOpenSSLWarning.*")
warnings.filterwarnings("ignore", category=UserWarning)

# Set UTF-8 encoding for stdin/stdout to handle Korean paths
sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')

def log_error(msg):
    print(json.dumps({"status": "error", "message": msg}), flush=True)

try:
    import sqlite3
    import json
    import requests
    import shutil
    import pillow_heif
    import subprocess
    import cv2
    import numpy as np
    import tensorflow as tf
    import tensorflow_hub as hub
    import mediapipe as mp
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading
    import queue
    import hashlib
except Exception as e:
    # Use fallback json via simple print since imports might have failed
    import json
    print(json.dumps({"status": "error", "message": f"Critical Import Error: {str(e)}\n{traceback.format_exc()}"}))
    sys.stdout.flush()
    sys.exit(1)

# Control Flags
PAUSE_EVENT = threading.Event()
PAUSE_EVENT.set()
STOP_EVENT = threading.Event()

# Models
TF_MODEL_CLS = None
TF_LABELS = []
MP_FACE_DETECTION = None

# Paths (Local)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'models', 'mobilenet_v3')
LABELS_PATH = os.path.join(BASE_DIR, 'models', 'ImageNetLabels.txt')

# Keywords
FOOD_KEYWORDS = [
    'food', 'dish', 'eating', 'meal', 'soup', 'bread', 'pizza', 'burger', 'sandwich', 'hotdog', 
    'fruit', 'vegetable', 'meat', 'beef', 'pork', 'chicken', 'fish', 'seafood', 'sushi',
    'dessert', 'cake', 'pie', 'cookie', 'ice cream', 'chocolate', 
    'coffee', 'tea', 'drink', 'beverage', 'juice', 'beer', 'wine', 'cocktail',
    'bottle', 'cup', 'mug', 'goblet', 'wineglass', 'beaker', 'bowl', 'plate', 'tray', 'pot', 'pan', 'wok', 'stove', 
    'bakery', 'restaurant', 'cafe', 'cooking',
    'lemon', 'orange', 'banana', 'apple', 'grape',
    'strawberry', 'corn', 'mushroom', 'broccoli', 'cucumber', 'tomato', 'potato', 'onion'
]

STRONG_PEOPLE_LABELS = [
    'baby', 'infant', 'toddler', 'child', 'boy', 'girl', 'man', 'woman', 'person', 'human',
    'pajama', 'crib', 'cradle', 'bassinet', 'stroller', 'pram', 'bonnet',
    'groom', 'gown', 'suit', 'necktie', 'necklace', 'kimono',
    'swing', 'parallel bars', 'horizontal bar'
]

def load_models():
    global TF_MODEL_CLS, TF_LABELS
    
    if TF_MODEL_CLS is None:
        print(json.dumps({"status": "startup", "message": "Loading AI Models..."}), flush=True)
        
        # Load MobileNet V3 (Context Analysis) from Local
        try:
            if not os.path.exists(MODEL_PATH):
                 log_error(f"Model not found at {MODEL_PATH}")
                 return

            TF_MODEL_CLS = hub.load(MODEL_PATH)
        except Exception as e:
            log_error(f"Failed to load model: {e}")
            raise e
        
        # Load Labels from Local
        try:
            if not os.path.exists(LABELS_PATH):
                 log_error(f"Labels not found at {LABELS_PATH}")
                 return

            with open(LABELS_PATH, 'r') as f:
                TF_LABELS = [line.strip() for line in f.readlines()]
        except Exception as e:
            log_error(f"Failed to load labels: {e}")
            raise e
            
        print(json.dumps({"status": "ready", "message": "AI Engine Ready"}), flush=True)

def calculate_file_hash(filepath):
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except:
        return None

def files_are_identical(p1, p2):
    try:
        if os.path.exists(p1) and os.path.exists(p2):
            if os.path.getsize(p1) != os.path.getsize(p2):
                return False
            return calculate_file_hash(p1) == calculate_file_hash(p2)
        return False
    except:
        return False

pillow_heif.register_heif_opener()

def move_preserving_metadata(src, dst):
    try:
        if os.name != 'nt':
            subprocess.run(["mv", src, dst], check=True)
        else:
            shutil.move(src, dst)
    except Exception:
        try:
            shutil.move(src, dst)
        except Exception as e:
            print(json.dumps({"status": "error", "message": f"Move failed: {e}"}))

def detect_faces_mediapipe(img_rgb):
    """Run MediaPipe Face Detection (Hybrid Range)"""
    # 1. Try Long Range Model (Best for general photos)
    with mp.solutions.face_detection.FaceDetection(
        model_selection=1, 
        min_detection_confidence=0.5
    ) as face_detection:
        results = face_detection.process(img_rgb)
        
        if results.detections:
            max_score = 0.0
            for detection in results.detections:
                score = detection.score[0]
                if score > max_score: max_score = score
            return len(results.detections), max_score

    # 2. Fallback: Try Short Range Model (Best for selfies/close-ups)
    with mp.solutions.face_detection.FaceDetection(
        model_selection=0, 
        min_detection_confidence=0.5
    ) as face_detection_short:
        results_short = face_detection_short.process(img_rgb)
        
        if results_short.detections:
            max_score = 0.0
            for detection in results_short.detections:
                score = detection.score[0]
                if score > max_score: max_score = score
            return len(results_short.detections), max_score

    return 0, 0.0

def classify_image(file_path):
    try:
        if TF_MODEL_CLS is None:
            load_models()
            
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            return "Error"
            
        # 1. Read Image
        try:
            # Use OpenCV for MediaPipe (needs numpy array)
            # Handle Korean paths by reading as byte stream first
            img_array = np.fromfile(file_path, np.uint8)
            img_cv = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if img_cv is None: return "Misc"
            
            img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
            
            # Prepare for TF (Context)
            img_tf = tf.image.convert_image_dtype(img_rgb, tf.float32)
            img_tf = tf.image.resize(img_tf, [224, 224])
            img_tf = tf.expand_dims(img_tf, 0)
        except Exception:
            return "Misc"
            
        # 2. MediaPipe Face Detection (The Truth)
        face_count, face_score = detect_faces_mediapipe(img_rgb)
        
        # 3. MobileNet Context Analysis
        logits = TF_MODEL_CLS(img_tf)
        probs = tf.nn.softmax(logits)
        top_k = tf.math.top_k(probs, k=25).indices.numpy()[0]
        predicted_labels = [TF_LABELS[i].lower() for i in top_k]
        
        # Check Keywords
        is_food_context = False
        is_people_context = False
        
        for i, label in enumerate(predicted_labels):
            label_parts = label.replace(',', '').split()
            
            if i < 5: # Strong context only
                for keyword in FOOD_KEYWORDS:
                    if keyword in label_parts:
                        is_food_context = True
                        break
            
            if i < 15: # Broader check for people context
                for keyword in STRONG_PEOPLE_LABELS:
                    if keyword in label_parts:
                        is_people_context = True
                        break
        
        # --- FINAL DECISION LOGIC (V3 Hybrid + Safety) ---
        
        # Rule 1: Conflict Resolution (Face vs Food)
        if face_count > 0 and is_food_context:
            # MediaPipe says Face, MobileNet says Food. Who to trust?
            # Plate/Food false positives usually have scores ~0.60. Real faces usually > 0.75.
            # Set threshold to 0.70 to separate them.
            if face_score < 0.70: 
                return "Food"
            else:
                return "People" # Strong face confidence overrides food context (e.g. person eating)

        # Rule 2: Verified Face -> People
        if face_count > 0:
            return "People"
            
        # Rule 3: Strong Food Context -> Food
        if is_food_context:
            return "Food"
            
        # Rule 3: Missing Face but Strong People Context -> People (Rescue)
        # Allows 'bonnet', 'cradle', 'bassinet' etc to save the photo even if no face is visible.
        # But ensure it's not food.
        if is_people_context and not is_food_context:
             return "People"
        
        # Rule 4: Everything else -> Misc
        return "Misc"

    except Exception as e:
        return "Misc"

def classify_task(img_data, dest_dir):
    img_id, current_path, filename, exif_date = img_data
    try:
        if not os.path.exists(current_path):
            return None, {"status": "error", "message": f"File not found: {current_path}"}
        
        category = classify_image(current_path)
        
        # Determine target path
        if category == "Misc":
            target_dir = os.path.join(dest_dir, exif_date)
        else:
            target_dir = os.path.join(dest_dir, exif_date, category)
            
        os.makedirs(target_dir, exist_ok=True)
        final_path = os.path.join(target_dir, filename)
        
        # Duplicate handling
        base, ext = os.path.splitext(filename)
        
        if os.path.exists(final_path):
            if files_are_identical(current_path, final_path):
                # Duplicate found: Do NOT delete source, just skip
                return None, {"status": "processing", "file": filename, "category": "Skipped"}
            
            counter = 1
            while True:
                candidate = os.path.join(target_dir, f"{base}_{counter}{ext}")
                if not os.path.exists(candidate):
                    final_path = candidate
                    break
                counter += 1
        
        if current_path != final_path:
            move_preserving_metadata(current_path, final_path)
        
        return (final_path, category, img_id), \
               {"status": "processing", "file": filename, "category": category if category != "Misc" else exif_date}
               
    except Exception as e:
        return None, {"status": "error", "message": f"Error {filename}: {str(e)}"}

def run_classification(dest_dir, db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, dest_path, filename, exif_date FROM files WHERE type='image' AND processed=0")
        images = cursor.fetchall()
        total_images = len(images)
        
        if total_images == 0:
            print(json.dumps({"status": "skipped", "message": "No new images."}))
            conn.close()
            return
    except Exception as e:
        print(json.dumps({"status": "error", "message": f"DB Error: {e}"}))
        return

    load_models()
    processed_count = 0
    updates = []
    max_workers = min(4, os.cpu_count() or 1)
    
    # We must close DB connection before threading to avoid lock issues if passing it (not passing here)
    conn.close() 

    # Re-open per usage or gather results and verify updates.
    # We'll batch connect for updates.

    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_img = {executor.submit(classify_task, img, dest_dir): img for img in images}
            
            for future in as_completed(future_to_img):
                if STOP_EVENT.is_set(): break
                while not PAUSE_EVENT.is_set() and not STOP_EVENT.is_set():
                    import time
                    time.sleep(0.5)

                db_entry, status_msg = future.result()
                processed_count += 1
                if db_entry: updates.append(db_entry)
                
                status_msg["progress"] = int((processed_count / total_images) * 100)
                status_msg["total"] = total_images
                status_msg["current"] = processed_count
                print(json.dumps(status_msg))
                sys.stdout.flush()
                
                if len(updates) >= 20:
                    update_db_batch(db_path, updates)
                    updates = []

        if updates:
            update_db_batch(db_path, updates)
            
    except Exception as e:
        print(json.dumps({"status": "error", "message": f"Batch Error: {e}"}))

    # Final Count
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM files WHERE type LIKE 'People%'")
        people_count = cursor.fetchone()[0]
        conn.close()
        print(json.dumps({"status": "completed", "people_count": people_count}))
    except:
        print(json.dumps({"status": "completed", "people_count": 0}))

def update_db_batch(db_path, updates):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.executemany("UPDATE files SET dest_path=?, processed=1, type=? WHERE id=?", updates)
        conn.commit()
        conn.close()
    except Exception as e:
        print(json.dumps({"status": "error", "message": f"DB Update failed: {e}"}))

# --- Service Mode ---
COMMAND_QUEUE = queue.Queue()

def input_listener():
    while True:
        try:
            line = sys.stdin.readline()
            if not line: break
            cmd = json.loads(line)
            action = cmd.get('action')
            
            if action == 'pause':
                PAUSE_EVENT.clear()
                print(json.dumps({"status": "paused"}))
                sys.stdout.flush()
            elif action == 'resume':
                PAUSE_EVENT.set()
                print(json.dumps({"status": "resumed"}))
                sys.stdout.flush()
            elif action == 'stop':
                STOP_EVENT.set()
                PAUSE_EVENT.set()
                print(json.dumps({"status": "stopped"}))
                sys.stdout.flush()
            elif action == 'classify':
                COMMAND_QUEUE.put(cmd)
            elif action == 'exit':
                os._exit(0)
        except: pass

def run_service_mode():
    load_models()
    threading.Thread(target=input_listener, daemon=True).start()
    
    while True:
        command = COMMAND_QUEUE.get()
        if command.get('action') == 'classify':
            STOP_EVENT.clear()
            PAUSE_EVENT.set()
            run_classification(command.get('dest'), command.get('db'))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('dest', nargs='?', help='Destination directory')
    parser.add_argument('db', nargs='?', help='Database file path')
    parser.add_argument('--mode', type=str, default='oneshot')
    args, unknown = parser.parse_known_args()
    
    try:
        if args.mode == 'service':
            run_service_mode()
        elif args.dest and args.db:
            run_classification(args.dest, args.db)
        else:
            print(json.dumps({"status": "error", "message": "Missing arguments"}))
    except Exception:
        pass
