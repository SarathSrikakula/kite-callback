
#####these above_count and below_count will check no of dots in graph before processing and also check Successful_Alerts before adding to excel
#Also TradingResults_Prices doesn't append duplicate data to Successful_Alerts
import os
FORCE_SAVE_ON_KITE_ERROR=True# this condition is used to save to Successful_Alerts even if alert fail so i can manually add it

above_count = 2  #  (used for alerts and in the graph as well)how many times a company from above the current price we will accept the count
below_count = 2  # (used for alerts and in the graph as well)how many times a company from below the current price we will accept the count
append_flag = False;  # when false append for TradingResults_Prices,(currently in append mode). Also TradingResults_Prices doesn't append duplicate data
#whatever there is
files_to_wipe = [
    # always in append mode no flag for it
    # "Successful_Alerts.csv", #when kite api gives success then it will add or just read it

    # always in append mode no flag for it
    "CurrentCompanies.csv",  # for magenta it will add the companies
    "TradingResults_Prices.csv",#append_flag. when false append for TradingResults_Prices,TradingResults_Prices(currently in append mode)
    # "TradingResults_Logs.csv",#append_flag. when false append for TradingResults_Prices,TradingResults_Prices(currently in append mode)
    "FailedAlerts.csv"
]


def wipe_files_completely():
    """
    Completely empties the specified files.
    Result: 0 KB files with no headers.
    """

    for file_name in files_to_wipe:
        try:
            # Opening in 'w' mode and immediately closing wipes the file
            open(file_name, 'w').close()
            print(f"Emptying: {file_name}... Done.")
        except Exception as e:
            print(f"Error wiping {file_name}: {e}")


# Call the function to clear them now
wipe_files_completely()

import numpy as np
import os
import pytesseract
import re
import shutil
import csv
from PIL import Image
import requests

# clear CurrentCompanies.csv by yourself
# clear Successful_ALerts by yourself
# clear Successful_ALerts by yourself
# clear TradingResults_Prices.csv by yourself


# --- Kite Configuration ---
API_KEY = '6ra48xexz4hvmalc'
ACCESS_TOKEN = '4g1ywEsE10YeQplWgFYlbiB3f1avLyrG'
KITE_URL = "https://api.kite.trade/alerts"
ALERT_DB_CSV = "Successful_Alerts.csv"  # Our local database
FailedAlerts="FailedAlerts.csv"
CurrentCompany = "CurrentCompanies.csv"  # Our local database

# ==========================================
# GLOBAL VARIABLES (Original Names & Comments)
# ==========================================
base_dir = os.path.dirname(os.path.abspath(__file__))

append_Alerts = True;
top_y = 265
bottom_y = 305
left_x = 600
right_x = 740

darkpurple = (91, 49, 141);
toleranceForAnyColor = 13  # the mark we put inorder to find we need to give tolerance for r,g,b
red_thresholds = {"min_r": 201, "max_g": 199, "max_b": 199}
green_thresholds = {"min_r": 100, "max_g": 120, "max_b": 100}

#1800, 900
#1660,750
x, y = 1800, 900  # Pixel position fixed to start from bottom
upto = 570  # go up to what lenth?
# Note: startFromLeft is defined inside the function as it depends on img width
#62
#50
oneMoreStaringFromLeft = 62;  # how much region we need to exclude to the left of the image
blackLineLower = [197, 197, 197]  # boundaries used to find the vertical black line used for horizantal
blackLineUpper = [228, 228, 228]
#1190
#6
distanceFromBlackLine = 1190; # used to fine x left co-ordinate
yTopAndBottomLimit = 15  # from center to how much above and below to determine y co-ordinates
target_y = 300  # Example input

# Set Tesseract Command
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def leftToRight(px_max, py, pixel_data, startFromLeft):
    pass


def group_coordinates(coords, threshold=10):
    if not coords: return []
    groups, current_group = [], [coords[0]]
    for i in range(1, len(coords)):
        if abs(coords[i][1] - coords[i - 1][1]) <= threshold:
            current_group.append(coords[i])
        else:
            groups.append(current_group)
            current_group = [coords[i]]
    groups.append(current_group)
    return groups


def visualize_groups(pixel_data, groups):
    pass


def get_vertical_centers(groups):
    return [group[len(group) // 2] for group in groups if group]


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
            return current_x + distanceFromBlackLine
    return None


def process_ocr_segments(original_img, left_x_val, right_x_val, y_centers):
    results = []
    lx = left_x_val[0] if isinstance(left_x_val, tuple) else left_x_val
    for y_mid in y_centers:
        crop_box = (lx, y_mid - 15, right_x_val, y_mid + 15)
        raw_text = pytesseract.image_to_string(original_img.crop(crop_box), config='--psm 7 digits').strip()
        try:
            number = int(''.join(filter(str.isdigit, raw_text)))
            results.append({"y": y_mid, "num": number})
        except ValueError:
            continue
    if not results: return []
    median_val = np.median([r["num"] for r in results])
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


def process_purple_markers(purple_ys, gap_threshold=1):
    """
    Groups y-coordinates into clusters and returns midpoints for each.
    gap_threshold: minimum distance between two separate dotted lines.
    """
    if not purple_ys: return []

    clusters = []
    if purple_ys:
        current_cluster = [purple_ys[0]]
        for i in range(1, len(purple_ys)):
            if purple_ys[i] - purple_ys[i - 1] <= gap_threshold:
                current_cluster.append(purple_ys[i])
            else:
                clusters.append(current_cluster)
                current_cluster = [purple_ys[i]]
                current_group = [purple_ys[i]]
        clusters.append(current_cluster)

    # Calculate midpoints for each identified cluster
    mid_points = [(c[0] + c[-1]) // 2 for c in clusters]
    return mid_points


def get_text_from_boundaries(pixel_data, y_start, y_end, x_start, x_end):
    snip = pixel_data[y_start:y_end, x_start:x_end]
    if snip.size == 0: return ""
    return pytesseract.image_to_string(Image.fromarray(snip.astype('uint8'), 'RGB'), config='--psm 7').strip()


def clean_ocr_label(text):
    if not text: return ""

    # 1. First, keep only the first word (splits at the first space)
    # This prevents junk text after the symbol from being processed
    first_word = text.split(' ')[0]

    # 2. Remove ANY character that is NOT an alphabet (a-z, A-Z) or a number (0-9)
    # This removes symbols like |, @, #, $, quotes, and dots
    clean_text = re.sub(r'[^a-zA-Z0-9]', '', first_word)

    # 3. Final strip to be safe
    return clean_text.strip()


# ==========================================
# NATIVE CSV TRACKER (Replaces Pandas/Openpyxl)
# ==========================================

class NativeResultTracker:
    def __init__(self, append_flag=True):
        self.results = []
        self.col1 = []
        self.col2 = []
        self.logs = []
        self.failed_alerts = []
        # Load existing alerts into a set for fast searching
        self.existing_alerts = self._load_alert_history()

    def _add_to_history_set(self, history_set, row):
        """Helper to ensure ID formatting is identical to trigger_kite_alerts"""
        if len(row) >= 3:
            sym = str(row[0]).strip().upper()
            op = str(row[1]).strip()
            # Ensure 2-decimal formatting so "99.08" matches "99.08"
            price = "{:.2f}".format(float(row[2]))
            history_set.add(f"{sym}_{op}_{price}")

    def _load_alert_history(self):
        history = set()
        if os.path.exists(ALERT_DB_CSV):
            with open(ALERT_DB_CSV, 'r') as f:
                reader = csv.reader(f)
                first_row = next(reader, None)

                # If file is empty, return
                if first_row is None:
                    return history

                # --- SMART CHECK ---
                # If the first row is NOT a header, process it as data
                if first_row[0].strip().upper() != "SYMBOL":
                    self._add_to_history_set(history, first_row)
                for row in reader:
                    if len(row) >= 3:
                        # CLEANING: Ensure history keys are stripped and consistent
                        symbol = str(row[0]).strip().upper()
                        op = str(row[1]).strip()
                        # Force price to 2 decimal string
                        price = "{:.2f}".format(float(row[2]))
                        history.add(f"{symbol}_{op}_{price}")
        else:
            with open(ALERT_DB_CSV, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Symbol", "Operator", "Target_Price"])
        return history

    def add_result(self, name, cur_p, dot_p):
        self.results.append({'name': name, 'cur_p': cur_p, 'dot_p': dot_p})
        self.logs.append([f"Asset: {name} | Price: {cur_p} | Dotted: {dot_p}"])
        if dot_p > cur_p:
            self.col1.extend([dot_p, name])
        else:
            self.col2.extend([dot_p, name])

    def trigger_kite_alerts(self):
        headers = {
            "X-Kite-Version": "3",
            "Authorization": f"token {API_KEY}:{ACCESS_TOKEN}"
        }

        for res in self.results:
            clean_name = clean_ocr_label(str(res['name']).strip().upper())
            cur_p = float(res['cur_p'])
            dot_p = float(res['dot_p'])

            # Determine direction
            operator = ">=" if dot_p > cur_p else "<="
            is_above = dot_p > cur_p

            # --- THE DIRECTIONAL CHECK ---
            # 1. Get all existing history for THIS symbol only
            symbol_history = [id for id in self.existing_alerts if id.startswith(clean_name + "_")]

            # 2. Count how many are already Above and how many are Below
            # Format in existing_alerts is: SYMBOL_OPERATOR_PRICE
            count_above = sum(1 for id in symbol_history if ">=" in id)
            count_below = sum(1 for id in symbol_history if "<=" in id)

            # 3. Apply the 2+2 Limit
            if is_above and count_above >= above_count:
                print(f"🛑 LIMIT: {clean_name} already has {count_above} alerts ABOVE. Skipping {dot_p}.")
                continue
            if not is_above and count_below >= below_count:
                print(f"🛑 LIMIT: {clean_name} already has {count_below} alerts BELOW. Skipping {dot_p}.")
                continue

            # CHECK IF ALERT ALREADY EXISTS
            # --- DUPLICATE PRICE CHECK ---
            price_str = "{:.2f}".format(dot_p)
            alert_id = f"{clean_name}_{operator}_{price_str}"
            if alert_id in self.existing_alerts:
                print(f"SKIPPED: {res['name']} {operator} {res['dot_p']} (Already exists)")
                continue

            payload = {
                "name": clean_name,
                "lhs_exchange": "NSE",
                "lhs_tradingsymbol": clean_name,
                "lhs_attribute": "LastTradedPrice",
                "operator": operator,
                "rhs_type": "constant",
                "rhs_constant": str(res['dot_p'])
            }

            try:
                response = requests.post(KITE_URL, headers=headers, data=payload)
                if response.json().get("status") == "success":
                    print(f"SUCCESS: Alert added for {clean_name}")
                    # Save to DB so we don't repeat next time
                    with open(ALERT_DB_CSV, 'a', newline='') as f:
                        csv.writer(f).writerow([clean_name, operator, res['dot_p']])
                else:
                    self.failed_alerts.append(
                        f" | Kite Error: {clean_name} dotted price {res['dot_p']} Error for {response.json().get('message')}")
                    if FORCE_SAVE_ON_KITE_ERROR:
                        print(f"⚠️ Flag Active: Saving {clean_name} to DB anyway despite Kite failure.")
                        with open(ALERT_DB_CSV, 'a', newline='') as f:
                            csv.writer(f).writerow([clean_name, operator, res['dot_p']])
                        with open(FailedAlerts, 'a', newline='') as f:
                            csv.writer(f).writerow([clean_name, operator, res['dot_p']])
            except Exception as e:
                self.failed_alerts.append(f"{clean_name} | System Error: {str(e)}")

    # i think below function is not used
    def save_results(self, filename="TradingResults.csv"):
        # Use 'a' if append_flag is True, otherwise 'w'
        mode = 'a' if self.append_flag else 'w'

        with open(filename, mode, newline='') as f:
            writer = csv.writer(f)
            # Write column values (simplified for your col1/col2 logic)
            max_len = max(len(self.col1), len(self.col2))
            for i in range(max_len):
                v1 = self.col1[i] if i < len(self.col1) else ""
                v2 = self.col2[i] if i < len(self.col2) else ""
                writer.writerow([v1, v2])

    def print_final_report(self):
        if self.failed_alerts:
            print("\n" + "=" * 50)
            print("ALERT FAILURE SUMMARY:")
            for item in self.failed_alerts:
                print(f"❌ {item}")
            print("=" * 50 + "\n")
        else:
            print("\n✅ All alerts were synced to Zerodha successfully!")

    def save_results(self, base_dir, override=False):
        price_file = os.path.join(base_dir, "TradingResults_Prices.csv")
        log_file = os.path.join(base_dir, "TradingResults_Logs.csv")
        mode = 'w' if override else 'a'

        # Write Prices
        max_len = max(len(self.col1), len(self.col2))
        with open(price_file, mode, newline='') as f:
            writer = csv.writer(f)
            for i in range(max_len):
                v1 = self.col1[i] if i < len(self.col1) else ""
                v2 = self.col2[i] if i < len(self.col2) else ""
                writer.writerow([v1, v2])

        # Write Logs
        with open(log_file, mode, newline='') as f:
            writer = csv.writer(f)
            writer.writerows(self.logs)
        print(f"Results saved to CSV in {base_dir}")

    def check_magenta_requirement(self, pixel_data, imageName):
        """NEW: Checks for Magenta color and skips if found."""
        target = (208, 27, 125)
        # Scan pixels for exact or near match
        raw_name = get_text_from_boundaries(pixel_data, top_y, bottom_y, left_x, right_x)
        processed_name_val = clean_ocr_label(raw_name)
        found = False
        for row in pixel_data:
            for p in row:
                if (abs(int(p[0]) - target[0]) < toleranceForAnyColor and
                        abs(int(p[1]) - target[1]) < toleranceForAnyColor and
                        abs(int(p[2]) - target[2]) < toleranceForAnyColor):


                    found = True
                    break
            if found: break

        if found:
            with open(CurrentCompany, 'a', newline='') as f:
                csv.writer(f).writerow([processed_name_val])
            print(f"{processed_name_val} as current Requirement")
            return True
        return False


# ==========================================
# MAIN EXECUTION PIPELINE
# ==========================================

def run_analysis_pipeline(input_path):
    img = Image.open(input_path).convert("RGB")
    pixels = np.array(img)
    startFromLeft = img.width - 60
    path_coordinates, red_coordinates = [], []

    for i in range(y, y - upto, -1):
        r, g, b = pixels[i, x]
        if ((r >= red_thresholds["min_r"] and g <= red_thresholds["max_g"] and b <= red_thresholds["max_b"]) or
                (r <= green_thresholds["min_r"] and g >= green_thresholds["max_g"] and b <= green_thresholds["max_b"])):
            red_coordinates.append((x, i))

        if [r, g, b] == [255, 255, 255]: continue
        path_coordinates.append((x, i))

    res_groups = group_coordinates(path_coordinates)
    centers = get_vertical_centers(res_groups)
    y_only_arr = [c[1] for c in centers]

    _, best_xRight_val = find_all_right_extremes(pixels, centers)
    leftX_val = find_black_vertical_boundary(pixels, centers)

    f_data = process_ocr_segments(img, leftX_val, best_xRight_val, y_only_arr)
    formatted_f_data = format_implied_decimals(f_data)

    red_mid_y = get_red_midpoint(red_coordinates)
    currentPrice_val = clean_and_calculate_price(red_mid_y, formatted_f_data)
    dotted_prices = []
    try:
        purp_ys = find_purple_y_coordinates_loop(pixels, darkpurple, toleranceForAnyColor)
        mid_purp_y_list = process_purple_markers(purp_ys)
        for mid_y in mid_purp_y_list:
            price = clean_and_calculate_price(mid_y, formatted_f_data)
            dotted_prices.append(price)
    except:
        print(f"Error calculating dotted prices: {e}")
        dotted_prices = []

    raw_name = get_text_from_boundaries(pixels, top_y, bottom_y, left_x, right_x)
    processed_name_val = clean_ocr_label(raw_name)

    return currentPrice_val, processed_name_val, dotted_prices, pixels


if __name__ == "__main__":
    tracker = NativeResultTracker(append_flag=append_Alerts)

    #source_folder = r"E:\Downloads"
    source_folder = os.path.join(base_dir, "Company_Charts")
    local_input_folder = os.path.join(base_dir, "input_queue")
    processed_folder = os.path.join(base_dir, "processed_archive")
    error_folder = os.path.join(base_dir, "error_storage")

    for folder in [local_input_folder, processed_folder, error_folder]:
        if not os.path.exists(folder): os.makedirs(folder)

    files_to_copy = [f for f in os.listdir(source_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

    for file_name in files_to_copy:
        shutil.copy2(os.path.join(source_folder, file_name), os.path.join(local_input_folder, file_name))

    local_images = [f for f in os.listdir(local_input_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    open(CurrentCompany, 'w').close()
    for image_name in local_images:
        current_image_path = os.path.join(local_input_folder, image_name)
        try:
            # --- STEP 1: LOAD PIXELS IMMEDIATELY ---
            img_for_check = Image.open(current_image_path).convert("RGB")
            pixel_matrix = np.array(img_for_check)

            # --- STEP 2: CHECK MAGENTA BEFORE DOING ANY ANALYSIS ---
            if tracker.check_magenta_requirement(pixel_matrix, image_name):
                # If found, this will print "current Requirement" and skip
                continue
                j=0;

            cur_p, name, dot_p_list, _ = run_analysis_pipeline(current_image_path)

            if not dot_p_list:
                shutil.move(current_image_path, os.path.join(error_folder, image_name))
                print(f"No purple markers found in {image_name}")
            else:
                # 1. Separate current targets into Above and Below groups
                above_targets = [p for p in dot_p_list if p > cur_p]
                below_targets = [p for p in dot_p_list if p <= cur_p]

                # 2. Slice both lists to keep only 2 from each
                # This automatically handles cases where there are 0, 1, or 4+ prices
                dot_p_list = above_targets[:above_count] + below_targets[:below_count]
                # 3. Process each dotted price found
                for dot_p in dot_p_list:
                    tracker.add_result(name, cur_p, dot_p)
                    #shutil.move(current_image_path, os.path.join(processed_folder, image_name))
                    print(f"Processed: {name} | Target: {dot_p} | Current: {cur_p}")
            Image.fromarray(pixel_matrix).save("output_final.png")
        except Exception as e:
            print(f"Error {image_name}: {e}")
            # shutil.move(current_image_path, os.path.join(error_folder, image_name))

    tracker.save_results(base_dir, override=(not append_flag))
    # 2. Then trigger the alerts
    # 3. Trigger Alerts
    tracker.trigger_kite_alerts()

    # 4. Show Failures
    tracker.print_final_report()
