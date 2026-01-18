import warnings
# Suppress urllib3 NotOpenSSLWarning
warnings.filterwarnings("ignore", message=".*NotOpenSSLWarning.*")

import os
import shutil
import sqlite3
import datetime
from PIL import Image
from PIL.ExifTags import TAGS
import json
import sys
import pillow_heif
import hashlib
import subprocess
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import queue

# Global state for duplicate tracking
HASH_LOCK = threading.Lock()
PROCESSED_HASHES = set()

# Register HEIF opener
pillow_heif.register_heif_opener()

# Supported image extensions
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.heic', '.webp', '.gif', '.bmp'}

def get_exif_date(file_path):
    # User Request: Prioritize EXIF "Content Creation Date" over File System "Creation Date".
    
    # Priority 1: EXIF Data (Content Created)
    try:
        img = Image.open(file_path)
        exif_data = img._getexif()
        if exif_data:
            # Create a dict for easier lookup
            exif = {TAGS.get(k, k): v for k, v in exif_data.items()}
            
            if 'DateTimeOriginal' in exif:
                return datetime.datetime.strptime(exif['DateTimeOriginal'], '%Y:%m:%d %H:%M:%S')
            if 'DateTimeDigitized' in exif:
                return datetime.datetime.strptime(exif['DateTimeDigitized'], '%Y:%m:%d %H:%M:%S')
            if 'DateTime' in exif:
                return datetime.datetime.strptime(exif['DateTime'], '%Y:%m:%d %H:%M:%S')
    except Exception:
        pass

    # Priority 2: File System Creation Time (macOS 'Created')
    # Use this if EXIF is missing.
    try:
        stat = os.stat(file_path)
        if hasattr(stat, 'st_birthtime') and stat.st_birthtime > 0:
            return datetime.datetime.fromtimestamp(stat.st_birthtime)
    except Exception:
        pass
        
    # Final Fallback: Modification Time
    mtime = os.path.getmtime(file_path)
    return datetime.datetime.fromtimestamp(mtime)

def calculate_file_hash(filepath):
    """Calculate MD5 hash of a file."""
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except:
        return None

def is_screenshot(file_path):
    """
    Determine if an image is a screenshot based on:
    1. Filename patterns
    2. Missing Camera EXIF (Model, Make)
    3. Software tags
    """
    filename = os.path.basename(file_path).lower()
    
    # 1. Filename Pattern Matching
    # Covers: Screenshot..., Screen Shot..., 스크린샷..., 화면 캡처...
    patterns = [
        r"screenshot", 
        r"screen shot", 
        r"스크린샷", 
        r"화면 캡처",
        r"screencast"
    ]
    if any(re.search(p, filename) for p in patterns):
        return True
        
    try:
        img = Image.open(file_path)
        exif_data = img._getexif()
        
        # 2. No EXIF data -> Very likely a screenshot (or downloaded image)
        if exif_data is None:
            # We can tentatively say yes, but let's be careful. 
            # Many screenshots have NO exif. Real photos usually have basic EXIF.
            return True
            
        exif = {TAGS.get(k, k): v for k, v in exif_data.items()}
        
        # 3. Check specific EXIF indicators
        # If 'Model' and 'Make' are missing, it's likely a screenshot
        has_camera_info = 'Model' in exif or 'Make' in exif
        
        if not has_camera_info:
            return True
            
        # 4. Check 'Software' tag
        software = exif.get('Software', '').lower()
        screenshot_indicators = ['screenshot', 'capture', 'ios', 'android', 'macos', 'windows']
        if any(ind in software for ind in screenshot_indicators):
            # But wait, 'iOS' is in real photos too (e.g. Software: iOS 17.0).
            # Real photos have 'Make': 'Apple'.
            # So if we have 'Software' but NO 'Model'/'Make' -> Screenshot.
            # We strictly checked `not has_camera_info` above.
            # If we HAVE camera info, it's a photo.
            if has_camera_info:
                return False
                
            return True
            
    except Exception:
        pass
        
    return False
def files_are_identical(p1, p2):
    """Check if two files are identical by size and hash."""
    try:
        if os.path.getsize(p1) != os.path.getsize(p2):
            return False
        return calculate_file_hash(p1) == calculate_file_hash(p2)
    except:
        return False

def copy_preserving_metadata(src, dst):
    """Copy file preserving all metadata including creation time (OS aware)."""
    try:
        if os.name == 'nt':
            # Windows: shutil.copy2 generally preserves creation time on modern Python
            shutil.copy2(src, dst)
        else:
            # macOS/Linux: Use cp -p to strictly preserve attributes including birthtime
            subprocess.run(["cp", "-p", src, dst], check=True)
    except Exception:
        # Fallback to python copy2 if subprocess fails
        try:
            shutil.copy2(src, dst)
        except Exception as e:
            print(json.dumps({"status": "error", "message": f"Copy failed: {e}"}))

def process_single_file(file_info, dest_dir, VIDEO_EXTS, IMAGE_EXTS):
    """Processes a single file and returns DB row data and status message."""
    file_path, file = file_info
    _, ext = os.path.splitext(file)
    ext = ext.lower()
    
    try:
        # 0. Calculate Hash for Duplicate Detection
        file_hash = calculate_file_hash(file_path)
        
        is_duplicate = False
        if file_hash:
            with HASH_LOCK:
                if file_hash in PROCESSED_HASHES:
                    is_duplicate = True
                else:
                    PROCESSED_HASHES.add(file_hash)

        # 1. Determine Type & Target Dir
        target_type = "unknown"
        target_dir = ""
        date_folder = "unknown"
        
        if is_duplicate:
            return None, {"status": "skipped", "file": file, "reason": "duplicate_content"}
        elif ext in VIDEO_EXTS:
            target_type = "video"
            target_dir = os.path.join(dest_dir, "Videos")
        elif ext in IMAGE_EXTS:
            if is_screenshot(file_path):
                target_type = "screenshot"
                dt = get_exif_date(file_path)
                date_folder = dt.strftime('%Y-%m')
                target_dir = os.path.join(dest_dir, "Screenshots", date_folder)
            else:
                target_type = "image"
                dt = get_exif_date(file_path)
                date_folder = dt.strftime('%Y-%m')
                target_dir = os.path.join(dest_dir, date_folder)
        else:
            target_type = "document"
            target_dir = os.path.join(dest_dir, "Documents")

        os.makedirs(target_dir, exist_ok=True)
        new_path = os.path.join(target_dir, file)

        # 2. Duplicate Check
        if os.path.exists(new_path) and files_are_identical(file_path, new_path):
            return None, {"status": "skipped", "file": file, "reason": "duplicate"}

        # 3. Collision Handling
        base, extension = os.path.splitext(file)
        counter = 1
        while os.path.exists(new_path):
            new_path = os.path.join(target_dir, f"{base}_{counter}{extension}")
            counter += 1

        # 4. Copy
        copy_preserving_metadata(file_path, new_path)
        
        # 5. Return DB record
        # processed=1 for duplicates, videos, documents, or screenshots to avoid AI processing
        processed = 1 if target_type in ['video', 'document', 'screenshot', 'duplicate', 'unknown'] else 0
        return (file_path, new_path, file, target_type, processed, date_folder if date_folder != "unknown" else None, file_hash), \
               {"status": "progress", "file": file, "type": target_type.capitalize()}

    except Exception as e:
        return None, {"status": "error", "message": f"Failed {file}: {str(e)}"}

# Control Flags
PAUSE_EVENT = threading.Event()
PAUSE_EVENT.set() # Set = Running, Cleared = Paused
STOP_EVENT = threading.Event()

def scan_and_organize(source_dir, dest_dir, db_path):
    # Command listener for pause/stop
    def command_listener():
        while True:
            line = sys.stdin.readline()
            if not line: break
            try:
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
                elif action == 'exit':
                    os._exit(0)
            except: pass

    listener_thread = threading.Thread(target=command_listener, daemon=True)
    listener_thread.start()

    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.heic', '.webp', '.bmp', '.tiff'}
    VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_path TEXT,
            dest_path TEXT,
            filename TEXT,
            type TEXT,
            processed INTEGER DEFAULT 0,
            cluster_id INTEGER DEFAULT -1,
            exif_date TEXT,
            hash TEXT
        )
    ''')
    conn.commit()

    # Reset and pre-populate hash tracking from destination
    print(json.dumps({"status": "progress", "file": "기존 파일 중복 검사 중...", "type": "System"}))
    with HASH_LOCK:
        PROCESSED_HASHES.clear()
        # Pre-scan destination tree for existing files to avoid re-organizing
        if os.path.exists(dest_dir):
            for root, _, files in os.walk(dest_dir):
                for f in files:
                    if f.lower().endswith(tuple(IMAGE_EXTS | VIDEO_EXTS)):
                        h = calculate_file_hash(os.path.join(root, f))
                        if h: PROCESSED_HASHES.add(h)

    file_list = []
    if os.path.isfile(source_dir):
        with open(source_dir, 'r', encoding='utf-8') as f:
            paths = json.load(f)
            file_list = [(p, os.path.basename(p)) for p in paths if os.path.exists(p)]
    else:
        for root, _, files in os.walk(source_dir):
            for file in files:
                if not file.startswith('.'):
                    file_list.append((os.path.join(root, file), file))
    
    total_files = len(file_list)
    print(json.dumps({"status": "started", "total": total_files}))
    sys.stdout.flush()
    
    # Use ThreadPool for I/O and non-GIL-blocked tasks
    results_to_insert = []
    new_images_count = 0
    max_workers = min(32, (os.cpu_count() or 1) * 4) 
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {executor.submit(process_single_file, f, dest_dir, VIDEO_EXTS, IMAGE_EXTS): f for f in file_list}
        
        for future in as_completed(future_to_file):
            if STOP_EVENT.is_set():
                break
            
            while not PAUSE_EVENT.is_set() and not STOP_EVENT.is_set():
                import time
                time.sleep(0.5)

            db_data, status_msg = future.result()
            if db_data:
                results_to_insert.append(db_data)
                # db_data[3] is target_type. Only 'image' needs AI processing.
                if db_data[3] == 'image':
                    new_images_count += 1
            
            # Print status and periodically commit
            print(json.dumps(status_msg))
            sys.stdout.flush()
            
            if len(results_to_insert) >= 100:
                cursor.executemany('''
                    INSERT INTO files (source_path, dest_path, filename, type, processed, exif_date, hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', results_to_insert)
                conn.commit()
                results_to_insert = []

    if results_to_insert:
        cursor.executemany('''
            INSERT INTO files (source_path, dest_path, filename, type, processed, exif_date, hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', results_to_insert)
        conn.commit()

    conn.close()
    print(json.dumps({"status": "completed", "new_images": new_images_count}))

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(json.dumps({"status": "error", "message": "Missing arguments"}))
        sys.exit(1)
    
    source = sys.argv[1]
    dest = sys.argv[2]
    db = sys.argv[3]
    
    try:
        scan_and_organize(source, dest, db)
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))
