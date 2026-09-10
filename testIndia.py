import glob
import os
import shutil
import time
from typing import Optional

import duckdb
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import yfinance as yf

# Set display options so all columns print clearly without wrapping
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 1000)

# ===================================================================
# CONFIGURATION & USER CONTROL VARIABLES (INDIAN MARKET)
# ===================================================================
# --- TEST & OVERWRITE CONTROLS ---
INCLUDE_WITH_ATH = True     # Set to True/False to include/exclude ATH screened stocks
INCLUDE_WITHOUT_ATH = False # Set to True/False to include/exclude non-ATH screened stocks
TEST_MODE = True  # If True: uses 'test_' prefixes & cleans test folders automatically on each run

# --- FILE & DATABASE PATHS ---
INPUT_FILE = "india_nse_bse_stocks_6mo.csv"  # Original Indian stock input source
DB_FILE = "india_stocks_5yr.duckdb"  # Path to local DuckDB historical database

# Dynamic Naming based on TEST_MODE
OUTPUT_FILE = (
    "test_final_screened_stocks_india.csv"
    if TEST_MODE
    else "final_screened_stocks_india.csv"
)
EXCEL_OUTPUT_DIR = "test_output_excels_india" if TEST_MODE else "output_excels_india"
CHARTS_OUTPUT_DIR = (
    "test_weekly_5yr_charts_india" if TEST_MODE else "weekly_5yr_charts_india"
)

# --- CHART GENERATION CONTROLS ---
FILTER_IS_NEW = "ALL"  # Options: "Yes", "No", or "ALL"
AUTO_SUBFOLDER_BY_FILTER = True  # Auto-create subfolders by filter status
DELETE_EXISTING_GRAPHS = True  # Clean chart subfolder before generating new images

# --- SCREENER THRESHOLD CONTROLS ---
MIN_ATH_PCT = 2.0
LOOKBACK_MONTHS = 6


# ===================================================================
# HELPER 1: DATA LOADERS & DIRECTORY MANAGEMENT
# ===================================================================
def load_stock_data(file_path: str) -> pd.DataFrame:
  """Loads CSV stock data and standardizes column headers."""
  if not file_path.endswith(".csv"):
    file_path += ".csv"

  df = pd.read_csv(file_path)
  df.columns = df.columns.str.strip().str.capitalize()
  df["Date"] = pd.to_datetime(df["Date"])
  return df


def get_existing_tickers(output_file: str) -> set:
  """Reads the existing output CSV file (if present) and returns a set of previously screened tickers."""
  if os.path.exists(output_file):
    try:
      prev_df = pd.read_csv(output_file)
      if "Ticker" in prev_df.columns:
        return set(prev_df["Ticker"].astype(str).tolist())
    except Exception as e:
      print(
          f"Note: Could not read existing output file ({e}). Treating all"
          " tickers as new."
      )
  return set()


def clean_test_environment():
  """Cleans up previous test outputs when TEST_MODE is active."""
  if TEST_MODE:
    print("\n🧹 [TEST MODE ACTIVE] Cleaning up previous test directories...")
    if os.path.exists(EXCEL_OUTPUT_DIR):
      shutil.rmtree(EXCEL_OUTPUT_DIR)
      print(f"  -> Removed folder: '{EXCEL_OUTPUT_DIR}'")
    if os.path.exists(CHARTS_OUTPUT_DIR):
      shutil.rmtree(CHARTS_OUTPUT_DIR)
      print(f"  -> Removed folder: '{CHARTS_OUTPUT_DIR}'")
    if os.path.exists(OUTPUT_FILE):
      os.remove(OUTPUT_FILE)
      print(f"  -> Removed file: '{OUTPUT_FILE}'")
    print("  -> Cleanup completed.\n")


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
  print(f"📁 Chart Root Path: '{target_dir}'")

  if delete_existing:
    existing_files = glob.glob(os.path.join(target_dir, "**", "*.png"), recursive=True)
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


def export_chunks(
    df: pd.DataFrame,
    folder_path: str,
    file_prefix: str,
    is_new_status: str = "Yes",
    chunk_size: int = 200,
):
  """Filters for Is_New == is_new_status ('Yes' or 'No'), sorts by Current_Price desc, and exports in 200-symbol CSV chunks."""
  if df.empty or "Is_New" not in df.columns:
    print(f"No records available to export for '{file_prefix}'")
    return

  filtered_df = df[df["Is_New"] == is_new_status].copy()

  if filtered_df.empty:
    print(
        "No tickers found with 'Is_New' =="
        f" '{is_new_status}' for '{file_prefix}'."
    )
    return

  filtered_df = filtered_df.sort_values(
      by="Current_Price", ascending=False
  ).reset_index(drop=True)

  os.makedirs(folder_path, exist_ok=True)

  total_chunks = (len(filtered_df) + chunk_size - 1) // chunk_size
  print(
      f"\nExporting {len(filtered_df)} stocks (Is_New = '{is_new_status}')"
      f" across {total_chunks} file(s) to '{folder_path}'..."
  )

  for i, start_idx in enumerate(range(0, len(filtered_df), chunk_size), start=1):
    chunk_tickers = filtered_df.iloc[start_idx : start_idx + chunk_size][
        "Ticker"
    ]
    export_df = pd.DataFrame({"Company": chunk_tickers})

    file_path = os.path.join(folder_path, f"{file_prefix}_{i}.csv")
    export_df.to_csv(file_path, index=False)
    print(f"  -> Saved {len(export_df)} companies to '{file_path}'")


# ===================================================================
# HELPER 2: SCREENING FUNCTIONS
# ===================================================================
def screen_by_low_threshold(
    df: pd.DataFrame,
    min_pct: float = 2.0,
    max_pct: float = 10.0,
    lookback_days: int = 30,
    min_price: float = 10.0,  # Adjusted default for INR prices
    min_avg_volume: int = 50000,
    latest_date: str = None,
    period_label: str = None,
) -> pd.DataFrame:
  """Screens stocks trading within min_pct and max_pct above their N-day low."""
  latest_excel_rows = df.sort_values("Date").groupby("Ticker").last()

  ref_date = pd.to_datetime(latest_date) if latest_date else df["Date"].max()
  cutoff_date = ref_date - pd.Timedelta(days=lookback_days)

  df_window = df[
      (df["Date"] >= cutoff_date) & (df["Date"] <= ref_date)
  ].copy()

  results = []
  tag = period_label if period_label else f"for {lookback_days} days"

  for ticker, group in df_window.groupby("Ticker"):
    group = group.sort_values("Date")
    if group.empty:
      continue

    latest_ticker_date = group["Date"].iloc[-1]
    current_price = latest_excel_rows.loc[ticker, "Close"]
    price_date_str = pd.to_datetime(
        latest_excel_rows.loc[ticker, "Date"]
    ).strftime("%Y-%m-%d")

    period_low = group["Low"].min()
    avg_volume = group["Volume"].mean()

    # Pre-filters (Price & Volume)
    if current_price < min_price or avg_volume < min_avg_volume:
      continue

    if period_low > 0:
      pct_diff = ((current_price - period_low) / period_low) * 100

      if min_pct <= pct_diff <= max_pct:
        lowest_date = group.loc[group["Low"] == period_low, "Date"].iloc[0]
        lowest_date_str = lowest_date.strftime("%Y-%m-%d")
        low_with_date = f"{period_low:.2f} ({lowest_date_str})"

        results.append({
            "Ticker": ticker,
            "Lookback_Period": tag,
            "Latest_Date": latest_ticker_date.strftime("%Y-%m-%d"),
            "Lowest_Date": lowest_date_str,
            "Current_Price": round(current_price, 2),
            "Price_Date": price_date_str,
            f"{lookback_days}D_Low": low_with_date,
            "Pct_Above_Low": round(pct_diff, 2),
            "Avg_Volume": int(avg_volume),
        })

  screened_df = pd.DataFrame(results)
  if not screened_df.empty:
    screened_df = screened_df.sort_values("Pct_Above_Low").reset_index(
        drop=True
    )

  return screened_df


def merge_screening_results(dfs: list) -> pd.DataFrame:
  """Combines multiple screening DataFrames into a single deduplicated DataFrame."""
  valid_dfs = [df for df in dfs if df is not None and not df.empty]
  if not valid_dfs:
    return pd.DataFrame()

  ticker_map = {}

  for df in valid_dfs:
    for _, row in df.iterrows():
      ticker = row["Ticker"]
      row_dict = row.to_dict()
      tag = row_dict.get("Lookback_Period", "")

      if ticker not in ticker_map:
        row_dict["Lookback_Period"] = [tag] if tag else []
        ticker_map[ticker] = row_dict
      else:
        existing = ticker_map[ticker]

        if tag and tag not in existing["Lookback_Period"]:
          existing["Lookback_Period"].append(tag)

        for col in row_dict:
          if col.endswith("D_Low"):
            existing[col] = row_dict[col]

        if row_dict.get("Pct_Above_Low", 999) < existing.get(
            "Pct_Above_Low", 999
        ):
          existing["Pct_Above_Low"] = row_dict["Pct_Above_Low"]
          existing["Lowest_Date"] = row_dict["Lowest_Date"]

  combined_rows = []
  for ticker, item in ticker_map.items():
    item["Lookback_Period"] = ", ".join(item["Lookback_Period"])
    combined_rows.append(item)

  final_df = pd.DataFrame(combined_rows)

  low_cols = [c for c in final_df.columns if c.endswith("D_Low")]
  for col in low_cols:
    final_df[col] = final_df[col].fillna("-")

  if "Pct_Above_Low" in final_df.columns:
    final_df = final_df.sort_values("Pct_Above_Low").reset_index(drop=True)

  return final_df


def filter_by_recent_ath(
    raw_df: pd.DataFrame,
    screened_df: pd.DataFrame,
    min_ath_pct: float = 2.0,
    lookback_months: int = 6,
) -> pd.DataFrame:
  """Filters out records where peak High over last N months is not at least 'min_ath_pct'% above Current_Price."""
  if screened_df.empty:
    return screened_df

  latest_ref_date = pd.to_datetime(screened_df["Latest_Date"]).max()
  cutoff_date = latest_ref_date - pd.DateOffset(months=lookback_months)

  candidate_tickers = screened_df["Ticker"].unique()
  recent_data = raw_df[
      (raw_df["Ticker"].isin(candidate_tickers))
      & (raw_df["Date"] >= cutoff_date)
      & (raw_df["Date"] <= latest_ref_date)
  ]

  if not recent_data.empty:
    max_indices = recent_data.groupby("Ticker")["High"].idxmax()
    highs_info = recent_data.loc[max_indices].set_index("Ticker")[
        ["High", "Date"]
    ]
  else:
    highs_info = pd.DataFrame()

  filtered_rows = []
  high_col_name = f"{lookback_months}M_High"
  pct_col_name = f"Pct_To_{lookback_months}M_High"

  for idx, row in screened_df.iterrows():
    ticker = row["Ticker"]
    current_price = row["Current_Price"]

    if ticker in highs_info.index and current_price > 0:
      period_high = highs_info.loc[ticker, "High"]
      high_date = pd.to_datetime(highs_info.loc[ticker, "Date"]).strftime(
          "%Y-%m-%d"
      )
      pct_to_high = ((period_high - current_price) / current_price) * 100

      if pct_to_high >= min_ath_pct:
        row_dict = row.to_dict()
        row_dict[high_col_name] = f"{period_high:.2f} ({high_date})"
        row_dict[pct_col_name] = round(pct_to_high, 2)
        filtered_rows.append(row_dict)

  final_df = pd.DataFrame(filtered_rows)
  if not final_df.empty:
    final_df = final_df.reset_index(drop=True)

  return final_df


# ===================================================================
# HELPER 3: CHARTING & LIVE DATA FETCHING (yfinance FOR NSE/BSE)
# ===================================================================
def filter_tickers_by_status(df: pd.DataFrame, is_new_filter: str) -> list:
  """Extracts ticker symbols from a given dataframe based on FILTER_IS_NEW choice."""
  if df.empty or "Ticker" not in df.columns:
    return []

  filtered_df = df.copy()
  if is_new_filter.upper() != "ALL":
    if "Is_New" in filtered_df.columns:
      filtered_df = filtered_df[
          filtered_df["Is_New"].astype(str).str.strip().str.capitalize()
          == is_new_filter.capitalize()
      ]

  return filtered_df["Ticker"].dropna().unique().tolist()


def fetch_duckdb_data_dynamic(
    ticker: str, start_date_str: str, db_file: str
) -> tuple[pd.DataFrame, Optional[str]]:
  """Fetches historical data from DuckDB for an Indian ticker."""
  if not os.path.exists(db_file):
    return pd.DataFrame(), None

  try:
    con = duckdb.connect(db_file, read_only=True)
    max_date_query = "SELECT MAX(date) FROM daily_stocks WHERE ticker = ?"
    max_date_res = con.execute(max_date_query, [ticker]).fetchone()[0]

    if max_date_res is None:
      con.close()
      return pd.DataFrame(), None

    max_date_str = str(max_date_res)
    query = """
        SELECT 
            CAST(date AS VARCHAR) as date_str,
            open AS Open, high AS High, low AS Low, close AS Close, volume AS Volume
        FROM daily_stocks
        WHERE ticker = ? AND date >= ? AND date <= ?
        ORDER BY date ASC
    """
    df = con.execute(query, [ticker, start_date_str, max_date_str]).df()
    con.close()

    if not df.empty:
      df["Date"] = pd.to_datetime(df["date_str"])
      return df[["Date", "Open", "High", "Low", "Close", "Volume"]], max_date_str

  except Exception as e:
    print(f"  ⚠️ DuckDB read error for {ticker}: {e}")

  return pd.DataFrame(), None


def fetch_yfinance_daily_data(
    ticker: str, start_date_str: str, end_date_str: str
) -> pd.DataFrame:
  """Fetches recent NSE/BSE daily bars using Yahoo Finance."""
  try:
    yf_ticker = ticker if ("." in ticker) else f"{ticker}.NS"
    data = yf.download(
        yf_ticker,
        start=start_date_str,
        end=end_date_str,
        progress=False,
        auto_adjust=True,
    )

    if not data.empty:
      if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

      data = data.reset_index()
      data["Date"] = pd.to_datetime(data["Date"])
      return data[["Date", "Open", "High", "Low", "Close", "Volume"]]
  except Exception as e:
    print(f"  ⚠️ yfinance download error for {ticker}: {e}")

  return pd.DataFrame()


def resample_to_weekly(df_daily: pd.DataFrame) -> pd.DataFrame:
  """Resamples daily OHLCV dataframe to weekly bars ending Friday."""
  if df_daily.empty:
    return pd.DataFrame()

  df = df_daily.sort_values("Date").drop_duplicates(
      subset=["Date"], keep="last"
  )
  df.set_index("Date", inplace=True)

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


def plot_and_save_chart(df: pd.DataFrame, ticker: str, output_dir: str):
  """Renders and saves a 5-year weekly line chart in INR (₹) formatting."""
  fig, (ax_price, ax_vol) = plt.subplots(
      2,
      1,
      figsize=(12, 6.5),
      gridspec_kw={"height_ratios": [3, 1]},
      sharex=True,
  )

  ax_price.plot(
      df["Date"], df["Close"], color="#1f77b4", linewidth=1.8, label="Weekly Close"
  )
  ax_price.set_title(
      f"{ticker} — 5-Year Weekly Price Trend (India)",
      fontsize=14,
      fontweight="bold",
      pad=12,
  )
  ax_price.set_ylabel("Price (₹)", fontsize=11)
  ax_price.grid(True, linestyle="--", alpha=0.5)
  ax_price.yaxis.set_major_formatter(mticker.FormatStrFormatter("₹%.2f"))

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
      bbox=dict(boxstyle="round,pad=0.2", fc="yellow", alpha=0.5),
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
      bbox=dict(boxstyle="round,pad=0.2", fc="lightgreen", alpha=0.5),
  )

  ax_vol.bar(df["Date"], df["Volume"], color="#7f7f7f", alpha=0.6, width=5)
  ax_vol.set_ylabel("Volume", fontsize=10)
  ax_vol.set_xlabel("Date", fontsize=11)
  ax_vol.grid(True, linestyle="--", alpha=0.3)
  ax_vol.yaxis.set_major_formatter(mticker.EngFormatter())

  plt.xticks(rotation=0)
  plt.tight_layout()

  clean_ticker_name = ticker.replace(".NS", "").replace(".BO", "")
  file_path = os.path.join(output_dir, f"{clean_ticker_name}_weekly.png")
  plt.savefig(file_path, dpi=150, bbox_inches="tight")
  plt.close(fig)

  print(f"  -> Saved chart: '{file_path}'")


def process_chart_batch(tickers: list, category_label: str, target_dir: str):
  """Generates and saves charts for a given set of tickers into a target folder."""
  if not tickers:
    print(f"\nNo tickers to process for category: '{category_label}'.")
    return 0

  category_folder = os.path.join(target_dir, category_label)
  os.makedirs(category_folder, exist_ok=True)

  today = pd.Timestamp.now()
  five_yrs_ago = (today - pd.DateOffset(years=5)).strftime("%Y-%m-%d")
  today_str = today.strftime("%Y-%m-%d")

  print(
      f"\n--- Generating Charts for '{category_label}' ({len(tickers)}"
      f" ticker(s)) ---"
  )
  print(f"📂 Category Save Path: '{category_folder}'")

  saved_count = 0
  for idx, ticker in enumerate(tickers, start=1):
    print(f"[{idx}/{len(tickers)}] Processing '{ticker}'...")

    df_db, max_db_date = fetch_duckdb_data_dynamic(
        ticker, five_yrs_ago, DB_FILE
    )

    if max_db_date is not None:
      live_start_date = (
          pd.to_datetime(max_db_date) + pd.Timedelta(days=1)
      ).strftime("%Y-%m-%d")
    else:
      live_start_date = five_yrs_ago

    df_live = pd.DataFrame()
    if live_start_date <= today_str:
      df_live = fetch_yfinance_daily_data(ticker, live_start_date, today_str)

    df_combined_daily = pd.concat([df_db, df_live], ignore_index=True)

    if not df_combined_daily.empty:
      df_weekly = resample_to_weekly(df_combined_daily)
      if not df_weekly.empty:
        plot_and_save_chart(df_weekly, ticker, category_folder)
        saved_count += 1

    time.sleep(0.1)

  return saved_count


# ===================================================================
# EXECUTION WORKFLOW
# ===================================================================
if __name__ == "__main__":
  print("================ STEP 1: INITIALIZING INDIAN SCREENER PIPELINE ================")

  # 1. Clean Environment if in TEST_MODE
  clean_test_environment()

  # 2. Check for existing tickers from previous output file
  print(f"Checking for existing results in '{OUTPUT_FILE}'...")
  previous_tickers = get_existing_tickers(OUTPUT_FILE)
  print(f"Found {len(previous_tickers)} ticker(s) from previous run.")

  # 3. Load full raw dataset
  print(f"\nLoading Indian stock data from '{INPUT_FILE}'...")
  raw_df = load_stock_data(INPUT_FILE)

  # -------------------------------------------------------------------
  # SCREENING RUN CONFIGURATION (TESTING 120D PARAMETERS)
  # -------------------------------------------------------------------
  run_30d = screen_by_low_threshold(
      df=raw_df,
      min_pct=2.0,
      max_pct=10.0,
      lookback_days=30,
      min_price=10.0,
      min_avg_volume=50000,
      latest_date=(pd.Timestamp.now() - pd.Timedelta(days=5)).strftime(
          "%Y-%m-%d"
      ),
      period_label="for 30 days",
  )

  run_60d = screen_by_low_threshold(
      df=raw_df,
      min_pct=2.0,
      max_pct=10.0,
      lookback_days=60,
      min_price=10.0,
      min_avg_volume=50000,
      latest_date=(pd.Timestamp.now() - pd.Timedelta(days=5)).strftime(
          "%Y-%m-%d"
      ),
      period_label="for 60 days",
  )

  run_90d = screen_by_low_threshold(
      df=raw_df,
      min_pct=2.0,
      max_pct=9.0,
      lookback_days=90,
      min_price=10.0,
      min_avg_volume=50000,
      latest_date=(pd.Timestamp.now() - pd.Timedelta(days=7)).strftime(
          "%Y-%m-%d"
      ),
      period_label="for 90 days",
  )

  # --- TEST FOCUS: 120-DAY RUNS FOR NSE/BSE ---
  run_120d = screen_by_low_threshold(
      df=raw_df,
      min_pct=2.0,
      max_pct=9.0,
      lookback_days=120,
      min_price=10.0,
      min_avg_volume=50000,
      latest_date=(pd.Timestamp.now() - pd.Timedelta(days=7)).strftime(
          "%Y-%m-%d"
      ),
      period_label="for 120 days",
  )

  run_90d10 = screen_by_low_threshold(
      df=raw_df,
      min_pct=2.0,
      max_pct=9.0,
      lookback_days=90,
      min_price=10.0,
      min_avg_volume=50000,
      latest_date=(pd.Timestamp.now() - pd.Timedelta(days=10)).strftime(
          "%Y-%m-%d"
      ),
      period_label="for 90 days",
  )

  run_120d10 = screen_by_low_threshold(
      df=raw_df,
      min_pct=2.0,
      max_pct=9.0,
      lookback_days=120,
      min_price=10.0,
      min_avg_volume=50000,
      latest_date=(pd.Timestamp.now() - pd.Timedelta(days=10)).strftime(
          "%Y-%m-%d"
      ),
      period_label="for 120 days",
  )

  # COMBINE ALL RUNS
  screened_df = merge_screening_results(
      [run_30d, run_90d, run_60d, run_120d, run_90d10, run_120d10]
  )
  print(
      f"Function 1 Output: {len(screened_df)} total unique candidate stock(s)"
      " found across all runs."
  )

  # -------------------------------------------------------------------
  # ATH FILTER PROCESS
  # -------------------------------------------------------------------
  df_with_ath = filter_by_recent_ath(
      raw_df=raw_df,
      screened_df=screened_df,
      min_ath_pct=MIN_ATH_PCT,
      lookback_months=LOOKBACK_MONTHS,
  )

  pct_col = f"Pct_To_{LOOKBACK_MONTHS}M_High"
  if not df_with_ath.empty and pct_col in df_with_ath.columns:
    df_with_ath = df_with_ath[df_with_ath[pct_col] <= 50.0].reset_index(
        drop=True
    )

  if not df_with_ath.empty:
    df_with_ath["Is_New"] = df_with_ath["Ticker"].apply(
        lambda t: "Yes" if str(t) not in previous_tickers else "No"
    )
    front_cols = ["Ticker", "Is_New", "Lookback_Period"]
    other_cols = [c for c in df_with_ath.columns if c not in front_cols]
    df_with_ath = df_with_ath[front_cols + other_cols].sort_values(
        by="Current_Price", ascending=False
    )

  if not df_with_ath.empty:
    with_ath_tickers = set(df_with_ath["Ticker"].unique())
    df_without_ath = (
        screened_df[~screened_df["Ticker"].isin(with_ath_tickers)]
        .copy()
        .reset_index(drop=True)
    )
  else:
    df_without_ath = screened_df.copy()

  if not df_without_ath.empty:
    df_without_ath["Is_New"] = df_without_ath["Ticker"].apply(
        lambda t: "Yes" if str(t) not in previous_tickers else "No"
    )
    front_cols = ["Ticker", "Is_New", "Lookback_Period"]
    other_cols = [c for c in df_without_ath.columns if c not in front_cols]
    df_without_ath = df_without_ath[front_cols + other_cols].sort_values(
        by="Current_Price", ascending=False
    )

  # SAVE MASTER TRACKING CSV
  dfs_to_concat = []

  if INCLUDE_WITH_ATH and not df_with_ath.empty:
      dfs_to_concat.append(df_with_ath)

  if INCLUDE_WITHOUT_ATH and not df_without_ath.empty:
      dfs_to_concat.append(df_without_ath)

  if dfs_to_concat:
      combined_master_df = pd.concat(dfs_to_concat, ignore_index=True)
  else:
      combined_master_df = pd.DataFrame()

  if not combined_master_df.empty:
    combined_master_df = combined_master_df.sort_values(
        by="Current_Price", ascending=False
    ).reset_index(drop=True)
    combined_master_df.drop(columns=["Lowest_Date"], errors="ignore").to_csv(
        OUTPUT_FILE, index=False
    )
    print(
        "\nSuccessfully saved combined master tracking results"
        f" ({len(combined_master_df)} tickers) to: '{OUTPUT_FILE}'"
    )

  # EXPORT CHUNKS
  export_chunks(
      df=df_without_ath,
      folder_path=f"{EXCEL_OUTPUT_DIR}/without_ath",
      file_prefix="screened_stocks_without_ath_new",
      is_new_status="Yes",
  )
  export_chunks(
      df=df_without_ath,
      folder_path=f"{EXCEL_OUTPUT_DIR}/without_ath_non_new",
      file_prefix="screened_stocks_without_ath_non_new",
      is_new_status="No",
  )
  export_chunks(
      df=df_with_ath,
      folder_path=f"{EXCEL_OUTPUT_DIR}/with_ath",
      file_prefix="screened_stocks_with_ath_new",
      is_new_status="Yes",
  )
  export_chunks(
      df=df_with_ath,
      folder_path=f"{EXCEL_OUTPUT_DIR}/with_ath_non_new",
      file_prefix="screened_stocks_with_ath_non_new",
      is_new_status="No",
  )

  # -------------------------------------------------------------------
  # STEP 2: CATEGORIZED CHART GENERATION PIPELINE FOR INDIAN STOCKS
  # -------------------------------------------------------------------
  print(
      "\n================ STEP 2: GENERATING WEEKLY CHARTS ================\n"
  )

  target_dir = prepare_project_directory(
      folder_name=CHARTS_OUTPUT_DIR,
      is_new_filter=FILTER_IS_NEW,
      use_subfolders=AUTO_SUBFOLDER_BY_FILTER,
      delete_existing=DELETE_EXISTING_GRAPHS,
  )

  # Load tickers dynamically based on user config flags
  tickers_with_ath = (
      filter_tickers_by_status(df_with_ath, FILTER_IS_NEW)
      if INCLUDE_WITH_ATH
      else []
  )
  tickers_without_ath = (
      filter_tickers_by_status(df_without_ath, FILTER_IS_NEW)
      if INCLUDE_WITHOUT_ATH
      else []
  )

  total_saved = 0
  start_time = time.time()

  if INCLUDE_WITH_ATH:
    total_saved += process_chart_batch(
        tickers=tickers_with_ath,
        category_label="with_ath",
        target_dir=target_dir,
    )

  if INCLUDE_WITHOUT_ATH:
    total_saved += process_chart_batch(
        tickers=tickers_without_ath,
        category_label="without_ath",
        target_dir=target_dir,
    )

  elapsed = (time.time() - start_time) / 60
  print(
      f"\nSUCCESS! Saved {total_saved} chart(s) across active categories in"
      f" {elapsed:.1f} minutes inside:"
  )
  print(f"📍 '{target_dir}'")
  print("===============================================================")