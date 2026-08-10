import glob
import os
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import yfinance as yf

# ===================================================================
# CONFIGURATION & USER VARIABLES
# ===================================================================
# Base file name (script automatically checks for .csv, .xlsx, or .xls)
INPUT_FILE_BASE = "final_screened_indian_stocks"

# Name of output folder created strictly inside your current project directory
FOLDER_NAME = "weekly_5yr_indian_charts"

# Default exchange suffix (".NS" for National Stock Exchange, ".BO" for Bombay Stock Exchange)
DEFAULT_SUFFIX = ".NS"

# Is_New filter choice: "Yes", "No", or "ALL"
FILTER_IS_NEW = "No"

# Create filter-specific subfolders (e.g., "weekly_5yr_indian_charts/is_new_yes")
AUTO_SUBFOLDER_BY_FILTER = True

# Delete old PNG graph images in target folder before running
DELETE_EXISTING_GRAPHS = True


# ===================================================================
# HELPER: Locate & Read Input File (CSV or Excel)
# ===================================================================
def load_input_dataframe(file_base: str) -> pd.DataFrame:
  """Detects if input file is .csv or .xlsx/.xls and loads it into a DataFrame."""
  target_file = None

  # Check possible extensions
  for ext in ["", ".csv", ".xlsx", ".xls"]:
    candidate = file_base + ext
    if os.path.exists(candidate):
      target_file = candidate
      break

  if not target_file:
    print(
        f"❌ Error: Could not find '{file_base}' as .csv, .xlsx, or .xls in"
        " current folder."
    )
    return pd.DataFrame()

  print(f"📄 Found Input File: '{target_file}'")

  try:
    if target_file.endswith(".xlsx") or target_file.endswith(".xls"):
      return pd.read_excel(target_file)
    else:
      return pd.read_csv(target_file)
  except Exception as e:
    print(f"❌ Error reading '{target_file}': {e}")
    return pd.DataFrame()


# ===================================================================
# HELPER: Prepare Target Directory Inside Project Folder
# ===================================================================
def prepare_project_directory(
    folder_name: str,
    is_new_filter: str,
    use_subfolders: bool,
    delete_existing: bool,
) -> str:
  """Creates output directory strictly inside the current project folder."""
  project_dir = os.getcwd()

  if use_subfolders:
    subfolder = f"is_new_{is_new_filter.lower()}"
    target_dir = os.path.join(project_dir, folder_name, subfolder)
  else:
    target_dir = os.path.join(project_dir, folder_name)

  os.makedirs(target_dir, exist_ok=True)
  print(f"📁 Project Output Folder: '{target_dir}'")

  # Wipe old PNG files if enabled
  if delete_existing:
    existing_files = glob.glob(os.path.join(target_dir, "*.png"))
    if existing_files:
      print(f"  -> Cleaning {len(existing_files)} existing PNGs...")
      for file in existing_files:
        try:
          os.remove(file)
        except Exception as e:
          print(f"  Failed to delete {file}: {e}")
      print("  -> Cleanup complete.")
    else:
      print("  -> No existing PNGs found in target directory.")

  return target_dir


# ===================================================================
# HELPER: Format Ticker for Yahoo Finance (.NS / .BO)
# ===================================================================
def format_indian_ticker(ticker: str, default_suffix: str) -> str:
  """Ensures ticker symbol has an exchange suffix like .NS or .BO."""
  clean_symbol = str(ticker).strip().upper().replace("&", "_")

  if clean_symbol.endswith(".NS") or clean_symbol.endswith(".BO"):
    return clean_symbol

  return f"{clean_symbol}{default_suffix}"


# ===================================================================
# HELPER: Fetch 5-Year Weekly Data via yfinance
# ===================================================================
def fetch_5yr_weekly_yf(ticker_yf: str) -> pd.DataFrame:
  """Fetches 5 years of weekly OHLCV stock data from Yahoo Finance."""
  try:
    stock = yf.Ticker(ticker_yf)
    df = stock.history(period="5y", interval="1wk")

    if df.empty:
      print(f"  ⚠️ No data found on Yahoo Finance for: {ticker_yf}")
      return pd.DataFrame()

    df = df.reset_index()
    return df[["Date", "Open", "High", "Low", "Close", "Volume"]]

  except Exception as e:
    print(f"  ❌ Error fetching {ticker_yf}: {e}")
    return pd.DataFrame()


# ===================================================================
# HELPER: Plot & Save Chart (Price + Volume in ₹)
# ===================================================================
def plot_and_save_chart(
    df: pd.DataFrame, display_name: str, output_dir: str
):
  """Plots 5-year weekly closing prices with volume sub-chart in INR (₹)."""
  fig, (ax_price, ax_vol) = plt.subplots(
      2,
      1,
      figsize=(12, 6.5),
      gridspec_kw={"height_ratios": [3, 1]},
      sharex=True,
  )

  # 1. Price Subplot
  ax_price.plot(
      df["Date"], df["Close"], color="#0052cc", linewidth=1.8, label="Weekly Close"
  )
  ax_price.set_title(
      f"{display_name} — 5-Year Weekly Price Trend",
      fontsize=14,
      fontweight="bold",
      pad=12,
  )
  ax_price.set_ylabel("Price (₹)", fontsize=11)
  ax_price.grid(True, linestyle="--", alpha=0.5)
  ax_price.yaxis.set_major_formatter(mticker.FormatStrFormatter("₹%.2f"))

  # Min / Max Markers
  min_row = df.loc[df["Close"].idxmin()]
  max_row = df.loc[df["Close"].idxmax()]

  ax_price.scatter(
      min_row["Date"], min_row["Close"], color="red", s=50, zorder=5
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
      max_row["Date"], max_row["Close"], color="green", s=50, zorder=5
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

  # Clean base ticker for image filename
  clean_filename = display_name.replace(".NS", "").replace(".BO", "")
  file_path = os.path.join(output_dir, f"{clean_filename}_5yr_weekly.png")

  plt.savefig(file_path, dpi=150, bbox_inches="tight")
  plt.close(fig)

  print(f"  -> Saved chart: '{file_path}'")


# ===================================================================
# MAIN WORKFLOW
# ===================================================================
if __name__ == "__main__":
  print(
      "================ 5-YEAR WEEKLY CHART GENERATOR (INDIAN STOCKS)"
      " ================\n"
  )

  # Step 1: Prepare output directory strictly inside current project
  target_dir = prepare_project_directory(
      FOLDER_NAME,
      FILTER_IS_NEW,
      AUTO_SUBFOLDER_BY_FILTER,
      DELETE_EXISTING_GRAPHS,
  )

  # Step 2: Read input file (.csv or .xlsx)
  df_input = load_input_dataframe(INPUT_FILE_BASE)

  if df_input.empty:
    print("Exiting script because input data could not be loaded.")
    exit()

  if "Ticker" not in df_input.columns:
    print("❌ Error: Missing 'Ticker' column in input file. Exiting.")
    exit()

  # Apply Is_New Filter if column exists
  if FILTER_IS_NEW.upper() != "ALL" and "Is_New" in df_input.columns:
    df_input = df_input[
        df_input["Is_New"].astype(str).str.strip().str.capitalize()
        == FILTER_IS_NEW.capitalize()
    ]

  raw_tickers = df_input["Ticker"].dropna().unique().tolist()
  print(
      f"\nProcessing {len(raw_tickers)} ticker(s) matching Is_New ="
      f" '{FILTER_IS_NEW}'...\n"
  )

  # Step 3: Loop through tickers, fetch data, and save charts
  saved_count = 0
  for idx, raw_ticker in enumerate(raw_tickers, start=1):
    yf_ticker = format_indian_ticker(raw_ticker, DEFAULT_SUFFIX)
    print(
        f"[{idx}/{len(raw_tickers)}] Fetching 5Y weekly data for '{yf_ticker}'..."
    )

    df_weekly = fetch_5yr_weekly_yf(yf_ticker)

    if not df_weekly.empty:
      plot_and_save_chart(df_weekly, yf_ticker, target_dir)
      saved_count += 1

  print(
      f"\n✅ SUCCESS! Generated {saved_count} chart(s) inside project folder:"
  )
  print(f"📍 '{target_dir}'")
  print("===============================================================")