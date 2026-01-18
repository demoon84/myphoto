import os
import sys
import json
import tensorflow as tf

# Add backend to path to import classifier
sys.path.append(os.path.join(os.getcwd(), 'backend'))
import classifier

# Force Load Models
classifier.load_models()

test_suites = [
    {"path": "/Users/demoon/사진/sample", "name": "PEOPLE_SET", "expect": "People"},
    {"path": "/Users/demoon/사진/sample2", "name": "MIX_SET", "expect": "Mix"},
    {"path": "/Users/demoon/사진/sample3", "name": "FOOD_SET", "expect": "Food"},
    {"path": "/Users/demoon/사진/sample4", "name": "MISC_SET", "expect": "Misc"},
    {"path": "/Users/demoon/사진/sample5", "name": "ERROR_SET", "expect": "Error"}
]

total_fails = 0

print("=== STARTING COMPREHENSIVE CLASSIFICATION TEST ===")

for suite in test_suites:
    folder = suite["path"]
    if not os.path.exists(folder):
        print(f"Skipping {folder} (Not found)")
        continue
        
    print(f"\n--- Testing {suite['name']} ({folder}) ---")
    files = [f for f in os.listdir(folder) if not f.startswith('.')]
    
    results = {"People": 0, "Food": 0, "Misc": 0, "Error": 0}
    files_processed = 0
    
    for filename in files:
        path = os.path.join(folder, filename)
        if os.path.isdir(path): continue
        files_processed += 1
        
        try:
            category = classifier.classify_image(path)
            results[category] = results.get(category, 0) + 1
            
            # Detailed Failure Logging based on expectation
            is_fail = False
            if suite["expect"] == "People" and category != "People": is_fail = True
            elif suite["expect"] == "Food" and category != "Food": is_fail = True
            elif suite["expect"] == "Misc" and category != "Misc": is_fail = True
            elif suite["expect"] == "Error" and category != "Error" and category != "Misc": pass 
            
            # Get internal score for debugging (quick hack: re-run logic or just use global if available? 
            # Since we can't easily get internals from classify_image_tf return value, 
            # let's just accept we need to inspect manually or rely on general knowledge.
            # OR, we can modify verify logic to just print filename if fail.
            # Actually, let's try to get info if possible. classifier.py doesn't return score.
            # We will just print the filename.
            
            if is_fail:
                 print(f"[{category}] {filename} [FAIL]")
            elif suite["expect"] == "Mix":
                 print(f"[{category}] {filename}")
                 
        except Exception as e:
            print(f"[CRASH] {filename}: {e}")
            results["Error"] += 1

    print(f"SUMMARY {suite['name']}: {results}")
    
    # Check Pass/Fail
    is_pass = True
    if suite["expect"] == "People":
        # Allow small margin of error (e.g., blurred faces)
        if results["People"] < files_processed * 0.9: 
            is_pass = False
    elif suite["expect"] == "Food":
        if results["Food"] != files_processed:
            is_pass = False
    elif suite["expect"] == "Misc":
        if results["Misc"] != files_processed:
            is_pass = False
    elif suite["expect"] == "Error":
        # Error files should be Error or Misc (handled safely)
        if results["People"] > 0 or results["Food"] > 0:
            is_pass = False

    if not is_pass:
        print(f"❌ TEST FAILED: {suite['name']}")
        total_fails += 1
    else:
        print(f"✅ TEST PASSED: {suite['name']}")

print(f"\n=== FINAL RESULT: {total_fails} Suites Failed ===")
if total_fails == 0:
    print("ALL TESTS PASSED!")
    sys.exit(0)
else:
    sys.exit(1)
