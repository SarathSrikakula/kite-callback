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
MARKET = "us"

# Base directory where CSV files live
BASE_PROJECT_DIR = r"E:\PycharmProjects\pythonProject"

# Dynamic folder and file resolution based on MARKET choice
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

# Map keyboard keys to your 4 categories
CATEGORIES = {
    "1": "su",
    "2": "vsu",
    "3": "g",
    "4": "vg",
}


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
    self.image_paths = (
        sorted(list(self.base_dir.rglob("*.png")))
        if self.base_dir.exists()
        else []
    )

    self.current_index = 0
    self.results = []  # Stores list of tuples: [('AAPL', 'su'), ...]

    if not self.image_paths:
      print(f"❌ Error: No PNG charts found in '{CHARTS_FOLDER}'")
      root.destroy()
      return

    self._build_ui()
    self._bind_keys()
    self._load_current_image()

    self.root.protocol("WM_DELETE_WINDOW", self._on_close)

  def _build_ui(self):
    """Builds GUI layout."""
    self.info_label = ttk.Label(
        self.root, font=("Helvetica", 14, "bold"), anchor="center"
    )
    self.info_label.pack(side=tk.TOP, fill=tk.X, py=8)

    self.image_label = ttk.Label(self.root)
    self.image_label.pack(expand=True, fill=tk.BOTH, px=10, py=5)

    button_frame = ttk.Frame(self.root)
    button_frame.pack(side=tk.BOTTOM, fill=tk.X, py=10)

    # 4 Category Buttons
    for key, cat_name in CATEGORIES.items():
      btn = ttk.Button(
          button_frame,
          text=f"[{key}] {cat_name.upper()}",
          command=lambda c=cat_name: self.categorize(c),
      )
      btn.pack(side=tk.LEFT, expand=True, fill=tk.X, px=4)

    # Secondary Action Buttons
    ttk.Button(button_frame, text="Skip (Space)", command=self.skip).pack(
        side=tk.LEFT, expand=True, fill=tk.X, px=4
    )
    ttk.Button(button_frame, text="Undo (Z)", command=self.undo).pack(
        side=tk.LEFT, expand=True, fill=tk.X, px=4
    )
    ttk.Button(
        button_frame, text="💾 Save & Exit", command=self._on_close
    ).pack(side=tk.LEFT, expand=True, fill=tk.X, px=4)

  def _bind_keys(self):
    """Binds keys for fast single-hand operation."""
    for key, cat_name in CATEGORIES.items():
      self.root.bind(key, lambda event, c=cat_name: self.categorize(c))
      self.root.bind(f"<KP_{key}>", lambda event, c=cat_name: self.categorize(c))

    self.root.bind("<space>", lambda event: self.skip())
    self.root.bind("z", lambda event: self.undo())
    self.root.bind("<Escape>", lambda event: self._on_close())

  def _get_current_ticker(self) -> str:
    """Extracts ticker name from filename (e.g., 'AAPL_5yr_weekly.png' -> 'AAPL')."""
    filename = self.image_paths[self.current_index].name
    return filename.split("_")[0].upper()

  def _load_current_image(self):
    """Displays active chart on screen."""
    if self.current_index >= len(self.image_paths):
      self.info_label.config(text="🎉 All charts categorized! Click 'Save & Exit'.")
      self.image_label.config(image="")
      return

    ticker = self._get_current_ticker()
    total = len(self.image_paths)

    self.info_label.config(
        text=f"[{MARKET.upper()}] Progress: [{self.current_index + 1}/{total}]"
        f"  |  Ticker: {ticker}"
    )

    image = Image.open(self.image_paths[self.current_index])
    image.thumbnail((1100, 620), Image.Resampling.LANCZOS)
    self.tk_image = ImageTk.PhotoImage(image)
    self.image_label.config(image=self.tk_image)

  def categorize(self, category_name: str):
    """Logs category selection in memory and loads next chart."""
    if self.current_index >= len(self.image_paths):
      return

    ticker = self._get_current_ticker()
    self.results.append((ticker, category_name))

    self.current_index += 1
    self._load_current_image()

  def skip(self):
    """Skips active image without logging."""
    if self.current_index < len(self.image_paths) - 1:
      self.current_index += 1
      self._load_current_image()

  def undo(self):
    """Reverts last entry and goes back 1 image."""
    if not self.results:
      return

    self.results.pop()
    self.current_index = max(0, self.current_index - 1)
    self._load_current_image()

  def _on_close(self):
    """Appends session records directly to the CSV file, keeping existing data and removing duplicates."""
    if self.results:
      existing_data = {}

      # Read existing records if CSV exists
      if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, mode="r", newline="", encoding="utf-8") as f:
          reader = csv.reader(f)
          header = next(reader, None)  # Skip header row
          for row in reader:
            if len(row) >= 2:
              existing_data[row[0]] = row[1]

      # Add or update entries with new session results
      for ticker, category in self.results:
        existing_data[ticker] = category

      # Write everything back out to CSV
      with open(OUTPUT_FILE, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Ticker", "Category"])  # Header
        for ticker, category in existing_data.items():
          writer.writerow([ticker, category])

      print(
          f"\n✅ Saved {len(self.results)} new entries to '{OUTPUT_FILE}'"
          f" (Total unique tickers: {len(existing_data)})"
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