import glob
import os
import time
from typing import Optional

import duckdb
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import requests

# ===================================================================
# CONFIGURATION & USER VARIABLES
# ===================================================================
API_KEY = "J35wnk4eNZEioisPriHivFBlefFd9dfb"
INPUT_FILE = "final_screened_stocks.csv"
DB_FILE = "us_stocks_5yr.duckdb"  # Path to your DuckDB database

# -------------------------------------------------------------------
# 📁 PROJECT FOLDER SETTINGS
# -------------------------------------------------------------------
FOLDER_NAME = "weekly_5yr_charts"

# Filter Choice ("Yes", "No", or "ALL")
FILTER_IS_NEW = "No"

# Auto-create subfolders inside project directory based on filter?
AUTO_SUBFOLDER_BY_FILTER = True

# Delete old graph images inside target folder before running?
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
  project_dir = os.getcwd()

  if use_subfolders:
    target_dir = os.path.join(
        project_dir, folder_name, f"is_new_{is_new_filter.lower()}"
    )
  else:
    target_dir = os.path.join(project_dir, folder_name)

  os.makedirs(target_dir, exist_ok=True)
  print(f"📁 Project Save Path: '{target_dir}'")

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
# HELPER 1: Dynamically Fetch Data from DuckDB & Detect Latest Date
# ===================================================================
def fetch_duckdb_data_dynamic(
    ticker: str, start_date_str: str, db_file: str
) -> tuple[pd.DataFrame, Optional[str]]:
  """Fetches all available historical data from start_date_str up to the max date present in DB for a ticker.

  Returns a tuple: (DataFrame, max_date_string)
  """
  if not os.path.exists(db_file):
    print(f"  ⚠️ Database '{db_file}' not found. Skipping DB fetch.")
    return pd.DataFrame(), None

  try:
    con = duckdb.connect(db_file, read_only=True)

    # Check maximum date for this ticker in DuckDB
    max_date_query = """
        SELECT MAX(date) FROM daily_stocks WHERE ticker = ?
    """
    max_date_res = con.execute(max_date_query, [ticker]).fetchone()[0]

    if max_date_res is None:
      con.close()
      return pd.DataFrame(), None

    max_date_str = str(max_date_res)

    # Query all data from 5 years ago up to the ticker's max date
    query = """
        SELECT 
            CAST(date AS VARCHAR) as date_str,
            open AS Open,
            high AS High,
            low AS Low,
            close AS Close,
            volume AS Volume
        FROM daily_stocks
        WHERE ticker = ? AND date >= ? AND date <= ?
        ORDER BY date ASC
    """

    df = con.execute(query, [ticker, start_date_str, max_date_str]).df()
    con.close()

    if not df.empty:
      df["Date"] = pd.to_datetime(df["date_str"])
      return (
          df[["Date", "Open", "High", "Low", "Close", "Volume"]],
          max_date_str,
      )

  except Exception as e:
    print(f"  ⚠️ DuckDB read error for {ticker}: {e}")

  return pd.DataFrame(), None


# ===================================================================
# HELPER 2: Fetch Recent Data from API
# ===================================================================
def fetch_api_daily_data(
    ticker: str, start_date_str: str, end_date_str: str, api_key: str
) -> pd.DataFrame:
  """Fetches daily bars for recent date range from API."""
  url = (
      f"https://api.massive.com/v2/aggs/ticker/{ticker}/range/1/day/{start_date_str}/{end_date_str}"
      f"?adjusted=true&sort=asc&apiKey={api_key}"
  )

  try:
    response = requests.get(url)

    if response.status_code == 429:
      print(f"  ⚠️ Rate limit hit for {ticker}. Waiting 15 seconds...")
      time.sleep(15)
      return fetch_api_daily_data(
          ticker, start_date_str, end_date_str, api_key
      )

    data = response.json()

    if (
        "results" in data
        and isinstance(data["results"], list)
        and len(data["results"]) > 0
    ):
      df = pd.DataFrame(data["results"])
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

  except Exception as e:
    print(f"  HTTP request error for {ticker}: {e}")

  return pd.DataFrame()


# ===================================================================
# HELPER 3: Resample Combined Daily Data to Weekly Bars
# ===================================================================
def resample_to_weekly(df_daily: pd.DataFrame) -> pd.DataFrame:
  """Converts daily OHLCV data into weekly aggregate bars."""
  if df_daily.empty:
    return pd.DataFrame()

  df = df_daily.sort_values("Date").drop_duplicates(
      subset=["Date"], keep="last"
  )
  df.set_index("Date", inplace=True)

  # Resample into weekly bars ending on Friday ('W-FRI')
  weekly_df = (
      df.resample("W-FRI")
      .agg({
          "Open": "first",
          "High": "max",
          "Low": "min",
          "Close": "last",
          "Volume": "sum",
      })
      .dropna()
  )

  return weekly_df.reset_index()


# ===================================================================
# HELPER 4: Generate & Save Weekly Chart
# ===================================================================
def plot_and_save_chart(df: pd.DataFrame, ticker: str, output_dir: str):
  """Plots weekly closing prices with volume sub-chart and saves as PNG."""
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
      f"{ticker} — 5-Year Weekly Price Trend (Dynamic DB + API)",
      fontsize=14,
      fontweight="bold",
      pad=12,
  )
  ax_price.set_ylabel("Price ($)", fontsize=11)
  ax_price.grid(True, linestyle="--", alpha=0.5)
  ax_price.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))

  # Highlight Highest & Lowest points on chart
  min_row = df.loc[df["Close"].idxmin()]
  max_row = df.loc[df["Close"].idxmax()]

  ax_price.scatter(
      min_row["Date"], min_row["Close"], color="red", s=50, zorder=5
  )
  ax_price.annotate(
      f"Low: ${min_row['Close']:.2f}",
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
      f"High: ${max_row['Close']:.2f}",
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

  file_path = os.path.join(output_dir, f"{ticker}_weekly.png")
  plt.savefig(file_path, dpi=150, bbox_inches="tight")
  plt.close(fig)

  print(f"  -> Saved chart: '{file_path}'")


# ===================================================================
# MAIN WORKFLOW
# ===================================================================
if __name__ == "__main__":
  print("================ DYNAMIC 5-YEAR WEEKLY CHART GENERATOR ================\n")

  target_dir = prepare_project_directory(
      folder_name=FOLDER_NAME,
      is_new_filter=FILTER_IS_NEW,
      use_subfolders=AUTO_SUBFOLDER_BY_FILTER,
      delete_existing=DELETE_EXISTING_GRAPHS,
  )

  tickers = load_target_tickers(INPUT_FILE, FILTER_IS_NEW)

  if not tickers:
    print("No tickers available to process. Exiting.")
    exit()

  today = pd.Timestamp.now()
  five_yrs_ago = (today - pd.DateOffset(years=5)).strftime("%Y-%m-%d")
  today_str = today.strftime("%Y-%m-%d")

  print(f"📅 Global Date Range Target: {five_yrs_ago} to {today_str}\n")

  start_time = time.time()
  saved = 0

  for idx, ticker in enumerate(tickers, start=1):
    print(f"[{idx}/{len(tickers)}] Processing '{ticker}'...")

    # 1. Dynamically fetch DB data up to ticker's MAX(date)
    df_db, max_db_date = fetch_duckdb_data_dynamic(
        ticker, five_yrs_ago, DB_FILE
    )

    # 2. Determine API start date dynamically
    if max_db_date is not None:
      # Start API fetch from the day AFTER the DB's latest date
      api_start_date = (
          pd.to_datetime(max_db_date) + pd.Timedelta(days=1)
      ).strftime("%Y-%m-%d")
      print(
          f"  -> DB data found up to {max_db_date}. Pulling API from"
          f" {api_start_date} to {today_str}..."
      )
    else:
      # If ticker doesn't exist in DB at all, fetch full 5 years from API
      api_start_date = five_yrs_ago
      print(
          f"  -> Ticker not in DB. Pulling full range ({api_start_date} to"
          f" {today_str}) from API..."
      )

    # 3. Fetch missing date range from API (if api_start_date <= today)
    df_api = pd.DataFrame()
    if api_start_date <= today_str:
      df_api = fetch_api_daily_data(ticker, api_start_date, today_str, API_KEY)

    # 4. Combine both data sources
    df_combined_daily = pd.concat([df_db, df_api], ignore_index=True)

    if not df_combined_daily.empty:
      # 5. Resample daily records to 5-year weekly bars
      df_weekly = resample_to_weekly(df_combined_daily)

      if not df_weekly.empty:
        plot_and_save_chart(df_weekly, ticker, target_dir)
        saved += 1

    # Respect API rate limits between requests
    if idx < len(tickers) and not df_api.empty:
      time.sleep(0.5)

  elapsed = (time.time() - start_time) / 60
  print(
      f"\nSUCCESS! Saved {saved} chart(s) in {elapsed:.1f} minutes inside:"
  )
  print(f"📍 '{target_dir}'")
  print("===============================================================")