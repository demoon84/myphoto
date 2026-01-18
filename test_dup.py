import os
import sys
import json
import sqlite3
import subprocess

# Set paths
project_root = "/Users/demoon/Documents/project/myphoto"
scanner_script = os.path.join(project_root, "backend", "scanner.py")
python_bin = os.path.join(project_root, "backend", "venv", "bin", "python3")
source_dir = "/Users/demoon/사진/dup_test"
dest_dir = "/Users/demoon/사진/dup_result"
db_path = os.path.join(dest_dir, "myphoto.db")

# Cleanup previous result
if os.path.exists(dest_dir):
    import shutil
    shutil.rmtree(dest_dir)
os.makedirs(dest_dir)

print(f"Running scanner on {source_dir}...")
# Running scanner.py source dest db
process = subprocess.Popen([python_bin, "-u", scanner_script, source_dir, dest_dir, db_path], 
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

for line in process.stdout:
    print(line.strip())

process.wait()

# Check results
print("\n--- RESULTS ---")
for root, dirs, files in os.walk(dest_dir):
    for file in files:
        if not file.endswith('.db'):
            rel_path = os.path.relpath(os.path.join(root, file), dest_dir)
            print(f"Organized: {rel_path}")

conn = sqlite3.connect(db_path)
count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
print(f"DB Records: {count}")
conn.close()
