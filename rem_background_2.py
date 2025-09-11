from PIL import Image

# Open the uploaded image
img_path = "e08c690b-4ec8-4f81-97a5-7ae222282447.png"
img = Image.open(img_path).convert("RGBA")

# Remove white background by making it transparent
datas = img.getdata()
new_data = []
for item in datas:
    # Detect white (or near-white) pixels and make them transparent
    if item[0] > 200 and item[1] > 200 and item[2] > 200:
        new_data.append((255, 255, 255, 0))
    else:
        new_data.append(item)

img.putdata(new_data)

# Save as transparent PNG for icon use
output_path = "ai_icon_transparent.png"
img.save(output_path, "PNG")

output_path
