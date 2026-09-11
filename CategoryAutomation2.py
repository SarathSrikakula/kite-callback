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

# 🎯 SET THE CATEGORY YOU WANT TO REVIEW & UPDATE: 'vsu', 'su', 'vg', 'g', or 'i'
SOURCE_CATEGORY = "i"

BASE_PROJECT_DIR = r"E:\PycharmProjects\pythonProject"

# Directories by market selection
if MARKET.lower() == "indian":
    CATEGORY_BASE_DIR = os.path.join(
        BASE_PROJECT_DIR, "weekly_5yr_charts_by_category"
    )
    OUTPUT_FILE = os.path.join(BASE_PROJECT_DIR, "filled_indian_stocks.csv")
else:
    CATEGORY_BASE_DIR = os.path.join(
        BASE_PROJECT_DIR, "weekly_5yr_charts_by_category_usa"
    )
    OUTPUT_FILE = os.path.join(BASE_PROJECT_DIR, "filled_us_stocks.csv")

# Source folder where target charts currently reside
CHARTS_FOLDER = os.path.join(CATEGORY_BASE_DIR, SOURCE_CATEGORY.lower())

# Keyboard mappings
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
def load_all_existing_data(csv_path: str) -> dict:
    """Reads the CSV file into a dictionary {TICKER: CATEGORY}."""
    data = {}
    if os.path.exists(csv_path):
        try:
            with open(csv_path, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header
                for row in reader:
                    if len(row) >= 2:
                        data[row[0].strip().upper()] = row[1].strip().lower()
        except Exception as e:
            print(f"⚠️ Warning reading existing CSV: {e}")
    return data


# ===================================================================
# GUI APPLICATION (CSV UPDATE, MOVER & DELETER)
# ===================================================================
class UpdateAndMoveCategorizer:

    def __init__(self, root):
        self.root = root
        self.root.title(
            f"Update & Move Categorizer | Market: {MARKET.upper()} | Reviewing:"
            f" [{SOURCE_CATEGORY.upper()}]"
        )
        self.root.geometry("1200x800")

        self.base_dir = Path(CHARTS_FOLDER)
        self.image_paths = (
            sorted(list(self.base_dir.rglob("*.png")))
            if self.base_dir.exists()
            else []
        )

        # Load existing records to update in memory
        self.all_csv_data = load_all_existing_data(OUTPUT_FILE)

        print(f"📊 Charts Found in '{SOURCE_CATEGORY}': {len(self.image_paths)}")
        print(f"📁 Source Directory: {CHARTS_FOLDER}")

        self.current_index = 0
        # History format:
        # ("categorize", ticker, src_path, dest_path, old_cat, new_cat)
        # ("delete", ticker, src_path, old_cat, file_bytes)
        # ("skip", ticker)
        self.history = []

        if not self.image_paths:
            print(f"\n🎉 No charts found in category folder '{SOURCE_CATEGORY}'!")
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
            btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)

        ttk.Button(button_frame, text="Skip [5]", command=self.skip).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=3
        )
        ttk.Button(button_frame, text="🗑️ Delete (D)", command=self.delete_item).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=3
        )
        ttk.Button(button_frame, text="Undo (Z)", command=self.undo).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=3
        )
        ttk.Button(
            button_frame, text="💾 Save & Exit", command=self._on_close
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)

    def _bind_keys(self):
        for key, cat_name in CATEGORIES.items():
            self.root.bind(key, lambda event, c=cat_name: self.categorize(c))
            self.root.bind(f"<KP_{key}>", lambda event, c=cat_name: self.categorize(c))

        self.root.bind("5", lambda event: self.skip())
        self.root.bind("<KP_5>", lambda event: self.skip())

        # Delete key shortcuts (Delete key, 'd', and 'D')
        self.root.bind("<Delete>", lambda event: self.delete_item())
        self.root.bind("d", lambda event: self.delete_item())
        self.root.bind("D", lambda event: self.delete_item())

        # Support both lowercase and uppercase Z for Undo
        self.root.bind("z", lambda event: self.undo())
        self.root.bind("Z", lambda event: self.undo())

        self.root.bind("<Escape>", lambda event: self._on_close())

    def _get_current_ticker(self) -> str:
        filename = self.image_paths[self.current_index].name
        return filename.split("_")[0].upper()

    def _load_current_image(self):
        if self.current_index >= len(self.image_paths):
            self.info_label.config(text="🎉 All charts reviewed! Click 'Save & Exit'.")
            self.image_label.config(image="")
            return

        ticker = self._get_current_ticker()
        total = len(self.image_paths)

        self.info_label.config(
            text=f"[{MARKET.upper()}] Updating [{SOURCE_CATEGORY.upper()}] | Queue: [{self.current_index + 1}/{total}]"
                 f"  |  Ticker: {ticker}"
        )

        image = Image.open(self.image_paths[self.current_index])
        image.thumbnail((1100, 620), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(image)
        self.image_label.config(image=self.tk_image)

    def categorize(self, target_category: str):
        if self.current_index >= len(self.image_paths):
            return

        src_path = self.image_paths[self.current_index]
        ticker = self._get_current_ticker()
        old_category = self.all_csv_data.get(ticker, SOURCE_CATEGORY)

        # Target directory setup
        target_dir = os.path.join(CATEGORY_BASE_DIR, target_category.lower())
        os.makedirs(target_dir, exist_ok=True)
        dest_path = os.path.join(target_dir, src_path.name)

        # 1. Update CSV in memory
        self.all_csv_data[ticker] = target_category

        # 2. Move file physically if target category is different
        if str(src_path) != str(dest_path):
            shutil.move(str(src_path), str(dest_path))

        # 3. Log to history stack
        self.history.append((
            "categorize",
            ticker,
            src_path,
            dest_path,
            old_category,
            target_category,
        ))

        self.current_index += 1
        self._load_current_image()

    def delete_item(self):
        if self.current_index >= len(self.image_paths):
            return

        src_path = self.image_paths[self.current_index]
        ticker = self._get_current_ticker()
        old_category = self.all_csv_data.get(ticker, SOURCE_CATEGORY)

        # 1. Backup file content into memory for Undo support
        with open(src_path, "rb") as f:
            file_bytes = f.read()

        # 2. Delete file physically from disk
        if os.path.exists(src_path):
            os.remove(src_path)

        # 3. Remove entry from CSV memory dictionary
        if ticker in self.all_csv_data:
            del self.all_csv_data[ticker]

        # 4. Log to history stack
        self.history.append((
            "delete",
            ticker,
            src_path,
            old_category,
            file_bytes,
        ))

        self.current_index += 1
        self._load_current_image()

    def skip(self):
        if self.current_index < len(self.image_paths):
            ticker = self._get_current_ticker()
            self.history.append(("skip", ticker))

            self.current_index += 1
            self._load_current_image()

    def undo(self):
        if not self.history:
            return

        last_action = self.history.pop()
        action_type = last_action[0]

        if action_type == "categorize":
            _, ticker, src_path, dest_path, old_category, _ = last_action

            # Move image back to original directory
            if os.path.exists(dest_path):
                shutil.move(str(dest_path), str(src_path))

            # Revert CSV record
            self.all_csv_data[ticker] = old_category

        elif action_type == "delete":
            _, ticker, src_path, old_category, file_bytes = last_action

            # Restore the deleted file from memory bytes back to disk
            with open(src_path, "wb") as f:
                f.write(file_bytes)

            # Restore CSV record
            self.all_csv_data[ticker] = old_category

        self.current_index = max(0, self.current_index - 1)
        self._load_current_image()

    def _on_close(self):
        # Save CSV upon exit
        if self.all_csv_data:
            with open(OUTPUT_FILE, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Ticker", "Category"])
                for ticker, category in self.all_csv_data.items():
                    writer.writerow([ticker, category])

            moved_count = sum(1 for action in self.history if action[0] == "categorize")
            deleted_count = sum(1 for action in self.history if action[0] == "delete")

            print(f"\n✅ Updated CSV written to: '{OUTPUT_FILE}'")
            print(f"📦 Total Files Moved: {moved_count}")
            print(f"🗑️ Total Files Deleted: {deleted_count}")

        self.root.destroy()


# ===================================================================
# EXECUTION
# ===================================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = UpdateAndMoveCategorizer(root)
    root.mainloop()