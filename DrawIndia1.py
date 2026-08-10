import glob
import os
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import yfinance as yf

# ===================================================================
# CONFIGURATION
# ===================================================================
# Base file name (auto-checks for .xlsx or .csv)
INPUT_FILE_BASE = "final_screened_indian_stocks"

# Output directory name created inside current project folder
OUTPUT_FOLDER = "weekly_5yr_indian_charts"

# Exchange suffix (.NS for National Stock Exchange, .BO for Bombay Stock Exchange)
DEFAULT_SUFFIX = ".NS"

# 🎯 EDIT THIS ARRAY TO PICK WHICH CATEGORIES TO PROCESS
# Options:
#   - Specific list: ["Automobile", "IT Services", "Banking"]
#   - Single category: ["Pharma"]
#   - Everything: ["ALL"] or []
SELECTED_CATEGORIES = ["Automobile", "IT Services", "Banking"]

# Save charts inside separate category subfolders? (e.g., weekly_5yr_indian_charts/Automobile/MARUTI_5yr_weekly.png)
CREATE_CATEGORY_SUBFOLDERS = True

# Delete previous PNG charts before generating new ones?
DELETE_EXISTING_GRAPHS = True


# ===================================================================
# HELPER FUNCTIONS
# ===================================================================
def load_ticker_category_data(file_base: str) -> pd.DataFrame:
  """Locates file and reads ONLY the 'Ticker' and 'Category' columns."""
  target_file = None
  for ext in ["", ".xlsx", ".csv", ".xls"]:
    candidate = file_base + ext
    if os.path.exists(candidate):
      target_file = candidate
      break

  if not target_file:
    print(
        f"❌ Error: File '{file_base}' (.xlsx or .csv) not found in current"
        " folder."
    )
    return pd.DataFrame()

  print(f"📄 Reading File: '{target_file}'")

  try:
    if target_file.endswith(".xlsx") or target_file.endswith(".xls"):
      df = pd.read_excel(target_file, usecols=["Ticker", "Category"])
    else:
      df = pd.read_csv(target_file, usecols=["Ticker", "Category"])

    return df.dropna(subset=["Ticker"])
  except Exception as e:
    print(
        f"❌ Error reading columns ('Ticker', 'Category') from '{target_file}':"
        f" {e}"
    )
    return pd.DataFrame()


def prepare_output_directory(folder_name: str, delete_existing: bool) -> str:
  """Creates base folder and cleans previous PNGs if requested."""
  base_dir = os.path.join(os.getcwd(), folder_name)
  os.makedirs(base_dir, exist_ok=True)

  if delete_existing:
    existing_files = glob.glob(
        os.path.join(base_dir, "**", "*.png"), recursive=True
    )
    if existing_files:
      print(f"🧹 Wiping {len(existing_files)} existing PNG chart(s)...")
      for file in existing_files:
        try:
          os.remove(file)
        except Exception:
          pass

  return base_dir


def format_indian_ticker(ticker: str, suffix: str) -> str:
  """Appends exchange suffix (.NS) if missing."""
  symbol = str(ticker).strip().upper().replace("&", "_")
  if symbol.endswith(".NS") or symbol.endswith(".BO"):
    return symbol
  return f"{symbol}{suffix}"


def fetch_and_plot(
    ticker_yf: str, category: str, display_name: str, save_dir: str
) -> bool:
  """Fetches 5y weekly data and saves chart in INR (₹)."""
  try:
    stock = yf.Ticker(ticker_yf)
    df = stock.history(period="5y", interval="1wk")

    if df.empty:
      print(f"  ⚠️ No data found on Yahoo Finance for: {ticker_yf}")
      return False

    df = df.reset_index()[["Date", "Close", "Volume"]]

    # Plot Setup
    fig, (ax_price, ax_vol) = plt.subplots(
        2,
        1,
        figsize=(12, 6.5),
        gridspec_kw={"height_ratios": [3, 1]},
        sharex=True,
    )

    # 1. Price Subplot
    ax_price.plot(
        df["Date"],
        df["Close"],
        color="#0052cc",
        linewidth=1.8,
        label="Weekly Close",
    )
    ax_price.set_title(
        f"{display_name} [{category}] — 5-Year Weekly Price Trend",
        fontsize=14,
        fontweight="bold",
        pad=12,
    )
    ax_price.set_ylabel("Price (₹)", fontsize=11)
    ax_price.grid(True, linestyle="--", alpha=0.5)
    ax_price.yaxis.set_major_formatter(mticker.FormatStrFormatter("₹%.2f"))

    # High / Low Callouts
    min_row = df.loc[df["Close"].idxmin()]
    max_row = df.loc[df["Close"].idxmax()]

    ax_price.scatter(
        min_row["Date"], min_row["Close"], color="red", s=40, zorder=5
    )
    ax_price.annotate(
        f"Low: ₹{min_row['Close']:.2f}",
        (min_row["Date"], min_row["Close"]),
        textcoords="offset points",
        xytext=(0, -15),
        ha="center",
        fontsize=8,
        bbox=dict(boxstyle="round,pad=0.2", fc="yellow", alpha=0.6),
    )

    ax_price.scatter(
        max_row["Date"], max_row["Close"], color="green", s=40, zorder=5
    )
    ax_price.annotate(
        f"High: ₹{max_row['Close']:.2f}",
        (max_row["Date"], max_row["Close"]),
        textcoords="offset points",
        xytext=(0, 10),
        ha="center",
        fontsize=8,
        bbox=dict(boxstyle="round,pad=0.2", fc="lightgreen", alpha=0.6),
    )

    # 2. Volume Subplot
    ax_vol.bar(df["Date"], df["Volume"], color="#6b778c", alpha=0.6, width=5)
    ax_vol.set_ylabel("Volume", fontsize=10)
    ax_vol.set_xlabel("Date", fontsize=11)
    ax_vol.grid(True, linestyle="--", alpha=0.3)
    ax_vol.yaxis.set_major_formatter(mticker.EngFormatter())

    plt.xticks(rotation=0)
    plt.tight_layout()

    # Save PNG
    clean_symbol = display_name.replace(".NS", "").replace(".BO", "")
    file_path = os.path.join(save_dir, f"{clean_symbol}_5yr_weekly.png")
    plt.savefig(file_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(f"  -> Saved chart: '{file_path}'")
    return True

  except Exception as e:
    print(f"  ❌ Error processing {ticker_yf}: {e}")
    return False


# ===================================================================
# MAIN EXECUTION
# ===================================================================
if __name__ == "__main__":
  print("================ TICKER & CATEGORY CHART GENERATOR ================\n")

  base_dir = prepare_output_directory(OUTPUT_FOLDER, DELETE_EXISTING_GRAPHS)
  df = load_ticker_category_data(INPUT_FILE_BASE)

  if df.empty:
    print("Exiting.")
    exit()

  # Apply category filtering
  if SELECTED_CATEGORIES and "ALL" not in [
      c.upper() for c in SELECTED_CATEGORIES
  ]:
    target_cats = [c.strip().lower() for c in SELECTED_CATEGORIES]
    df = df[
        df["Category"].astype(str).str.strip().str.lower().isin(target_cats)
    ]
    print(f"🎯 Filtered for Categories: {SELECTED_CATEGORIES}")

  if df.empty:
    print("❌ No matching categories found in the input file.")
    exit()

  print(f"\nProcessing {len(df)} stock(s)...\n")

  saved = 0
  for idx, row in df.iterrows():
    raw_ticker = str(row["Ticker"]).strip()
    category = str(row["Category"]).strip()
    yf_ticker = format_indian_ticker(raw_ticker, DEFAULT_SUFFIX)

    # Determine output folder
    if CREATE_CATEGORY_SUBFOLDERS:
      save_dir = os.path.join(base_dir, category.replace("/", "_"))
      os.makedirs(save_dir, exist_ok=True)
    else:
      save_dir = base_dir

    print(f"[{saved+1}/{len(df)}] [{category}] Fetching '{yf_ticker}'...")
    if fetch_and_plot(yf_ticker, category, raw_ticker, save_dir):
      saved += 1

  print(f"\n✅ Done! {saved} chart(s) created in:")
  print(f"📍 '{base_dir}'")
  print("===================================================================")