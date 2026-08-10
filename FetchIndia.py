import io
import json
import ssl
import sys
import urllib.request
import pandas as pd
import yfinance as yf

# Force unbuffered terminal output so prints appear instantly
sys.stdout.reconfigure(line_buffering=True)


def fetch_nse_tickers_and_isins():
  """Fetches all NSE tickers and their ISIN codes for deduplication."""
  url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
  print("[1/4] Connecting to NSE India...", flush=True)

  req = urllib.request.Request(
      url,
      headers={
          "User-Agent": (
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
              " (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
          )
      },
  )

  try:
    with urllib.request.urlopen(req, timeout=15) as response:
      csv_data = response.read()

    df = pd.read_csv(io.BytesIO(csv_data))
    df.columns = df.columns.str.strip()

    symbols = [f"{s.strip()}.NS" for s in df["SYMBOL"].dropna().unique()]

    isin_col = [c for c in df.columns if "ISIN" in c.upper()]
    nse_isins = set()
    if isin_col:
      nse_isins = set(df[isin_col[0]].dropna().str.strip().unique())

    print(
        f"  -> NSE Master: Found {len(symbols):,} listed securities"
        f" ({len(nse_isins):,} ISINs).",
        flush=True,
    )
    return symbols, nse_isins

  except Exception as e:
    print(f"  -> Error fetching NSE master list: {e}", flush=True)
    return [], set()


def fetch_bse_exclusive_tickers(nse_isins):
  """Fetches active BSE scrips and keeps ONLY those NOT already listed on NSE."""
  url = "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w?Group=&Scrip_code=&industry=&segment=Equity&status=Active"
  print("[2/4] Connecting to BSE India API...", flush=True)

  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
      ),
      "Accept": "application/json, text/plain, */*",
      "Accept-Language": "en-US,en;q=0.9",
      "Referer": "https://www.bseindia.com/",
      "Origin": "https://www.bseindia.com",
  }

  req = urllib.request.Request(url, headers=headers)
  context = ssl._create_unverified_context()

  try:
    with urllib.request.urlopen(req, context=context, timeout=15) as response:
      raw_content = response.read().decode("utf-8").strip()

      if not (raw_content.startswith("[") or raw_content.startswith("{")):
        print(
            "  -> BSE anti-bot filter blocked API. Skipping BSE-only stocks.",
            flush=True,
        )
        return []

      data = json.loads(raw_content)

    bse_df = pd.DataFrame(data)
    total_bse = len(bse_df)

    bse_exclusive_tickers = []
    duplicates_skipped = 0

    for _, row in bse_df.iterrows():
      scrip_code = str(row.get("Scrip_Code", "")).strip()
      isin = str(row.get("ISIN_NUMBER", "")).strip()

      if not scrip_code or scrip_code == "nan":
        continue

      if isin and isin in nse_isins:
        duplicates_skipped += 1
      else:
        bse_exclusive_tickers.append(f"{scrip_code}.BO")

    print(
        f"  -> BSE Master: Found {total_bse:,} active securities.", flush=True
    )
    print(
        f"  -> Skipped {duplicates_skipped:,} dual-listed duplicates.",
        flush=True,
    )
    print(
        f"  -> Added {len(bse_exclusive_tickers):,} BSE-exclusive stocks.",
        flush=True,
    )

    return bse_exclusive_tickers

  except Exception as e:
    print(
        f"  -> Could not fetch BSE scrips ({e}). Proceeding with NSE only.",
        flush=True,
    )
    return []


def download_all_combined_indian_stocks(
    output_file="all_indian_stocks_6mo.csv",
):
  """Fetches NSE + BSE exclusive stocks, downloads 6M price data, and exports clean CSV."""
  print(
      "\n================ STARTING INDIAN STOCK DATA FETCH ================\n",
      flush=True,
  )

  # 1. Fetch NSE Tickers + ISIN set
  nse_tickers, nse_isins = fetch_nse_tickers_and_isins()

  # 2. Fetch BSE Exclusive Tickers (deduplicated)
  bse_tickers = fetch_bse_exclusive_tickers(nse_isins)

  # 3. Combine unique tickers across both exchanges
  all_tickers = nse_tickers + bse_tickers
  total_unique_companies = len(all_tickers)

  if not all_tickers:
    print("[ERROR] No tickers retrieved. Aborting.", flush=True)
    return

  print(
      f"\n[3/4] TOTAL UNIQUE TICKERS TO FETCH: {total_unique_companies:,}\n",
      flush=True,
  )

  # 4. Batch Download from Yahoo Finance (chunks of 1,000)
  chunk_size = 70
  all_records = []

  print(
      "[4/4] Downloading 6 months of historical prices from Yahoo"
      " Finance...",
      flush=True,
  )

  for i in range(0, total_unique_companies, chunk_size):
    chunk = all_tickers[i : i + chunk_size]
    print(
        f"  -> Downloading Batch {i//chunk_size + 1} of"
        f" {-(-total_unique_companies // chunk_size)} ({len(chunk)} tickers)...",
        flush=True,
    )

    try:
      df_raw = yf.download(
          tickers=chunk,
          period="6mo",
          interval="1d",
          group_by="ticker",
          threads=True,
          progress=False,
      )

      for ticker in chunk:
        try:
          if (
              isinstance(df_raw.columns, pd.MultiIndex)
              and ticker in df_raw.columns.levels[0]
          ):
            df_ticker = df_raw[ticker].dropna(how="all").copy()
          elif not isinstance(df_raw.columns, pd.MultiIndex):
            df_ticker = df_raw.dropna(how="all").copy()
          else:
            continue

          if df_ticker.empty:
            continue

          df_ticker = df_ticker.reset_index()

          df_ticker["Ticker"] = ticker.replace(".NS", "").replace(
              ".BO", "_BSE"
          )
          df_ticker["Date"] = pd.to_datetime(df_ticker["Date"]).dt.strftime(
              "%Y-%m-%d"
          )

          df_ticker = df_ticker.rename(
              columns={
                  "Open": "Open",
                  "High": "High",
                  "Low": "Low",
                  "Close": "Close",
                  "Volume": "Volume",
              }
          )

          cols = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"]
          df_ticker = df_ticker[[c for c in cols if c in df_ticker.columns]]

          all_records.append(df_ticker)
        except Exception:
          continue
    except Exception as e:
      print(f"  -> Error on batch download: {e}", flush=True)

  # 5. Export and Summarize
  if all_records:
    print("\nSaving data to CSV...", flush=True)
    final_df = pd.concat(all_records, ignore_index=True)
    final_df.to_csv(output_file, index=False)

    successful_count = final_df["Ticker"].nunique()

    print(
        "\n================ UNIFIED FETCH SUMMARY REPORT ================",
        flush=True,
    )
    print(
        f"1. Total Unique Companies Combined:   {total_unique_companies:,}",
        flush=True,
    )
    print(
        f"2. Successful Yahoo Downloads:        {successful_count:,}",
        flush=True,
    )
    print(
        f"3. Total Daily Rows Saved:            {len(final_df):,}",
        flush=True,
    )
    print(f"4. Saved Output File:                 '{output_file}'", flush=True)
    print(
        "==============================================================\n",
        flush=True,
    )
  else:
    print("[ERROR] No historical data retrieved.", flush=True)


# =====================================================================
# THIS PART MUST BE AT THE VERY BOTTOM OF THE FILE (UNINDENTED)
# =====================================================================
if __name__ == "__main__":
  print("Script execution started...", flush=True)
  download_all_combined_indian_stocks("all_indian_stocks_6mo.csv")