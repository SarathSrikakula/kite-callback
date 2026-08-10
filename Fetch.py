import time
import pandas as pd
import requests

# Insert your free key from Polygon.io
API_KEY = "J35wnk4eNZEioisPriHivFBlefFd9dfb"

# 1. Generate list of business/trading days for the last 6 months
end_date = pd.Timestamp.now()
start_date = end_date - pd.DateOffset(months=6)
trading_days = pd.date_range(start=start_date, end=end_date, freq="B")

all_data = []
print(f"Fetching 6 months of U.S. market data across {len(trading_days)} trading days...", flush=True)

start_time = time.time()

for i, date in enumerate(trading_days, start=1):
    date_str = date.strftime("%Y-%m-%d")

    # Polygon Grouped Daily endpoint returns ALL stocks for date_str
    url = f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{date_str}?adjusted=true&apiKey={API_KEY}"

    try:
        res = requests.get(url)
        data = res.json()

        if data.get("status") == "OK" and "results" in data:
            df_day = pd.DataFrame(data["results"])

            # Map Polygon keys: T=Ticker, o=Open, h=High, l=Low, c=Close, v=Volume
            df_day = df_day.rename(columns={
                "T": "Ticker",
                "o": "Open",
                "h": "High",
                "l": "Low",
                "c": "Close",
                "v": "Volume"
            })
            df_day["Date"] = date_str

            # Filter and order columns
            cols = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"]
            df_day = df_day[[c for c in cols if c in df_day.columns]]

            all_data.append(df_day)
            print(f"[{i}/{len(trading_days)}] {date_str}: Retrived {len(df_day):,} stocks.", flush=True)

        elif "NOT_AUTHORIZED" in str(data) or "MAX_REQUESTS" in str(data):
            print(f"Rate limit hit on {date_str}. Waiting 15 seconds...", flush=True)
            time.sleep(15)
            continue

        else:
            # Weekend / Market Holiday
            print(f"[{i}/{len(trading_days)}] {date_str}: Market Closed / No data.", flush=True)

    except Exception as e:
        print(f"Error on {date_str}: {e}", flush=True)

    # Free Tier Limit: 5 requests per minute -> Sleep 12.5 seconds between calls
    time.sleep(12.5)

# 2. Combine all trading days into a single DataFrame and export
if all_data:
    print("\nCombining all trading days...", flush=True)
    final_df = pd.concat(all_data, ignore_index=True)

    output_file = "polygon_all_us_stocks_6mo.csv"
    final_df.to_csv(output_file, index=False)

    elapsed = (time.time() - start_time) / 60
    print(
        f"\nSUCCESS! Downloaded {len(final_df):,} total records across "
        f"{final_df['Ticker'].nunique():,} stocks in {elapsed:.1f} minutes.",
        flush=True
    )
    print(f"Saved output file to {output_file}", flush=True)
else:
    print("No data retrieved.", flush=True)