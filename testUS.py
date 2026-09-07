import glob
import os
import random
import shutil
import time
from typing import Optional, Set, Tuple

import duckdb
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import requests

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 1000)

# ===================================================================
# CONFIGURATION & USER CONTROL VARIABLES
# ===================================================================
TEST_MODE = True

# Control variable to make saving general 5-year weekly charts optional
SAVE_WEEKLY_5YR_CHARTS = False

# Independent control variable for category-based chart generation
SAVE_CATEGORY_CHARTS = True
MAX_CHARTS_PER_CATEGORY = 20  # Set numerical limit (e.g. 20) or None for all tickers

INPUT_FILE = "polygon_all_us_stocks_6mo.csv"
DB_FILE = "us_stocks_5yr.duckdb"
API_KEY = "J35wnk4eNZEioisPriHivFBlefFd9dfb"

OUTPUT_FILE = (
    "test_final_screened_stocks.csv" if TEST_MODE else "final_screened_stocks.csv"
)
EXCEL_OUTPUT_DIR = "test_output_excels" if TEST_MODE else "output_excels"
CHARTS_OUTPUT_DIR = (
    "test_weekly_5yr_charts" if TEST_MODE else "weekly_5yr_charts"
)
CHARTS_CATEGORY_OUTPUT_DIR = (
    "test_weekly_5yr_charts_category" if TEST_MODE else "weekly_5yr_charts_category"
)

FILTER_IS_NEW = "ALL"
AUTO_SUBFOLDER_BY_FILTER = True
DELETE_EXISTING_GRAPHS = True

MIN_ATH_PCT = 2.0
LOOKBACK_MONTHS = 6
INCLUDE_WITH_ATH = True
INCLUDE_WITHOUT_ATH = True


# ===================================================================
# HELPER 1: DATA LOADERS & DIRECTORY MANAGEMENT
# ===================================================================
def load_stock_data(file_path: str) -> pd.DataFrame:
    print(f"📖 Loading input stock data from '{file_path}'...")
    if not file_path.endswith(".csv"):
        file_path += ".csv"
    df = pd.read_csv(file_path)
    df.columns = df.columns.str.strip().str.capitalize()
    df["Date"] = pd.to_datetime(df["Date"])
    print(f"   └─ Successfully loaded {len(df):,} rows covering {df['Ticker'].nunique():,} unique tickers.")
    return df


def get_existing_tickers(output_file: str) -> Set[str]:
    print(f"🔍 Checking for historical tracking file: '{output_file}'...")
    if os.path.exists(output_file):
        try:
            prev_df = pd.read_csv(output_file)
            if "Ticker" in prev_df.columns:
                existing = set(prev_df["Ticker"].astype(str).tolist())
                print(f"   └─ Found {len(existing):,} existing ticker(s) in tracking history.")
                return existing
        except Exception as e:
            print(f"   ⚠️ Could not read existing output file ({e}). Treating all tickers as new.")
    else:
        print("   └─ No previous tracking file found. All screened tickers will be marked as 'Is_New = Yes'.")
    return set()


def clean_test_environment() -> None:
    if TEST_MODE:
        print("\n🧹 [TEST MODE ACTIVE] Cleaning up previous test directories and artifacts...")
        if os.path.exists(EXCEL_OUTPUT_DIR):
            shutil.rmtree(EXCEL_OUTPUT_DIR)
            print(f"   ├── Removed directory: '{EXCEL_OUTPUT_DIR}'")
        if os.path.exists(CHARTS_OUTPUT_DIR):
            shutil.rmtree(CHARTS_OUTPUT_DIR)
            print(f"   ├── Removed directory: '{CHARTS_OUTPUT_DIR}'")
        if os.path.exists(CHARTS_CATEGORY_OUTPUT_DIR):
            shutil.rmtree(CHARTS_CATEGORY_OUTPUT_DIR)
            print(f"   ├── Removed directory: '{CHARTS_CATEGORY_OUTPUT_DIR}'")
        if os.path.exists(OUTPUT_FILE):
            os.remove(OUTPUT_FILE)
            print(f"   ├── Removed file: '{OUTPUT_FILE}'")
        print("   └── Environment cleanup complete.\n")


def prepare_project_directory(
    folder_name: str,
    is_new_filter: str,
    use_subfolders: bool,
    delete_existing: bool,
) -> str:
    project_dir = os.getcwd()
    if use_subfolders:
        target_dir = os.path.join(
            project_dir, folder_name, f"is_new_{is_new_filter.lower()}"
        )
    else:
        target_dir = os.path.join(project_dir, folder_name)

    os.makedirs(target_dir, exist_ok=True)
    print(f"📁 Chart Output Directory set to: '{target_dir}'")

    if delete_existing:
        existing_files = glob.glob(os.path.join(target_dir, "*.png"))
        if existing_files:
            print(f"   └─ Deleting {len(existing_files)} existing chart file(s)...")
            for file in existing_files:
                try:
                    os.remove(file)
                except Exception as e:
                    print(f"      ⚠️ Failed to delete {file}: {e}")
            print("   └─ Directory cleaned.")

    return target_dir


def export_chunks(
    df: pd.DataFrame,
    folder_path: str,
    file_prefix: str,
    is_new_status: str = "Yes",
    chunk_size: int = 200,
) -> None:
    """Exports data into chunked CSV files and ensures folder directories are created even if empty."""
    os.makedirs(folder_path, exist_ok=True)

    if df.empty or "Is_New" not in df.columns:
        print(f"   ├── Folder created: '{folder_path}' (No input data)")
        return

    filtered_df = df[df["Is_New"] == is_new_status].copy()
    if filtered_df.empty:
        print(f"   ├── Folder created: '{folder_path}' (0 tickers matching Is_New = '{is_new_status}')")
        return

    filtered_df = filtered_df.sort_values(
        by="Current_Price", ascending=False
    ).reset_index(drop=True)

    total_chunks = (len(filtered_df) + chunk_size - 1) // chunk_size
    print(
        f"   ├── Exporting {len(filtered_df)} stocks [Is_New = '{is_new_status}'] "
        f"across {total_chunks} chunk(s) -> '{folder_path}'"
    )

    for i, start_idx in enumerate(range(0, len(filtered_df), chunk_size), start=1):
        chunk_tickers = filtered_df.iloc[start_idx : start_idx + chunk_size]["Ticker"]
        export_df = pd.DataFrame({"Company": chunk_tickers})

        file_path = os.path.join(folder_path, f"{file_prefix}_{i}.csv")
        export_df.to_csv(file_path, index=False)
        print(f"   │   ├── Saved chunk {i}/{total_chunks}: '{file_path}' ({len(export_df)} tickers)")


def export_by_lookback_categories(
    df: pd.DataFrame,
    ath_status_slug: str,  # "with_ath" or "without_ath"
    base_output_dir: str,
) -> None:
    """Dynamically parses all lookback tags present in the dataframe and exports New and Non-New chunks."""
    print(f"\n📂 Processing Categories for ATH State: [{ath_status_slug.upper()}]")

    if df.empty or "Lookback_Period" not in df.columns:
        print("   ⚠️ No input data available to export.")
        return

    # Dynamically extract all distinct tags across comma-separated values in the dataset
    all_periods = set()
    for row_tags in df["Lookback_Period"].dropna().unique():
        for tag in str(row_tags).split(", "):
            if tag.strip():
                all_periods.add(tag.strip())

    for tag in sorted(all_periods):
        # Automatically derive a clean folder slug from the tag string
        # e.g., "for 30 days" -> "30d" | "for 90 days (10d lag)" -> "90d_lag10"
        slug = (
            tag.lower()
            .replace("for ", "")
            .replace(" days", "d")
            .replace(" day", "d")
            .replace(" (", "_")
            .replace(")", "")
            .replace(" ", "_")
        )

        period_df = df[df["Lookback_Period"].astype(str).str.contains(tag, regex=False)].copy()

        print(f"   ├── [{slug}] Processing category '{tag}' ({len(period_df)} ticker(s) total)...")

        # Export New
        export_chunks(
            df=period_df,
            folder_path=os.path.join(base_output_dir, ath_status_slug, f"{slug}_new"),
            file_prefix=f"screened_{ath_status_slug}_{slug}_new",
            is_new_status="Yes",
        )

        # Export Non-New
        export_chunks(
            df=period_df,
            folder_path=os.path.join(base_output_dir, ath_status_slug, f"{slug}_non_new"),
            file_prefix=f"screened_{ath_status_slug}_{slug}_non_new",
            is_new_status="No",
        )


# ===================================================================
# HELPER 2: SCREENING FUNCTIONS
# ===================================================================
def screen_by_low_threshold(
    df: pd.DataFrame,
    min_pct: float = 2.0,
    max_pct: float = 10.0,
    lookback_days: int = 30,
    min_price: float = 1.0,
    min_avg_volume: int = 100000,
    latest_date: Optional[str] = None,
    period_label: Optional[str] = None,
) -> pd.DataFrame:
    tag = period_label if period_label else f"for {lookback_days} days"
    print(f"⏳ Running Screen: Tag='{tag}' | Lookback={lookback_days}d | Max_Date={latest_date or 'Latest'}...")

    latest_excel_rows = df.sort_values("Date").groupby("Ticker").last()

    ref_date = pd.to_datetime(latest_date) if latest_date else df["Date"].max()
    cutoff_date = ref_date - pd.Timedelta(days=lookback_days)

    df_window = df[(df["Date"] >= cutoff_date) & (df["Date"] <= ref_date)].copy()

    results = []

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
        screened_df = screened_df.sort_values("Pct_Above_Low").reset_index(drop=True)

    print(f"   └─ Passed Screen '{tag}': {len(screened_df):,} tickers.")
    return screened_df


def merge_screening_results(dfs: list) -> pd.DataFrame:
    print("\n🔀 Merging results from all screening runs...")
    valid_dfs = [df for df in dfs if df is not None and not df.empty]
    if not valid_dfs:
        print("   ⚠️ No screened candidates found across any lookback period.")
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

                if row_dict.get("Pct_Above_Low", 999) < existing.get("Pct_Above_Low", 999):
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

    print(f"   └─ Consolidated {len(final_df):,} total unique screened ticker(s).")
    return final_df


def filter_by_recent_ath(
    raw_df: pd.DataFrame,
    screened_df: pd.DataFrame,
    min_ath_pct: float = 2.0,
    lookback_months: int = 6,
) -> pd.DataFrame:
    if screened_df.empty:
        return screened_df

    print(f"\n🎯 Screening for 6-Month All-Time Highs (ATH) [Min Pct to High = {min_ath_pct}%]...")
    latest_ref_date = pd.to_datetime(screened_df["Latest_Date"]).max()
    cutoff_date = latest_ref_date - pd.DateOffset(months=lookback_months)

    candidate_tickers = screened_df["Ticker"].unique()

    recent_data = raw_df[
        (raw_df["Ticker"].isin(candidate_tickers))
        & (raw_df["Date"] >= cutoff_date)
        & (raw_df["Date"] <= latest_ref_date)
    ]

    highs_info = pd.DataFrame()
    if not recent_data.empty:
        max_indices = recent_data.groupby("Ticker")["High"].idxmax()
        highs_info = recent_data.loc[max_indices].set_index("Ticker")[["High", "Date"]]

    all_time_highs = raw_df[raw_df["Ticker"].isin(candidate_tickers)].groupby("Ticker")["High"].max()

    filtered_rows = []
    high_col_name = f"{lookback_months}M_High"
    pct_col_name = f"Pct_To_{lookback_months}M_High"

    for idx, row in screened_df.iterrows():
        ticker = row["Ticker"]
        current_price = row["Current_Price"]

        if ticker in highs_info.index and current_price > 0:
            period_high = highs_info.loc[ticker, "High"]
            high_date = pd.to_datetime(highs_info.loc[ticker, "Date"]).strftime("%Y-%m-%d")

            ath_val = all_time_highs.get(ticker)
            is_true_ath = period_high >= ath_val if pd.notna(ath_val) else False

            if is_true_ath:
                pct_to_high = ((period_high - current_price) / current_price) * 100

                if pct_to_high >= min_ath_pct:
                    row_dict = row.to_dict()
                    row_dict[high_col_name] = f"{period_high:.2f} ({high_date})"
                    row_dict[pct_col_name] = round(pct_to_high, 2)
                    filtered_rows.append(row_dict)

    final_df = pd.DataFrame(filtered_rows)
    if not final_df.empty:
        final_df = final_df.reset_index(drop=True)

    print(f"   └─ Identified {len(final_df):,} ticker(s) hitting recent ATH criteria.")
    return final_df


# ===================================================================
# HELPER 3: CHARTING & DATA FETCHING
# ===================================================================
def load_target_tickers(file_path: str, is_new_filter: str) -> list:
    if not os.path.exists(file_path):
        print(f"⚠️ Error: Master tracking file '{file_path}' does not exist.")
        return []

    df = pd.read_csv(file_path)
    if "Ticker" not in df.columns:
        print(f"⚠️ Error: 'Ticker' column missing in '{file_path}'.")
        return []

    if is_new_filter.upper() != "ALL":
        if "Is_New" in df.columns:
            df = df[
                df["Is_New"].astype(str).str.strip().str.capitalize()
                == is_new_filter.capitalize()
            ]

    tickers = df["Ticker"].dropna().unique().tolist()
    print(f"📋 Chart Queue: Loaded {len(tickers)} ticker(s) matching Is_New = '{is_new_filter}' from '{file_path}'.")
    return tickers


def fetch_duckdb_data_dynamic(
    ticker: str, start_date_str: str, db_file: str
) -> Tuple[pd.DataFrame, Optional[str]]:
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
        print(f"   ⚠️ DuckDB read error for {ticker}: {e}")

    return pd.DataFrame(), None


def fetch_api_daily_data(
    ticker: str, start_date_str: str, end_date_str: str, api_key: str
) -> pd.DataFrame:
    url = (
        f"https://api.massive.com/v2/aggs/ticker/{ticker}/range/1/day/{start_date_str}/{end_date_str}"
        f"?adjusted=true&sort=asc&apiKey={api_key}"
    )

    try:
        response = requests.get(url)
        if response.status_code == 429:
            print(f"   ⚠️ Rate limit hit for {ticker}. Pausing execution for 15 seconds...")
            time.sleep(15)
            return fetch_api_daily_data(ticker, start_date_str, end_date_str, api_key)

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
        print(f"   ⚠️ API request error for {ticker}: {e}")

    return pd.DataFrame()


def resample_to_weekly(df_daily: pd.DataFrame) -> pd.DataFrame:
    if df_daily.empty:
        return pd.DataFrame()

    df = df_daily.sort_values("Date").drop_duplicates(subset=["Date"], keep="last")
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


def plot_and_save_chart(df: pd.DataFrame, ticker: str, output_dir: str) -> None:
    fig, (ax_price, ax_vol) = plt.subplots(
        2, 1, figsize=(12, 6.5), gridspec_kw={"height_ratios": [3, 1]}, sharex=True
    )

    ax_price.plot(
        df["Date"], df["Close"], color="#1f77b4", linewidth=1.8, label="Weekly Close"
    )
    ax_price.set_title(
        f"{ticker} — 5-Year Weekly Price Trend",
        fontsize=14,
        fontweight="bold",
        pad=12,
    )
    ax_price.set_ylabel("Price ($)", fontsize=11)
    ax_price.grid(True, linestyle="--", alpha=0.5)
    ax_price.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))

    min_row = df.loc[df["Close"].idxmin()]
    max_row = df.loc[df["Close"].idxmax()]

    ax_price.scatter(min_row["Date"], min_row["Close"], color="red", s=50, zorder=5)
    ax_price.annotate(
        f"Low: ${min_row['Close']:.2f}",
        (min_row["Date"], min_row["Close"]),
        textcoords="offset points",
        xytext=(0, -15),
        ha="center",
        fontsize=8,
        bbox=dict(boxstyle="round,pad=0.2", fc="yellow", alpha=0.5),
    )

    ax_price.scatter(max_row["Date"], max_row["Close"], color="green", s=50, zorder=5)
    ax_price.annotate(
        f"High: ${max_row['Close']:.2f}",
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

    file_path = os.path.join(output_dir, f"{ticker}_weekly.png")
    plt.savefig(file_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def generate_chart_for_ticker(ticker: str, output_dir: str, five_yrs_ago: str, today_str: str) -> bool:
    """Fetches data, resamples, and plots a chart for a single ticker directly into output_dir."""
    df_db, max_db_date = fetch_duckdb_data_dynamic(ticker, five_yrs_ago, DB_FILE)

    if max_db_date is not None:
        api_start_date = (pd.to_datetime(max_db_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        api_start_date = five_yrs_ago

    df_api = pd.DataFrame()
    if api_start_date <= today_str:
        df_api = fetch_api_daily_data(ticker, api_start_date, today_str, API_KEY)

    df_combined_daily = pd.concat([df_db, df_api], ignore_index=True)

    if not df_combined_daily.empty:
        df_weekly = resample_to_weekly(df_combined_daily)
        if not df_weekly.empty:
            plot_and_save_chart(df_weekly, ticker, output_dir)
            return True
    return False


# ===================================================================
# EXECUTION WORKFLOW
# ===================================================================
if __name__ == "__main__":
    print("====================================================================")
    print("      🚀 STEP 1: INITIALIZING SCREENER & EXPORT PIPELINE            ")
    print("====================================================================")

    clean_test_environment()

    previous_tickers = get_existing_tickers(OUTPUT_FILE)
    raw_df = load_stock_data(INPUT_FILE)

    print("\n---------------- RUNNING MULTI-LOOKBACK SCREENS ----------------")
    run_30d = screen_by_low_threshold(
        df=raw_df, min_pct=2.0, max_pct=10.0, lookback_days=30,
        min_price=1.0, min_avg_volume=100000,
        latest_date=(pd.Timestamp.now() - pd.Timedelta(days=5)).strftime("%Y-%m-%d"),
        period_label="for 30 days",
    )

    run_60d = screen_by_low_threshold(
        df=raw_df, min_pct=2.0, max_pct=10.0, lookback_days=60,
        min_price=1.0, min_avg_volume=100000,
        latest_date=(pd.Timestamp.now() - pd.Timedelta(days=5)).strftime("%Y-%m-%d"),
        period_label="for 60 days",
    )

    run_90d = screen_by_low_threshold(
        df=raw_df, min_pct=2.0, max_pct=9.0, lookback_days=90,
        min_price=2.0, min_avg_volume=150000,
        latest_date=(pd.Timestamp.now() - pd.Timedelta(days=7)).strftime("%Y-%m-%d"),
        period_label="for 90 days",
    )

    run_120d = screen_by_low_threshold(
        df=raw_df, min_pct=2.0, max_pct=9.0, lookback_days=120,
        min_price=2.0, min_avg_volume=150000,
        latest_date=(pd.Timestamp.now() - pd.Timedelta(days=7)).strftime("%Y-%m-%d"),
        period_label="for 120 days",
    )

    run_90d10 = screen_by_low_threshold(
        df=raw_df, min_pct=2.0, max_pct=9.0, lookback_days=90,
        min_price=2.0, min_avg_volume=150000,
        latest_date=(pd.Timestamp.now() - pd.Timedelta(days=10)).strftime("%Y-%m-%d"),
        period_label="for 90 days (10d lag)",
    )

    run_120d10 = screen_by_low_threshold(
        df=raw_df, min_pct=2.0, max_pct=9.0, lookback_days=120,
        min_price=2.0, min_avg_volume=150000,
        latest_date=(pd.Timestamp.now() - pd.Timedelta(days=10)).strftime("%Y-%m-%d"),
        period_label="for 120 days (10d lag)",
    )

    run_121d10 = screen_by_low_threshold(
        df=raw_df, min_pct=2.0, max_pct=9.0, lookback_days=121,
        min_price=2.0, min_avg_volume=150000,
        latest_date=(pd.Timestamp.now() - pd.Timedelta(days=10)).strftime("%Y-%m-%d"),
        period_label="for 121 days (10d lag)",
    )

    screened_df = merge_screening_results(
        [run_30d, run_60d, run_90d, run_120d, run_90d10, run_120d10, run_121d10]
    )


    df_with_ath = filter_by_recent_ath(
        raw_df=raw_df, screened_df=screened_df,
        min_ath_pct=MIN_ATH_PCT, lookback_months=LOOKBACK_MONTHS,
    )

    pct_col = f"Pct_To_{LOOKBACK_MONTHS}M_High"
    if not df_with_ath.empty and pct_col in df_with_ath.columns:
        df_with_ath = df_with_ath[df_with_ath[pct_col] <= 50.0].reset_index(drop=True)

    if not df_with_ath.empty:
        df_with_ath["Is_New"] = df_with_ath["Ticker"].apply(
            lambda t: "Yes" if str(t) not in previous_tickers else "No"
        )
        new_cnt = (df_with_ath["Is_New"] == "Yes").sum()
        non_new_cnt = (df_with_ath["Is_New"] == "No").sum()
        print(f"   └─ ATH Candidates Tagged: {new_cnt} New | {non_new_cnt} Non-New")

    if not df_with_ath.empty:
        with_ath_tickers = set(df_with_ath["Ticker"].unique())
        df_without_ath = screened_df[~screened_df["Ticker"].isin(with_ath_tickers)].copy().reset_index(drop=True)
    else:
        df_without_ath = screened_df.copy()

    if not df_without_ath.empty:
        df_without_ath["Is_New"] = df_without_ath["Ticker"].apply(
            lambda t: "Yes" if str(t) not in previous_tickers else "No"
        )
        new_cnt = (df_without_ath["Is_New"] == "Yes").sum()
        non_new_cnt = (df_without_ath["Is_New"] == "No").sum()
        print(f"   └─ Non-ATH Candidates Tagged: {new_cnt} New | {non_new_cnt} Non-New")

    # Master Tracking CSV Export
    print("\n💾 Saving Master Tracking File...")
    dfs_to_concat = []
    if INCLUDE_WITH_ATH and not df_with_ath.empty:
        dfs_to_concat.append(df_with_ath)
    if INCLUDE_WITHOUT_ATH and not df_without_ath.empty:
        dfs_to_concat.append(df_without_ath)

    if dfs_to_concat:
        combined_master_df = pd.concat(dfs_to_concat, ignore_index=True)
        combined_master_df = combined_master_df.sort_values(
            by="Current_Price", ascending=False
        ).reset_index(drop=True)
        combined_master_df.drop(columns=["Lowest_Date"], errors="ignore").to_csv(
            OUTPUT_FILE, index=False
        )
        print(f"   └─ Successfully saved {len(combined_master_df):,} records to '{OUTPUT_FILE}'")

    # Category Chunks Exports
    print("\n---------------- EXPORTING BY LOOKBACK PERIOD CATEGORIES ----------------")
    if INCLUDE_WITH_ATH:
        export_by_lookback_categories(
            df=df_with_ath,
            ath_status_slug="with_ath",
            base_output_dir=EXCEL_OUTPUT_DIR,
        )

    if INCLUDE_WITHOUT_ATH:
        export_by_lookback_categories(
            df=df_without_ath,
            ath_status_slug="without_ath",
            base_output_dir=EXCEL_OUTPUT_DIR,
        )

    # -------------------------------------------------------------------
    # STEP 2: CHART GENERATION PIPELINES
    # -------------------------------------------------------------------
    today = pd.Timestamp.now()
    five_yrs_ago = (today - pd.DateOffset(years=5)).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")

    # --- PIPELINE A: STANDARD FLAT CHART GENERATION ---
    if SAVE_WEEKLY_5YR_CHARTS:
        print("\n====================================================================")
        print("      📊 GENERATING STANDARD 5-YEAR WEEKLY CHARTS                   ")
        print("====================================================================\n")

        target_dir = prepare_project_directory(
            folder_name=CHARTS_OUTPUT_DIR,
            is_new_filter=FILTER_IS_NEW,
            use_subfolders=AUTO_SUBFOLDER_BY_FILTER,
            delete_existing=DELETE_EXISTING_GRAPHS,
        )

        tickers = load_target_tickers(OUTPUT_FILE, FILTER_IS_NEW)
        if tickers:
            saved = 0
            for idx, ticker in enumerate(tickers, start=1):
                if generate_chart_for_ticker(ticker, target_dir, five_yrs_ago, today_str):
                    saved += 1
                    print(f"   ├── [{idx}/{len(tickers)}] Saved '{ticker}_weekly.png' -> '{target_dir}'")
                else:
                    print(f"   ├── [{idx}/{len(tickers)}] ⚠️ Warning: No data for '{ticker}'. Skipped.")

            print(f"\n  🎉 STANDARD CHARTS COMPLETE! Saved {saved}/{len(tickers)} chart(s).")
    else:
        print("\n  ⏭️  SKIPPING STANDARD CHARTS (SAVE_WEEKLY_5YR_CHARTS = False)")

    # --- PIPELINE B: CATEGORY-BASED CHART GENERATION (WITH RANDOM SELECTION & LIMIT) ---
    if SAVE_CATEGORY_CHARTS:
        print("\n====================================================================")
        print(f"  📁 SAVING CATEGORY CHARTS TO '{CHARTS_CATEGORY_OUTPUT_DIR}'")
        if MAX_CHARTS_PER_CATEGORY:
            print(f"  🎲 Sampling Strategy: Randomly choosing up to {MAX_CHARTS_PER_CATEGORY} ticker(s) per category subfolder")
        print("====================================================================\n")

        category_saved_count = 0

        for root, dirs, files in os.walk(EXCEL_OUTPUT_DIR):
            csv_files = [f for f in files if f.endswith(".csv")]
            rel_path = os.path.relpath(root, EXCEL_OUTPUT_DIR)

            if rel_path == ".":
                continue

            category_target_dir = os.path.join(CHARTS_CATEGORY_OUTPUT_DIR, rel_path)
            os.makedirs(category_target_dir, exist_ok=True)

            if DELETE_EXISTING_GRAPHS:
                for old_file in glob.glob(os.path.join(category_target_dir, "*.png")):
                    try:
                        os.remove(old_file)
                    except Exception:
                        pass

            if not csv_files:
                continue

            cat_tickers = []
            for csv_file in csv_files:
                csv_path = os.path.join(root, csv_file)
                try:
                    chunk_df = pd.read_csv(csv_path)
                    if "Company" in chunk_df.columns:
                        cat_tickers.extend(chunk_df["Company"].dropna().astype(str).tolist())
                except Exception as e:
                    print(f"   ⚠️ Could not read {csv_path}: {e}")

            # Deduplicate while retaining a list structure
            cat_tickers = list(set(cat_tickers))

            # Apply random sampling if category size exceeds the cap
            if MAX_CHARTS_PER_CATEGORY is not None and len(cat_tickers) > MAX_CHARTS_PER_CATEGORY:
                cat_tickers = random.sample(cat_tickers, MAX_CHARTS_PER_CATEGORY)

            folder_saved = 0
            for ticker in cat_tickers:
                if generate_chart_for_ticker(ticker, category_target_dir, five_yrs_ago, today_str):
                    folder_saved += 1
                    category_saved_count += 1

            print(f"   ├── Category '{rel_path}': Saved {folder_saved} chart(s) -> '{category_target_dir}'")

        print(f"\n====================================================================")
        print(f"  🎉 CATEGORY GENERATION COMPLETE! Total Saved: {category_saved_count} chart(s).")
        print(f"  📍 Save Location: '{CHARTS_CATEGORY_OUTPUT_DIR}'")
        print("====================================================================")
    else:
        print("\n  ⏭️  SKIPPING CATEGORY CHARTS (SAVE_CATEGORY_CHARTS = False)")