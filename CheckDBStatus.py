import duckdb
import pandas as pd

# Connect to your DuckDB database
con = duckdb.connect("us_stocks_5yr.duckdb")

# Run the query to get count per day
query = """
    SELECT 
        date, 
        COUNT(ticker) AS total_tickers
    FROM 
        daily_stocks
    GROUP BY 
        date
    ORDER BY 
        date ASC;
"""

df_counts = con.execute(query).df()

# -------------------------------------------------------------------
# 1. Save to CSV for easy inspection in Excel
# -------------------------------------------------------------------
csv_filename = "daily_ticker_counts.csv"
df_counts.to_csv(csv_filename, index=False)
print(f"📁 Daily counts saved to '{csv_filename}'\n")

# -------------------------------------------------------------------
# 2. Print every single row in the console (no truncation)
# -------------------------------------------------------------------
pd.set_option("display.max_rows", None)  # Show all rows
pd.set_option("display.width", 1000)

print("=== TICKER COUNT FOR EVERY DAY ===")
print(df_counts)