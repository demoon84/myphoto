import sqlite3
import json
import sys
import os
import shutil
import numpy as np
from sklearn.cluster import DBSCAN
from deepface import DeepFace
import subprocess
import cv2
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

def read_image_safe(path):
    """Read image dealing with non-ASCII paths."""
    try:
        stream = open(path, "rb")
        bytes = bytearray(stream.read())
        numpy_array = np.asarray(bytes, dtype=np.uint8)
        img = cv2.imdecode(numpy_array, cv2.IMREAD_COLOR)
        return img
    except:
        return None

def move_preserving_metadata(src, dst):
    """Move file preserving metadata by using system 'mv' on Unix-like systems."""
    try:
        if os.name != 'nt':
            subprocess.run(["mv", src, dst], check=True)
        else:
            shutil.move(src, dst)
    except Exception:
        try:
            shutil.move(src, dst)
        except Exception:
            pass

# Suppress TensorFlow logs
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

def extract_embedding(img_data):
    """Worker task to extract embedding for a single image."""
    img_id, file_path, filename = img_data
    try:
        if not os.path.exists(file_path):
            return None
            
        img_arr = read_image_safe(file_path)
        if img_arr is None:
            return None

        embeddings_obj = DeepFace.represent(
            img_path=img_arr,
            model_name="Facenet512",
            detector_backend="opencv",
            enforce_detection=False
        )
        
        if embeddings_obj:
            # Pick largest face
            embeddings_obj.sort(key=lambda x: x['facial_area']['w'] * x['facial_area']['h'], reverse=True)
            embedding = embeddings_obj[0]["embedding"]
            return (img_id, file_path, filename, embedding)
            
    except Exception:
        pass
    return None

def run_face_clustering(dest_dir, db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, dest_path, filename FROM files WHERE type LIKE 'People' AND processed=1")
    people_images = cursor.fetchall()
    
    if not people_images:
        print(json.dumps({"status": "completed", "message": "No 'People' photos found."}))
        conn.close()
        return

    total = len(people_images)
    print(json.dumps({"status": "analyzing", "message": f"Analyzing {total} photos for faces (Parallel)..."}))
    sys.stdout.flush()

    encodings = []
    image_ids = []
    processed_count = 0
    
    # Parallel extraction
    max_workers = min(4, os.cpu_count() or 1)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_img = {executor.submit(extract_embedding, img): img for img in people_images}
        
        for future in as_completed(future_to_img):
            result = future.result()
            processed_count += 1
            if result:
                img_id, f_path, f_name, embedding = result
                encodings.append(embedding)
                image_ids.append((img_id, f_path, f_name))
            
            if processed_count % 5 == 0 or processed_count == total:
                print(json.dumps({
                    "status": "progress", 
                    "message": f"Extracting faces... {int(processed_count/total*100)}% ({processed_count}/{total})"
                }))
                sys.stdout.flush()

    if not encodings:
        print(json.dumps({"status": "completed", "message": "No faces detected."}))
        conn.close()
        return

    # Grouping
    print(json.dumps({"status": "clustering", "message": f"Grouping {len(encodings)} faces..."}))
    sys.stdout.flush()
    
    clt = DBSCAN(metric="cosine", n_jobs=-1, eps=0.30, min_samples=1)
    clt.fit(encodings)
    labels = clt.labels_
    
    unique_labels = set(labels)
    grouped_count = 0
    db_updates = []
    
    for label_id in unique_labels:
        if label_id == -1: continue
        cluster_name = f"People_{label_id + 1}"
        indices = np.where(labels == label_id)[0]
        
        for idx in indices:
            img_id, current_path, filename = image_ids[idx]
            target_dir = os.path.join(os.path.dirname(current_path), cluster_name)
            os.makedirs(target_dir, exist_ok=True)
            
            final_path = os.path.join(target_dir, filename)
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(final_path) and final_path != current_path:
                final_path = os.path.join(target_dir, f"{base}_{counter}{ext}")
                counter += 1
                
            if current_path != final_path:
                move_preserving_metadata(current_path, final_path)
                db_updates.append((final_path, img_id))
                grouped_count += 1

    if db_updates:
        cursor.executemany("UPDATE files SET dest_path=? WHERE id=?", db_updates)
        conn.commit()

    conn.close()
    print(json.dumps({
        "status": "completed", 
        "message": f"Clustering complete. {grouped_count} photos grouped into {len(unique_labels) - (1 if -1 in unique_labels else 0)} clusters."
    }))

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"status": "error", "message": "Missing arguments"}))
        sys.exit(1)
        
    dest = sys.argv[1]
    db = sys.argv[2]
    
    try:
        run_face_clustering(dest, db)
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))
