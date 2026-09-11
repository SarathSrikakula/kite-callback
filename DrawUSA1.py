import glob
import os
import time
from typing import Optional, Tuple
import duckdb
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import requests

# ===================================================================
# CONFIGURATION
# ===================================================================
API_KEY = "J35wnk4eNZEioisPriHivFBlefFd9dfb"
INPUT_FILE_BASE = "filled_us_stocks"
DB_FILE = "us_stocks_5yr.duckdb"  # Path to your DuckDB database

# Output directory name created inside current project folder
OUTPUT_FOLDER = "weekly_5yr_charts_by_category_usa"

# 🎯 EDIT THIS ARRAY TO PICK WHICH CATEGORIES TO PROCESS
SELECTED_CATEGORIES =["su", "vsu", "g","vg","i"]

# Save charts inside separate category subfolders?
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


# ===================================================================
# HELPER 1: Dynamically Fetch Data from DuckDB & Detect Latest Date
# ===================================================================
def fetch_duckdb_data_dynamic(
    ticker: str, start_date_str: str, db_file: str
) -> Tuple[pd.DataFrame, Optional[str]]:
  """Fetches historical data up to the max date present in DuckDB for a ticker.

  Returns tuple: (DataFrame, max_date_string)
  """
  if not os.path.exists(db_file):
    print(f"  ⚠️ Database '{db_file}' not found. Skipping DB fetch.")
    return pd.DataFrame(), None

  try:
    con = duckdb.connect(db_file, read_only=True)

    # Find the maximum date stored for this specific ticker
    max_date_res = con.execute(
        "SELECT MAX(date) FROM daily_stocks WHERE ticker = ?", [ticker]
    ).fetchone()[0]

    if max_date_res is None:
      con.close()
      return pd.DataFrame(), None

    max_date_str = str(max_date_res)

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
  """Fetches daily aggregate bars for recent date range from API."""
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

    elif "NOT_AUTHORIZED" in str(data) or "MAX_REQUESTS" in str(data):
      print(f"  Auth/Limit issue for {ticker}. Waiting 15 seconds...")
      time.sleep(15)
      return pd.DataFrame()
    else:
      print(f"  No data found in response for symbol: {ticker}")
      return pd.DataFrame()

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
# HELPER 4: Plot & Save Chart
# ===================================================================
def plot_and_save_chart(
    df: pd.DataFrame,
    ticker: str,
    category: str,
    base_dir: str,
    create_category_subfolders: bool = True,
) -> bool:
  """Plots weekly closing prices with volume sub-chart and saves as PNG in category directory."""
  if create_category_subfolders:
    save_dir = os.path.join(base_dir, str(category).replace("/", "_").strip())
    os.makedirs(save_dir, exist_ok=True)
  else:
    save_dir = base_dir

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
      f"{ticker} [{category}] — 5-Year Weekly Price Trend (Dynamic DB + API)",
      fontsize=14,
      fontweight="bold",
      pad=12,
  )
  ax_price.set_ylabel("Price ($)", fontsize=11)
  ax_price.grid(True, linestyle="--", alpha=0.5)
  ax_price.yaxis.set_major_formatter(mticker.FormatStrFormatter("$%.2f"))

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

  file_path = os.path.join(save_dir, f"{ticker}_5yr_weekly.png")
  plt.savefig(file_path, dpi=150, bbox_inches="tight")
  plt.close(fig)

  print(f"  -> Saved chart: '{file_path}'")
  return True


# ===================================================================
# MAIN EXECUTION
# ===================================================================
if __name__ == "__main__":
  print("================ TICKER & CATEGORY CHART GENERATOR ================\n")

  base_dir = prepare_output_directory(OUTPUT_FOLDER, DELETE_EXISTING_GRAPHS)
  df_input = load_ticker_category_data(INPUT_FILE_BASE)

  if df_input.empty:
    print("Exiting.")
    exit()

  # Apply category filtering
  if SELECTED_CATEGORIES and "ALL" not in [
      c.upper() for c in SELECTED_CATEGORIES
  ]:
    target_cats = [c.strip().lower() for c in SELECTED_CATEGORIES]
    df_input = df_input[
        df_input["Category"]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(target_cats)
    ]
    print(f"🎯 Filtered for Categories: {SELECTED_CATEGORIES}")

  if df_input.empty:
    print("❌ No matching categories found in the input file.")
    exit()

  today = pd.Timestamp.now()
  five_yrs_ago = (today - pd.DateOffset(years=5)).strftime("%Y-%m-%d")
  today_str = today.strftime("%Y-%m-%d")

  print(f"\n📅 Date Range Target: {five_yrs_ago} to {today_str}")
  print(f"Processing {len(df_input)} stock(s)...\n")

  saved = 0
  total_stocks = len(df_input)

  for idx, (_, row) in enumerate(df_input.iterrows(), start=1):
    raw_ticker = str(row["Ticker"]).strip().upper()
    category = str(row["Category"]).strip()

    print(
        f"[{idx}/{total_stocks}] [{category}] Processing ticker '{raw_ticker}'..."
    )

    # 1. Dynamically fetch DB data up to ticker's MAX(date)
    df_db, max_db_date = fetch_duckdb_data_dynamic(
        raw_ticker, five_yrs_ago, DB_FILE
    )

    # 2. Determine API start date dynamically
    if max_db_date is not None:
      api_start_date = (
          pd.to_datetime(max_db_date) + pd.Timedelta(days=1)
      ).strftime("%Y-%m-%d")
      print(
          f"  -> DB data up to {max_db_date}. Pulling API from {api_start_date}"
          f" to {today_str}..."
      )
    else:
      api_start_date = five_yrs_ago
      print(
          f"  -> Ticker not in DB. Pulling full range ({api_start_date} to"
          f" {today_str}) from API..."
      )

    # 3. Fetch missing date range from API (if api_start_date <= today_str)
    df_api = pd.DataFrame()
    if api_start_date <= today_str:
      df_api = fetch_api_daily_data(
          raw_ticker, api_start_date, today_str, API_KEY
      )

    # 4. Combine both sources
    df_combined_daily = pd.concat([df_db, df_api], ignore_index=True)

    if not df_combined_daily.empty:
      # 5. Resample daily records to 5-year weekly bars
      df_weekly = resample_to_weekly(df_combined_daily)

      if not df_weekly.empty:
        if plot_and_save_chart(
            df_weekly,
            raw_ticker,
            category,
            base_dir,
            CREATE_CATEGORY_SUBFOLDERS,
        ):
          saved += 1

    # Respect API rate limits between requests
    if not df_api.empty:
      time.sleep(0.5)

  print(f"\n✅ Done! {saved} chart(s) created in:")
  print(f"📍 '{base_dir}'")
  print("===================================================================")