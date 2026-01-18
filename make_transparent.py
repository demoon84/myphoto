from PIL import Image


def make_transparent(input_path, output_path):
    print(f"Processing {input_path}...")
    try:
        img = Image.open(input_path).convert("RGBA")
        datas = img.getdata()

        newData = []
        # Threshold for white background removal
        threshold = 240 

        for item in datas:
            # item is (R, G, B, A)
            if item[0] > threshold and item[1] > threshold and item[2] > threshold:
                newData.append((255, 255, 255, 0)) # Transparent
            else:
                newData.append(item)

        img.putdata(newData)
        
        # Crop to content
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
            print(f"Cropped to {bbox}")
            
        img.save(output_path, "PNG")
        print(f"Successfully saved transparent & cropped icon to {output_path}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Process both the app icon and the main logo
    make_transparent("src/renderer/src/assets/logo.png", "src/renderer/src/assets/logo.png")
