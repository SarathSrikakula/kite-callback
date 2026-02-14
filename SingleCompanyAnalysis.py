import numpy as np
import os
import pytesseract
import re
from PIL import Image

# ==========================================
# GLOBAL VARIABLES (Original Names & Comments)
# ==========================================


# Define local variables for the getting company boundaries
top_y = 160
bottom_y = 200
left_x = 560
right_x = 700

darkpurple = (94, 66, 129);
toleranceForAnyColor = 20  # the mark we put inorder to find we need to give tolerance for r,g,b
# Pixel position (x, y)
red_thresholds = {
    "min_r": 201,
    "max_g": 199,
    "max_b": 199
}
green_thresholds = {
    "min_r": 100,
    "max_g": 120,
    "max_b": 100
}
x, y = 1660, 750  # Pixel position fixed to start from bottom
upto = 570  # go up to what lenth?
# Note: startFromLeft is defined inside the function as it depends on img width
oneMoreStaringFromLeft = 50;  # how much region we need to exclude to the left of the image
blackLineLower = [197, 197, 197];  # boundaries used to find the vertical black line used for horizantal
blackLineUpper = [228, 228, 228];
distanceFromBlackLine = 6;  # used to fine x left co-ordinate

yTopAndBottomLimit = 15;  # from center to how much above and below to determine y co-ordinates
target_y = 300  # Example input

# Set Tesseract Command
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def leftToRight(px_max, py, pixel_data, startFromLeft):
    """Starting from px_max, moves left to x=0 at the constant height py."""
    pass  # Keeping logic consistent with your original empty/commented loop


def group_coordinates(coords, threshold=10):
    if not coords: return []
    groups = []
    current_group = [coords[0]]
    for i in range(1, len(coords)):
        if abs(coords[i][1] - coords[i - 1][1]) <= threshold:
            current_group.append(coords[i])
        else:
            groups.append(current_group)
            current_group = [coords[i]]
    groups.append(current_group)
    return groups


def visualize_groups(pixel_data, groups):
    i = 10
    for group in groups:
        color = [10 + i, 10 + i, 10 + i]
        i += 25
        # logic for visualization if needed


def get_vertical_centers(groups):
    centers = []
    for group in groups:
        if not group: continue
        mid_idx = len(group) // 2
        centers.append(group[mid_idx])
    return centers


def visualize_y_centers(pixel_data, centers):
    for cx, cy in centers:
        pixel_data[cy - yTopAndBottomLimit:cy + yTopAndBottomLimit, cx] = [255, 255, 0]


def find_all_right_extremes(pixel_data, centers, diff_threshold=10):
    img_width = pixel_data.shape[1]
    white = [255, 255, 255]
    best_overall_x = 0
    for idx, (start_x, target_y_val) in enumerate(centers):
        current_extreme_x = start_x
        for x_scan in range(start_x, img_width - oneMoreStaringFromLeft):
            if pixel_data[target_y_val, x_scan].tolist() != white:
                current_extreme_x = x_scan
        if (current_extreme_x - start_x) > diff_threshold:
            if current_extreme_x > best_overall_x:
                best_overall_x = current_extreme_x
    return {}, best_overall_x


def find_black_vertical_boundary(pixel_data, centers, y_span=30):
    if not centers: return None
    mid_idx = len(centers) // 2
    start_x, t_y = centers[mid_idx]
    for current_x in range(start_x, -1, -1):
        y_top, y_bot = t_y - y_span, t_y + y_span
        if y_top < 0 or y_bot >= pixel_data.shape[0]: continue
        vertical_slice = pixel_data[y_top: y_bot + 1, current_x]
        is_in_range = (vertical_slice >= blackLineLower) & (vertical_slice <= blackLineUpper)
        if np.all(is_in_range):
            pixel_data[t_y - 30:t_y + 30, current_x + distanceFromBlackLine] = [0, 255, 0]
            return current_x + distanceFromBlackLine
    return None


def process_ocr_segments(original_img, left_x_val, right_x_val, y_centers):
    results = []
    lx = left_x_val[0] if isinstance(left_x_val, tuple) else left_x_val
    for y_mid in y_centers:
        crop_box = (lx, y_mid - 15, right_x_val, y_mid + 15)
        crop_img = original_img.crop(crop_box)
        raw_text = pytesseract.image_to_string(crop_img, config='--psm 7 digits').strip()
        try:
            number = int(''.join(filter(str.isdigit, raw_text)))
            results.append({"y": y_mid, "num": number})
        except ValueError:
            continue
    if not results: return []
    all_nums = [r["num"] for r in results]
    median_val = np.median(all_nums)
    return [r for r in results if abs(r["num"] - median_val) < (median_val * 0.5)]


def format_implied_decimals(ocr_results):
    formatted_data = []
    for entry in ocr_results:
        raw_digits = ''.join(filter(str.isdigit, str(entry['num'])))
        if not raw_digits: continue
        if len(raw_digits) > 2:
            val = raw_digits[:-2] + '.' + raw_digits[-2:]
        elif len(raw_digits) == 2:
            val = "0." + raw_digits
        else:
            val = "0.0" + raw_digits
        formatted_data.append({"y": entry['y'], "num": float(val)})
    return formatted_data


def clean_and_calculate_price(target_y_val, formatted_data):
    batch = sorted(formatted_data, key=lambda i: i['y'])
    if not batch: return 0.0
    if target_y_val > batch[0]['y']:
        p1, p2 = batch[0], batch[1]
    elif target_y_val < batch[-1]['y']:
        p1, p2 = batch[-2], batch[-1]
    else:
        ys, prices = [i['y'] for i in batch], [i['num'] for i in batch]
        return round(float(np.interp(target_y_val, ys, prices)), 2)
    slope = (p2['num'] - p1['num']) / (p2['y'] - p1['y'])
    return round(float(p1['num'] + (target_y_val - p1['y']) * slope), 2)


def get_red_midpoint(red_coords):
    if not red_coords: return None
    y_vals = [c[1] for c in red_coords]
    return (min(y_vals) + max(y_vals)) // 2


def find_purple_y_coordinates_loop(pixel_data, target_rgb, tolerance=20):
    rows, cols = pixel_data.shape[0], pixel_data.shape[1]
    found_ys = set()
    tr, tg, tb = target_rgb
    for py in range(rows):
        for px in range(cols):
            r, g, b = pixel_data[py, px]
            if (abs(int(r) - tr) <= tolerance and abs(int(g) - tg) <= tolerance and abs(int(b) - tb) <= tolerance):
                found_ys.add(py);
                break
    return sorted(list(found_ys))


def process_purple_marker(purple_ys, pixel_data):
    if not purple_ys: return None
    mid_y = (purple_ys[0] + purple_ys[-1]) // 2
    pixel_data[mid_y, :] = [20, 255, 150]
    return mid_y


def get_text_from_boundaries(pixel_data, y_start, y_end, x_start, x_end):
    snip = pixel_data[y_start:y_end, x_start:x_end]
    if snip.size == 0: return ""
    temp_img = Image.fromarray(snip.astype('uint8'), 'RGB')
    return pytesseract.image_to_string(temp_img, config='--psm 7').strip()


def clean_ocr_label(text):
    if not text: return ""
    clean_text = re.sub(r'[“”"\'‘’]', '', text)
    clean_text = re.sub(r'\s*\d+$', '', clean_text)
    return clean_text.strip()


# ==========================================
# MAIN EXECUTION PIPELINE
# ==========================================

def run_analysis_pipeline(input_path):
    # 1. Image Initialization
    img = Image.open(input_path).convert("RGB")
    pixels = np.array(img)
    startFromLeft = img.width - 60  # how much region we need to exclude

    # 2. Scanning Upwards
    path_coordinates, red_coordinates = [], []
    target_red_color = [255, 0, 0]

    for i in range(y, y - upto, -1):
        r, g, b = pixels[i, x]
        if ((r >= red_thresholds["min_r"] and g <= red_thresholds["max_g"] and b <= red_thresholds["max_b"]) or (
                r <= green_thresholds["min_r"] and g >= green_thresholds["max_g"] and b <= green_thresholds["max_b"])):
            red_coordinates.append((x, i))
            pixels[i, x - 4: x + 5] = [255, 255, 0]

        if [r, g, b] == [255, 255, 255]: continue

        leftToRight(x, i, pixels, startFromLeft)
        path_coordinates.append((x, i))

    # 3. Processing Groups and Boundaries
    res_groups = group_coordinates(path_coordinates)
    visualize_groups(pixels, res_groups)
    centers = get_vertical_centers(res_groups)
    visualize_y_centers(pixels, centers)
    y_only_arr = [c[1] for c in centers]

    _, best_xRight_val = find_all_right_extremes(pixels, centers)
    leftX_val = find_black_vertical_boundary(pixels, centers)

    # 4. OCR and Price Logic
    f_data = process_ocr_segments(img, leftX_val, best_xRight_val, y_only_arr)
    formatted_f_data = format_implied_decimals(f_data)

    # 5. Result Calculations
    red_mid_y = get_red_midpoint(red_coordinates)
    currentPrice_val = clean_and_calculate_price(red_mid_y, formatted_f_data)

    try:
        purp_ys = find_purple_y_coordinates_loop(pixels, darkpurple, toleranceForAnyColor)
        mid_purp_y = process_purple_marker(purp_ys, pixels)
        dottedPrice_val = clean_and_calculate_price(mid_purp_y, formatted_f_data)
    except Exception as e:
        dottedPrice_val = 0;
        print(f"Dotted Error for: {e}")

    # 6. Name Extraction
    raw_name = get_text_from_boundaries(pixels, top_y, bottom_y, left_x, right_x)
    processed_name_val = clean_ocr_label(raw_name)

    # 7. Final Visual Polish
    if best_xRight_val > 0:
        pixels[:, best_xRight_val] = [0, 255, 255]

    # Save output for review
    Image.fromarray(pixels).save("output_final.png")

    return currentPrice_val, processed_name_val, dottedPrice_val


# ==========================================
# TRIGGER
# ==========================================

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    image_path = os.path.join(base_dir, "img.jpeg")#test image
    # Call the main pipeline with the global image_path
    cur_p, name, dot_p = run_analysis_pipeline(image_path)

    print(f"\n--- Processed Results ---")
    print(f"Company Name: {name}")
    print(f"Current Price: {cur_p}")
    print(f"Dotted Price:  {dot_p}")