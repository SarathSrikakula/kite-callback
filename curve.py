import os
import pandas as pd

# Set display options so all columns print clearly without wrapping
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 1000)


# -------------------------------------------------------------------
# Helper: Data Loader
# -------------------------------------------------------------------
def load_stock_data(file_path: str) -> pd.DataFrame:
  """Loads CSV stock data and standardizes column headers."""
  if not file_path.endswith(".csv"):
    file_path += ".csv"

  df = pd.read_csv(file_path)

  # Standardize column headers
  df.columns = df.columns.str.strip().str.capitalize()
  df["Date"] = pd.to_datetime(df["Date"])
  return df


# -------------------------------------------------------------------
# Helper: Read Previously Screened Tickers
# -------------------------------------------------------------------
def get_existing_tickers(output_file: str) -> set:
  """Reads the existing output CSV file (if present) and returns a set

  of previously screened stock tickers.
  """
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


# -------------------------------------------------------------------
# Helper: Export 200-Symbol Chunks (Filtered by Is_New status)
# -------------------------------------------------------------------
def export_chunks(
    df: pd.DataFrame,
    folder_path: str,
    file_prefix: str,
    is_new_status: str = "Yes",
    chunk_size: int = 200,
):
  """Filters for Is_New == is_new_status ('Yes' or 'No'), sorts by Current_Price desc,

  and exports in 200-symbol single-column 'Company' CSV chunks.
  """
  if df.empty or "Is_New" not in df.columns:
    print(f"No records available to export for '{file_prefix}'")
    return

  # Filter strictly for Is_New == is_new_status & sort by Current_Price descending
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


# -------------------------------------------------------------------
# FUNCTION 1: Single Screen Run
# -------------------------------------------------------------------
def screen_by_low_threshold(
    df: pd.DataFrame,
    min_pct: float = 2.0,
    max_pct: float = 10.0,
    lookback_days: int = 30,
    min_price: float = 1.0,
    min_avg_volume: int = 100000,
    latest_date: str = None,  # Reference date for lookback window
    period_label: str = None,  # Custom label e.g., "for 30 days"
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


# -------------------------------------------------------------------
# HELPER: Merge Any Number of Screening DataFrames
# -------------------------------------------------------------------
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


# -------------------------------------------------------------------
# FUNCTION 2: Lookback High Threshold Filter
# -------------------------------------------------------------------
def filter_by_recent_ath(
    raw_df: pd.DataFrame,
    screened_df: pd.DataFrame,
    min_ath_pct: float = 2.0,
    lookback_months: int = 6,
) -> pd.DataFrame:
  """Filters out records where peak High over last N months is not at least

  'min_ath_pct'% above Current_Price, and adds High + High % columns to output.
  """
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


# -------------------------------------------------------------------
# EXECUTION WORKFLOW
# -------------------------------------------------------------------
if __name__ == "__main__":
  input_file = "polygon_all_us_stocks_6mo.csv"
  output_file = "final_screened_stocks.csv"

  # Configurable Variables
  MIN_ATH_PCT = 2.0
  LOOKBACK_MONTHS = 6

  # STEP 0: Remember existing tickers from previous output file
  print(f"Checking for existing results in '{output_file}'...")
  previous_tickers = get_existing_tickers(output_file)
  print(f"Found {len(previous_tickers)} ticker(s) from previous run.")

  # 1. Load full raw dataset
  print(f"\nLoading stock data from '{input_file}'...")
  raw_df = load_stock_data(input_file)

  # 2. RUN SCREENER WITH YOUR SPECIFIC PARAMETERS
  run_30d = screen_by_low_threshold(
      df=raw_df,
      min_pct=2.0,
      max_pct=10.0,
      lookback_days=30,
      min_price=1.0,
      min_avg_volume=100000,
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
      min_price=1.0,
      min_avg_volume=100000,
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
      min_price=2.0,
      min_avg_volume=150000,
      latest_date=(pd.Timestamp.now() - pd.Timedelta(days=7)).strftime(
          "%Y-%m-%d"
      ),
      period_label="for 90 days",
  )

  run_120d = screen_by_low_threshold(
      df=raw_df,
      min_pct=2.0,
      max_pct=9.0,
      lookback_days=120,
      min_price=2.0,
      min_avg_volume=150000,
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
      min_price=2.0,
      min_avg_volume=150000,
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
      min_price=2.0,
      min_avg_volume=150000,
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
  # PROVISION B: WITH ATH FILTER (Cap <= 50%)
  # -------------------------------------------------------------------
  df_with_ath = filter_by_recent_ath(
      raw_df=raw_df,
      screened_df=screened_df,
      min_ath_pct=MIN_ATH_PCT,
      lookback_months=LOOKBACK_MONTHS,
  )

  # Enforce Pct_To_6M_High <= 50.0 filter
  pct_col = f"Pct_To_{LOOKBACK_MONTHS}M_High"
  if not df_with_ath.empty and pct_col in df_with_ath.columns:
    df_with_ath = df_with_ath[df_with_ath[pct_col] <= 50.0].reset_index(
        drop=True
    )

  if not df_with_ath.empty:
    df_with_ath["Is_New"] = df_with_ath["Ticker"].apply(
        lambda t: "Yes" if str(t) not in previous_tickers else "No"
    )

    # Reorder columns logically
    front_cols = ["Ticker", "Is_New", "Lookback_Period"]
    other_cols = [c for c in df_with_ath.columns if c not in front_cols]
    df_with_ath = df_with_ath[front_cols + other_cols]

    # Sort by Current_Price descending
    df_with_ath = df_with_ath.sort_values(
        by="Current_Price", ascending=False
    ).reset_index(drop=True)

  # -------------------------------------------------------------------
  # PROVISION A: WITHOUT ATH FILTER (MUTUALLY EXCLUSIVE)
  # Excludes any tickers present in df_with_ath to guarantee zero overlap
  # -------------------------------------------------------------------
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

    # Reorder columns logically
    front_cols = ["Ticker", "Is_New", "Lookback_Period"]
    other_cols = [c for c in df_without_ath.columns if c not in front_cols]
    df_without_ath = df_without_ath[front_cols + other_cols]

    # Sort by Current_Price descending
    df_without_ath = df_without_ath.sort_values(
        by="Current_Price", ascending=False
    ).reset_index(drop=True)

  # -------------------------------------------------------------------
  # PRINT BOTH RESULTS TO CONSOLE
  # -------------------------------------------------------------------
  print("\n================ FINAL SCREENING RESULTS (WITH ATH) ================")
  if not df_with_ath.empty:
    display_with = df_with_ath.drop(columns=["Lowest_Date"], errors="ignore")
    print(f"Passed Screening Check: {len(display_with)} stock(s) matched:\n")
    print(display_with.to_string(index=False))
  else:
    print("No stocks passed all criteria for ATH filter.")
  print("=========================================================\n")

  print("================ FINAL SCREENING RESULTS (WITHOUT ATH) ================")
  if not df_without_ath.empty:
    display_without = df_without_ath.drop(
        columns=["Lowest_Date"], errors="ignore"
    )
    print(f"Passed Screening Check: {len(display_without)} stock(s) matched:\n")
    print(display_without.to_string(index=False))
  else:
    print("No stocks found for WITHOUT ATH criteria.")
  print("=========================================================\n")

  # -------------------------------------------------------------------
  # SAVE MASTER TRACKING CSV (COMBINING BOTH SETS)
  # -------------------------------------------------------------------
  combined_master_df = pd.concat(
      [df_with_ath, df_without_ath], ignore_index=True
  )

  if not combined_master_df.empty:
    combined_master_df = combined_master_df.sort_values(
        by="Current_Price", ascending=False
    ).reset_index(drop=True)
    combined_master_df.drop(columns=["Lowest_Date"], errors="ignore").to_csv(
        output_file, index=False
    )
    print(
        "Successfully saved combined master tracking results"
        f" ({len(combined_master_df)} tickers) to: '{output_file}'"
    )
  else:
    print("No stocks passed screening criteria to save to output_file.")

  # -------------------------------------------------------------------
  # EXPORT 200-SYMBOL CHUNKS TO CSV (NEW AND NON-NEW)
  # -------------------------------------------------------------------

  # --- WITHOUT ATH FILTER ---
  print(
      "\n================ EXPORTING WITHOUT ATH FILTER CHUNKS ================"
  )
  # 1. NEW Stocks (Is_New == "Yes")
  export_chunks(
      df=df_without_ath,
      folder_path="output_excels/without_ath",
      file_prefix="screened_stocks_without_ath_new",
      is_new_status="Yes",
  )

  # 2. NON-NEW Stocks (Is_New == "No")
  export_chunks(
      df=df_without_ath,
      folder_path="output_excels/without_ath_non_new",
      file_prefix="screened_stocks_without_ath_non_new",
      is_new_status="No",
  )

  # --- WITH ATH FILTER ---
  print("\n================ EXPORTING WITH ATH FILTER CHUNKS ================")
  # 1. NEW Stocks (Is_New == "Yes")
  export_chunks(
      df=df_with_ath,
      folder_path="output_excels/with_ath",
      file_prefix="screened_stocks_with_ath_new",
      is_new_status="Yes",
  )

  # 2. NON-NEW Stocks (Is_New == "No")
  export_chunks(
      df=df_with_ath,
      folder_path="output_excels/with_ath_non_new",
      file_prefix="screened_stocks_with_ath_non_new",
      is_new_status="No",
  )

  print(
      "\n===================================================================\n"
  )