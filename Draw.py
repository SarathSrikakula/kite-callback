import glob
import os
import time
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import requests

# ===================================================================
# CONFIGURATION & USER VARIABLES
# ===================================================================
API_KEY = "J35wnk4eNZEioisPriHivFBlefFd9dfb"
INPUT_FILE = "final_screened_stocks.csv"  # or "final_screened_indian_stocks.csv"

# -------------------------------------------------------------------
# 📁 PROJECT FOLDER SETTINGS
# -------------------------------------------------------------------
# Name of the folder to be created inside your current project directory
FOLDER_NAME = "weekly_5yr_charts"

# Filter Choice ("Yes", "No", or "ALL")
FILTER_IS_NEW = "No"

# Auto-create subfolders inside project directory based on filter?
# e.g., "weekly_5yr_charts/is_new_yes"
AUTO_SUBFOLDER_BY_FILTER = True

# Delete old graph images inside the target folder before running
DELETE_EXISTING_GRAPHS = True


# ===================================================================
# HELPER: Prepare Target Directory Inside Project Folder
# ===================================================================
def prepare_project_directory(
    folder_name: str,
    is_new_filter: str,
    use_subfolders: bool,
    delete_existing: bool,
) -> str:
  """Creates a folder strictly inside the current working directory."""
  # Get current project directory
  project_dir = os.getcwd()

  # Construct path inside current project
  if use_subfolders:
    target_dir = os.path.join(
        project_dir, folder_name, f"is_new_{is_new_filter.lower()}"
    )
  else:
    target_dir = os.path.join(project_dir, folder_name)

  # Create directory if it doesn't exist
  os.makedirs(target_dir, exist_ok=True)
  print(f"📁 Project Save Path: '{target_dir}'")

  # Delete old graphs inside this specific project subfolder if requested
  if delete_existing:
    existing_files = glob.glob(os.path.join(target_dir, "*.png"))
    if existing_files:
      print(
          f"  -> Cleaning up {len(existing_files)} existing chart(s) in"
          f" '{target_dir}'..."
      )
      for file in existing_files:
        try:
          os.remove(file)
        except Exception as e:
          print(f"  Failed to delete {file}: {e}")
      print("  -> Cleanup complete.")
    else:
      print(f"  -> No existing PNGs found in '{target_dir}'.")

  return target_dir


# ===================================================================
# HELPER: Load Tickers
# ===================================================================
def load_target_tickers(file_path: str, is_new_filter: str) -> list:
  """Reads CSV and extracts ticker symbols based on FILTER_IS_NEW choice."""
  if not os.path.exists(file_path):
    print(f"Error: Input file '{file_path}' does not exist.")
    return []

  df = pd.read_csv(file_path)

  if "Ticker" not in df.columns:
    print(f"Error: 'Ticker' column missing in '{file_path}'.")
    return []

  # Apply Is_New filter
  if is_new_filter.upper() != "ALL":
    if "Is_New" in df.columns:
      df = df[
          df["Is_New"].astype(str).str.strip().str.capitalize()
          == is_new_filter.capitalize()
      ]
    else:
      print("Warning: 'Is_New' column not found. Processing all tickers.")

  tickers = df["Ticker"].dropna().unique().tolist()
  print(
      f"Loaded {len(tickers)} ticker(s) matching Is_New = '{is_new_filter}'"
      f" from '{file_path}'."
  )
  return tickers


# ===================================================================
# HELPER: Fetch 5 Years Weekly Data from Polygon.io
# ===================================================================
def fetch_5yr_weekly_data(ticker: str, api_key: str) -> pd.DataFrame:
  """Fetches 5 years of weekly OHLCV aggregate bars for a single ticker."""
  to_date = pd.Timestamp.now().strftime("%Y-%m-%d")
  from_date = (pd.Timestamp.now() - pd.DateOffset(years=5)).strftime("%Y-%m-%d")

  url = (
      f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/week/{from_date}/{to_date}"
      f"?adjusted=true&sort=asc&apiKey={api_key}"
  )

  try:
    response = requests.get(url)
    data = response.json()

    if (
        data.get("status") == "OK"
        and "results" in data
        and len(data["results"]) > 0
    ):
      df = pd.DataFrame(data["results"])
      # Map Polygon columns: t=timestamp (ms), c=close, o=open, h=high, l=low, v=volume
      df["Date"] = pd.to_datetime(df["t"], unit="ms")
      df = df.rename(
          columns={
              "c": "Close",
              "o": "Open",
              "h": "High",
              "l": "Low",
              "v": "Volume",
          }
      )
      return df[["Date", "Open", "High", "Low", "Close", "Volume"]]

    elif "NOT_AUTHORIZED" in str(data) or "MAX_REQUESTS" in str(data):
      print(f"  Rate limit/Auth issue for {ticker}. Waiting 15 seconds...")
      time.sleep(15)
      return pd.DataFrame()
    else:
      print(f"  No data found for symbol: {ticker}")
      return pd.DataFrame()

  except Exception as e:
    print(f"  HTTP request error for {ticker}: {e}")
    return pd.DataFrame()


# ===================================================================
# HELPER: Generate & Save 5-Year Weekly Chart
# ===================================================================
def plot_and_save_chart(df: pd.DataFrame, ticker: str, output_dir: str):
  """Plots 5-year weekly closing prices with volume sub-chart and saves as PNG."""
  fig, (ax_price, ax_vol) = plt.subplots(
      2,
      1,
      figsize=(12, 6.5),
      gridspec_kw={"height_ratios": [3, 1]},
      sharex=True,
  )

  # 1. Price Subplot
  ax_price.plot(
      df["Date"], df["Close"], color="#1f77b4", linewidth=1.8, label="Weekly Close"
  )
  ax_price.set_title(
      f"{ticker} — 5-Year Weekly Price Trend",
      fontsize=14,
      fontweight="bold",
      pad=12,
  )
  ax_price.set_ylabel("Price ($ / ₹)", fontsize=11)
  ax_price.grid(True, linestyle="--", alpha=0.5)
  ax_price.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))

  # Highlight Highest & Lowest points on chart
  min_row = df.loc[df["Close"].idxmin()]
  max_row = df.loc[df["Close"].idxmax()]

  ax_price.scatter(
      min_row["Date"], min_row["Close"], color="red", s=50, zorder=5
  )
  ax_price.annotate(
      f"Low: {min_row['Close']:.2f}",
      (min_row["Date"], min_row["Close"]),
      textcoords="offset points",
      xytext=(0, -15),
      ha="center",
      fontsize=8,
      bbox=dict(boxstyle="round,pad=0.2", fc="yellow", alpha=0.5),
  )

  ax_price.scatter(
      max_row["Date"], max_row["Close"], color="green", s=50, zorder=5
  )
  ax_price.annotate(
      f"High: {max_row['Close']:.2f}",
      (max_row["Date"], max_row["Close"]),
      textcoords="offset points",
      xytext=(0, 10),
      ha="center",
      fontsize=8,
      bbox=dict(boxstyle="round,pad=0.2", fc="lightgreen", alpha=0.5),
  )

  # 2. Volume Subplot
  ax_vol.bar(df["Date"], df["Volume"], color="#7f7f7f", alpha=0.6, width=5)
  ax_vol.set_ylabel("Volume", fontsize=10)
  ax_vol.set_xlabel("Date", fontsize=11)
  ax_vol.grid(True, linestyle="--", alpha=0.3)
  ax_vol.yaxis.set_major_formatter(mticker.EngFormatter())

  plt.xticks(rotation=0)
  plt.tight_layout()

  # Save chart directly into project folder path
  file_path = os.path.join(output_dir, f"{ticker}_5yr_weekly.png")
  plt.savefig(file_path, dpi=150, bbox_inches="tight")
  plt.close(fig)

  print(f"  -> Saved chart: '{file_path}'")


# ===================================================================
# MAIN WORKFLOW
# ===================================================================
if __name__ == "__main__":
  print("================ 5-YEAR WEEKLY CHART GENERATOR ================\n")

  # Step 1: Set up folder inside current project directory
  target_dir = prepare_project_directory(
      folder_name=FOLDER_NAME,
      is_new_filter=FILTER_IS_NEW,
      use_subfolders=AUTO_SUBFOLDER_BY_FILTER,
      delete_existing=DELETE_EXISTING_GRAPHS,
  )

  # Step 2: Read target tickers filtered by Is_New status
  tickers = load_target_tickers(INPUT_FILE, FILTER_IS_NEW)

  if not tickers:
    print("No tickers available to process. Exiting.")
    exit()

  print(
      f"\nProcessing {len(tickers)} ticker(s) with 12.5s delays for Polygon"
      " Free Tier limits...\n"
  )

  # Step 3: Loop through tickers, fetch data, and save charts
  start_time = time.time()

  for idx, ticker in enumerate(tickers, start=1):
    print(f"[{idx}/{len(tickers)}] Fetching 5Y weekly data for '{ticker}'...")

    df_weekly = fetch_5yr_weekly_data(ticker, API_KEY)

    if not df_weekly.empty:
      plot_and_save_chart(df_weekly, ticker, target_dir)

    # Respect Polygon Free Tier Limit (5 calls/min -> 12.5s delay)
    if idx < len(tickers):
      time.sleep(12.5)

  elapsed = (time.time() - start_time) / 60
  print(
      f"\nSUCCESS! Saved {len(tickers)} chart(s) in {elapsed:.1f} minutes inside"
      " your project folder:"
  )
  print(f"📍 '{target_dir}'")
  print("===============================================================")