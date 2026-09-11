import csv
import os
import shutil
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

# ===================================================================
# CONFIGURATION
# ===================================================================
# 🎯 CHANGE THIS VARIABLE: 'us' or 'indian'
MARKET = "us"

# 🎯 CONTROL FILE MOVEMENT: Set to True to move images to category folders, or False to update CSV only
MOVE_FILES = True

BASE_PROJECT_DIR = r"E:\PycharmProjects\pythonProject"

if MARKET.lower() == "indian":
    CHARTS_FOLDER = os.path.join(
        BASE_PROJECT_DIR, "weekly_5yr_indian_charts", "is_new_yes"
    )
    CATEGORY_BASE_DIR = os.path.join(
        BASE_PROJECT_DIR, "weekly_5yr_charts_by_category"
    )
    OUTPUT_FILE = os.path.join(BASE_PROJECT_DIR, "filled_indian_stocks.csv")
else:
    CHARTS_FOLDER = os.path.join(
        BASE_PROJECT_DIR, "weekly_5yr_charts", "is_new_yes"
    )
    CATEGORY_BASE_DIR = os.path.join(
        BASE_PROJECT_DIR, "weekly_5yr_charts_by_category_usa"
    )
    OUTPUT_FILE = os.path.join(BASE_PROJECT_DIR, "filled_us_stocks.csv")

# Keyboard mappings (Includes '8': 'i')
CATEGORIES = {
    "1": "vsu",
    "2": "su",
    "3": "vg",
    "4": "g",
    "8": "i",
}


# ===================================================================
# HELPER FUNCTIONS
# ===================================================================
def extract_ticker_from_filename(filename: str) -> str:
    """Extracts ticker name cleanly from a filename (e.g. 'AAPL_5yr.png' -> 'AAPL')."""
    base_name = os.path.splitext(filename)[0]
    return base_name.split("_")[0].strip().upper()


def get_already_categorized_tickers(csv_path: str) -> set:
    """Reads existing CSV and returns a set of tickers already processed."""
    already_done = set()
    if os.path.exists(csv_path):
        try:
            with open(csv_path, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header row
                for row in reader:
                    if row and row[0].strip():
                        already_done.add(row[0].strip().upper())
        except Exception as e:
            print(f"⚠️ Warning reading existing CSV: {e}")
    return already_done


# ===================================================================
# GUI APPLICATION
# ===================================================================
class FastCSVCategorizer:

    def __init__(self, root):
        self.root = root
        mode_str = "Mover & CSV" if MOVE_FILES else "CSV Only"
        self.root.title(
            f"Fast CSVCategorizer ({mode_str}) | Market: {MARKET.upper()} | Target:"
            f" {os.path.basename(OUTPUT_FILE)}"
        )
        self.root.geometry("1150x800")

        self.base_dir = Path(CHARTS_FOLDER)
        all_image_paths = (
            sorted(list(self.base_dir.glob("*.png")))
            if self.base_dir.exists()
            else []
        )

        # Get set of already processed tickers from CSV
        already_done_tickers = get_already_categorized_tickers(OUTPUT_FILE)

        # Filter out images whose tickers exist in the CSV
        self.image_paths = []
        for img_path in all_image_paths:
            ticker = extract_ticker_from_filename(img_path.name)
            if ticker not in already_done_tickers:
                self.image_paths.append(img_path)

        print(f"📊 Total Charts Found in Folder: {len(all_image_paths)}")
        print(f"✅ Tickers Already in CSV: {len(already_done_tickers)}")
        print(f"🔄 Remaining Queue to Process: {len(self.image_paths)}")
        print(f"📁 Move Files Enabled: {MOVE_FILES}")

        self.current_index = 0
        self.results = {}  # Store as dict {ticker: category}
        # History format: ("categorize", ticker, src_path, dest_path) or ("skip", ticker)
        self.action_history = []

        if not self.image_paths:
            print("\n🎉 All available charts are already categorized!")
            root.destroy()
            return

        self._build_ui()
        self._bind_keys()
        self._load_current_image()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        self.info_label = ttk.Label(
            self.root, font=("Helvetica", 14, "bold"), anchor="center"
        )
        self.info_label.pack(side=tk.TOP, fill=tk.X, pady=8)

        self.image_label = ttk.Label(self.root)
        self.image_label.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)

        button_frame = ttk.Frame(self.root)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

        for key, cat_name in CATEGORIES.items():
            btn = ttk.Button(
                button_frame,
                text=f"[{key}] {cat_name.upper()}",
                command=lambda c=cat_name: self.categorize(c),
            )
            btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)

        ttk.Button(button_frame, text="Skip [5]", command=self.skip).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=4
        )
        ttk.Button(button_frame, text="Undo (Z)", command=self.undo).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=4
        )
        ttk.Button(
            button_frame, text="💾 Save & Exit", command=self._on_close
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)

    def _bind_keys(self):
        for key, cat_name in CATEGORIES.items():
            self.root.bind(key, lambda event, c=cat_name: self.categorize(c))
            self.root.bind(f"<KP_{key}>", lambda event, c=cat_name: self.categorize(c))

        self.root.bind("5", lambda event: self.skip())
        self.root.bind("<KP_5>", lambda event: self.skip())
        self.root.bind("z", lambda event: self.undo())
        self.root.bind("Z", lambda event: self.undo())
        self.root.bind("<Escape>", lambda event: self._on_close())

    def _get_current_ticker(self) -> str:
        filename = self.image_paths[self.current_index].name
        return extract_ticker_from_filename(filename)

    def _load_current_image(self):
        if self.current_index >= len(self.image_paths):
            self.info_label.config(text="🎉 All charts categorized! Click 'Save & Exit'.")
            self.image_label.config(image="")
            return

        ticker = self._get_current_ticker()
        total = len(self.image_paths)

        self.info_label.config(
            text=f"[{MARKET.upper()}] Remaining Queue: [{self.current_index + 1}/{total}]"
            f"  |  Ticker: {ticker}"
        )

        image = Image.open(self.image_paths[self.current_index])
        image.thumbnail((1100, 620), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(image)
        self.image_label.config(image=self.tk_image)

    def categorize(self, category_name: str):
        if self.current_index >= len(self.image_paths):
            return

        src_path = self.image_paths[self.current_index]
        ticker = self._get_current_ticker()

        # 1. Update CSV buffer
        self.results[ticker] = category_name

        dest_path = None
        # 2. Conditionally move file physically based on MOVE_FILES variable
        if MOVE_FILES:
            target_dir = os.path.join(CATEGORY_BASE_DIR, category_name.lower())
            os.makedirs(target_dir, exist_ok=True)
            dest_path = os.path.join(target_dir, src_path.name)

            if str(src_path) != str(dest_path):
                shutil.move(str(src_path), str(dest_path))

        # 3. Track history for Undo
        self.action_history.append(("categorize", ticker, src_path, dest_path))

        self.current_index += 1
        self._load_current_image()

    def skip(self):
        if self.current_index < len(self.image_paths):
            ticker = self._get_current_ticker()
            self.action_history.append(("skip", ticker))
            self.current_index += 1
            self._load_current_image()

    def undo(self):
        if not self.action_history:
            return

        last_action = self.action_history.pop()
        action_type = last_action[0]

        if action_type == "categorize":
            _, ticker, src_path, dest_path = last_action

            # Move image back to original folder if MOVE_FILES was enabled
            if MOVE_FILES and dest_path and os.path.exists(dest_path):
                shutil.move(str(dest_path), str(src_path))

            # Delete from CSV memory buffer
            if ticker in self.results:
                del self.results[ticker]

        self.current_index = max(0, self.current_index - 1)
        self._load_current_image()

    def _on_close(self):
        if self.results:
            existing_data = {}

            # Read existing CSV file first
            if os.path.exists(OUTPUT_FILE):
                with open(OUTPUT_FILE, mode="r", newline="", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    for row in reader:
                        if len(row) >= 2:
                            existing_data[row[0].strip().upper()] = row[1].strip()

            # Append/overwrite with new session results
            for ticker, category in self.results.items():
                existing_data[ticker] = category

            # Rewrite CSV cleanly
            with open(OUTPUT_FILE, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Ticker", "Category"])
                for ticker, category in existing_data.items():
                    writer.writerow([ticker, category])

            print(
                f"\n✅ Saved {len(self.results)} new entries to '{OUTPUT_FILE}'"
                f" (Total Unique: {len(existing_data)})"
            )

            if MOVE_FILES:
                moved_count = sum(
                    1 for action in self.action_history if action[0] == "categorize"
                )
                print(f"📦 Total Files Moved to Category Folders: {moved_count}")
        else:
            print("\n⚠️ No new selections recorded.")

        self.root.destroy()


# ===================================================================
# EXECUTION
# ===================================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = FastCSVCategorizer(root)
    root.mainloop()