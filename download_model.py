import tensorflow as tf
import tensorflow_hub as hub
import os
import requests

URL = "https://tfhub.dev/google/imagenet/mobilenet_v3_small_100_224/classification/5"
DEST = os.path.abspath(os.path.join(os.getcwd(), 'backend', 'models', 'mobilenet_v3'))

print(f"Downloading model to {DEST}...")
os.makedirs(DEST, exist_ok=True)

# Load from Hub (this will download or use cache)
model = hub.load(URL)

# Save as SavedModel
tf.saved_model.save(model, DEST)
print("Model saved.")

# Download Labels
LABELS_URL = "https://storage.googleapis.com/download.tensorflow.org/data/ImageNetLabels.txt"
LABELS_DEST = os.path.join(os.getcwd(), 'backend', 'models', 'ImageNetLabels.txt')

print(f"Downloading labels to {LABELS_DEST}...")
r = requests.get(LABELS_URL)
with open(LABELS_DEST, 'wb') as f:
    f.write(r.content)
print("Labels saved.")
