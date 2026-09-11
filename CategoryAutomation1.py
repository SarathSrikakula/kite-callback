import csv
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

# ===================================================================
# CONFIGURATION
# ===================================================================
# 🎯 CHANGE THIS VARIABLE: 'us' or 'indian'
MARKET = "indian"

BASE_PROJECT_DIR = r"E:\PycharmProjects\pythonProject"

if MARKET.lower() == "indian":
    CHARTS_FOLDER = os.path.join(
        BASE_PROJECT_DIR, "weekly_5yr_indian_charts", "is_new_yes"
    )
    OUTPUT_FILE = os.path.join(BASE_PROJECT_DIR, "filled_indian_stocks.csv")
else:
    CHARTS_FOLDER = os.path.join(
        BASE_PROJECT_DIR, "weekly_5yr_charts", "is_new_yes"
    )
    OUTPUT_FILE = os.path.join(BASE_PROJECT_DIR, "filled_us_stocks.csv")

# Keyboard mappings
CATEGORIES = {
    "1": "vsu",
    "2": "su",
    "3": "vg",
    "4": "g",
}


# ===================================================================
# HELPER FUNCTIONS
# ===================================================================
def get_already_categorized_tickers(csv_path: str) -> set:
    """Reads existing CSV and returns a set of tickers already processed."""
    already_done = set()
    if os.path.exists(csv_path):
        try:
            with open(csv_path, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header
                for row in reader:
                    if row:
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
        self.root.title(
            f"Fast CSV Categorizer | Market: {MARKET.upper()} | Target:"
            f" {os.path.basename(OUTPUT_FILE)}"
        )
        self.root.geometry("1150x800")

        self.base_dir = Path(CHARTS_FOLDER)
        all_image_paths = (
            sorted(list(self.base_dir.rglob("*.png")))
            if self.base_dir.exists()
            else []
        )

        # Fetch tickers already present in the output CSV
        already_done_tickers = get_already_categorized_tickers(OUTPUT_FILE)

        # Filter out images whose tickers are already categorized
        self.image_paths = []
        for img_path in all_image_paths:
            ticker = img_path.name.split("_")[0].upper()
            if ticker not in already_done_tickers:
                self.image_paths.append(img_path)

        print(f"📊 Total Charts Found: {len(all_image_paths)}")
        print(f"✅ Already Categorized: {len(already_done_tickers)}")
        print(f"🔄 Remaining to Process: {len(self.image_paths)}")

        self.current_index = 0
        self.results = []

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

        ttk.Button(button_frame, text="Skip (Space)", command=self.skip).pack(
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
        self.root.bind("<Escape>", lambda event: self._on_close())

    def _get_current_ticker(self) -> str:
        filename = self.image_paths[self.current_index].name
        return filename.split("_")[0].upper()

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

        ticker = self._get_current_ticker()
        self.results.append((ticker, category_name))

        self.current_index += 1
        self._load_current_image()

    def skip(self):
        if self.current_index < len(self.image_paths) - 1:
            self.current_index += 1
            self._load_current_image()

    def undo(self):
        if not self.results:
            return

        self.results.pop()
        self.current_index = max(0, self.current_index - 1)
        self._load_current_image()

    def _on_close(self):
        if self.results:
            existing_data = {}

            if os.path.exists(OUTPUT_FILE):
                with open(OUTPUT_FILE, mode="r", newline="", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    for row in reader:
                        if len(row) >= 2:
                            existing_data[row[0]] = row[1]

            for ticker, category in self.results:
                existing_data[ticker] = category

            with open(OUTPUT_FILE, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Ticker", "Category"])
                for ticker, category in existing_data.items():
                    writer.writerow([ticker, category])

            print(
                f"\n✅ Appended {len(self.results)} new entries to '{OUTPUT_FILE}'"
                f" (Total Unique: {len(existing_data)})"
            )
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