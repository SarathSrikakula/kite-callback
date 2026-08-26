import os
import time
import duckdb
import pandas as pd
import requests

API_KEY = "J35wnk4eNZEioisPriHivFBlefFd9dfb"  # Replace with your key
DB_FILE = "us_stocks_5yr.duckdb"
PARQUET_DIR = "data_parquet"

os.makedirs(PARQUET_DIR, exist_ok=True)

# 1. Initialize DuckDB Table
con = duckdb.connect(DB_FILE)
con.execute("""
    CREATE TABLE IF NOT EXISTS daily_stocks (
        ticker VARCHAR,
        date DATE,
        open DOUBLE,
        high DOUBLE,
        low DOUBLE,
        close DOUBLE,
        volume DOUBLE,
        vwap DOUBLE,
        transactions INT,
        PRIMARY KEY (ticker, date)
    )
""")


def fetch_grouped_day(date_str: str) -> pd.DataFrame:
  """Fetches all US stocks for a single trading date."""
  url = (
      f"https://api.massive.com/v2/aggs/grouped/locale/us/market/stocks/{date_str}"
      f"?adjusted=true&apiKey={API_KEY}"
  )

  try:
    resp = requests.get(url)
    if resp.status_code == 429:
      print("  ⚠️ Rate limit hit. Waiting 12 seconds...")
      time.sleep(12)
      return fetch_grouped_day(date_str)

    data = resp.json()
    if "results" in data and len(data["results"]) > 0:
      df = pd.DataFrame(data["results"])

      # Rename Polygon API short-keys to readable column names
      # c: close, o: open, h: high, l: low, v: volume, vw: vwap, n: transactions, T: ticker
      df = df.rename(
          columns={
              "T": "ticker",
              "o": "open",
              "h": "high",
              "l": "low",
              "c": "close",
              "v": "volume",
              "vw": "vwap",
              "n": "transactions",
          }
      )

      df["date"] = date_str

      # Filter down to essential columns
      cols = [
          "ticker",
          "date",
          "open",
          "high",
          "low",
          "close",
          "volume",
          "vwap",
          "transactions",
      ]
      existing_cols = [c for c in cols if c in df.columns]

      return df[existing_cols]

  except Exception as e:
    print(f" Error fetching {date_str}: {e}")

  return pd.DataFrame()


def build_5yr_database():
  # Generate trading dates for the last 5 years (excluding weekends)
  end_date = pd.Timestamp.now()
  start_date = end_date - pd.DateOffset(years=5)

  # Business day range
  date_range = (
      pd.date_range(start=start_date, end=end_date, freq="B")
      .strftime("%Y-%m-%d")
      .tolist()
  )

  print(f"🚀 Starting 5-year download (~{len(date_range)} trading days)...")

  for idx, current_date in enumerate(date_range, 1):
    # Skip if date already exists in DuckDB
    exists = con.execute(
        "SELECT COUNT(*) FROM daily_stocks WHERE date = ?", [current_date]
    ).fetchone()[0]
    if exists > 0:
      continue

    print(f"[{idx}/{len(date_range)}] Fetching market data for {current_date}...")
    df = fetch_grouped_day(current_date)

    if not df.empty:
      # Option A: Save to DuckDB
      con.execute("INSERT OR IGNORE INTO daily_stocks SELECT * FROM df")

      # Option B: Save as Parquet file per day
      #parquet_path = os.path.join(PARQUET_DIR, f"{current_date}.parquet")
      #df.to_parquet(parquet_path, index=False)

    # Respect API rate limits (e.g., 5 calls/min for free tier or unlimited for paid)
    time.sleep(0.2)

  print("\n✅ Download and storage complete!")


if __name__ == "__main__":
  build_5yr_database()