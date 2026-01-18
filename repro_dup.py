import os
import sys
import json
import sqlite3
import shutil
import subprocess

# Set paths
project_root = "/Users/demoon/Documents/project/myphoto"
classifier_script = os.path.join(project_root, "backend", "classifier.py")
python_bin = os.path.join(project_root, "backend", "venv", "bin", "python3")

dest_dir = "/Users/demoon/사진/dup_test_ai"
if os.path.exists(dest_dir):
    shutil.rmtree(dest_dir)
os.makedirs(dest_dir)

# Create a "Date folder" file
date_dir = os.path.join(dest_dir, "2024-01")
os.makedirs(date_dir)
sample_file = "/Users/demoon/사진/sample/1 (1).JPG"
current_file = os.path.join(date_dir, "test.jpg")
shutil.copy2(sample_file, current_file)

# Create an existing "Category folder" file (identical)
cat_dir = os.path.join(date_dir, "People")
os.makedirs(cat_dir)
final_file = os.path.join(cat_dir, "test.jpg")
shutil.copy2(sample_file, final_file)

print(f"Current file exists: {os.path.exists(current_file)}")
print(f"Final file exists: {os.path.exists(final_file)}")

# Now run the classifier logic (using oneshot for testing)
# We need a dummy DB
db_path = os.path.join(dest_dir, "test.db")
conn = sqlite3.connect(db_path)
conn.execute("CREATE TABLE files (id INTEGER PRIMARY KEY, dest_path TEXT, filename TEXT, exif_date TEXT, type TEXT, processed INTEGER)")
conn.execute("INSERT INTO files (dest_path, filename, exif_date, type, processed) VALUES (?, ?, ?, ?, ?)", 
             (current_file, "test.jpg", "2024-01", "image", 0))
conn.commit()
conn.close()

print("\n--- Running Classifier ---")
# python3 classifier.py dest db
subprocess.run([python_bin, classifier_script, dest_dir, db_path], check=True)

print("\n--- After Classification ---")
print(f"Original Date Folder file exists: {os.path.exists(current_file)} (Should be False if identical)")
print(f"Category folder 'test.jpg' exists: {os.path.exists(os.path.join(cat_dir, 'test.jpg'))}")
print(f"Category folder 'test_1.jpg' exists: {os.path.exists(os.path.join(cat_dir, 'test_1.jpg'))} (Should be False)")

# Check files in cat_dir
print(f"Files in {cat_dir}: {os.listdir(cat_dir)}")
