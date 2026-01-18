import os
import sys
import json
import sqlite3
import shutil
import subprocess

# Set paths
project_root = "/Users/demoon/Documents/project/myphoto"
scanner_script = os.path.join(project_root, "backend", "scanner.py")
python_bin = os.path.join(project_root, "backend", "venv", "bin", "python3")

source_dir = "/Users/demoon/사진/re_run_test"
dest_dir = "/Users/demoon/사진/re_run_dest"

if os.path.exists(source_dir): shutil.rmtree(source_dir)
if os.path.exists(dest_dir): shutil.rmtree(dest_dir)

os.makedirs(source_dir)
os.makedirs(dest_dir)

# 1. Start with one file
sample_file = "/Users/demoon/사진/sample/1 (1).JPG"
shutil.copy2(sample_file, os.path.join(source_dir, "test.jpg"))

db_path = os.path.join(dest_dir, "myphoto.db")

print("--- RUN 1: Organize ---")
subprocess.run([python_bin, "-u", scanner_script, source_dir, dest_dir, db_path], check=True)

# Manually "categorize" it like AI would
date_folder = os.listdir(dest_dir)[0] # e.g. 2018-07
if date_folder == "myphoto.db": date_folder = os.listdir(dest_dir)[1]

cat_dir = os.path.join(dest_dir, date_folder, "People")
os.makedirs(cat_dir)
shutil.move(os.path.join(dest_dir, date_folder, "test.jpg"), os.path.join(cat_dir, "test.jpg"))

print(f"File moved to {cat_dir}/test.jpg")

# 2. RUN 2: Same source
print("\n--- RUN 2: Organize Again ---")
# Reset DB (like App.tsx does)
if os.path.exists(db_path): os.remove(db_path)

result = subprocess.run([python_bin, "-u", scanner_script, source_dir, dest_dir, db_path], 
                      stdout=subprocess.PIPE, text=True)
print(result.stdout)

# Check if a new file was created in the date folder
organized_files = []
for root, dirs, files in os.walk(dest_dir):
    for f in files:
        if f.endswith('.jpg'):
            rel = os.path.relpath(os.path.join(root, f), dest_dir)
            organized_files.append(rel)

print(f"Organized files: {organized_files}")
if any("test.jpg" in f and not "People" in f for f in organized_files):
    print("FAILURE: Duplicate created in date folder!")
else:
    print("SUCCESS: Duplicate skipped based on global hash!")

# 3. Test _1 creation for different files
print("\n--- RUN 3: Different file with same name ---")
# Use a different sample
diff_sample = "/Users/demoon/사진/sample/1 (2).JPG"
shutil.copy2(diff_sample, os.path.join(source_dir, "test.jpg"))

result = subprocess.run([python_bin, "-u", scanner_script, source_dir, dest_dir, db_path], 
                      stdout=subprocess.PIPE, text=True)
print(result.stdout)

organized_files = []
for root, dirs, files in os.walk(dest_dir):
    for f in files:
        if f.endswith('.jpg'):
            rel = os.path.relpath(os.path.join(root, f), dest_dir)
            organized_files.append(rel)
print(f"Organized files after diff: {organized_files}")
