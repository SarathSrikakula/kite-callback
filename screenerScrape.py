import requests
from bs4 import BeautifulSoup
import re
import time
import csv
import os

# --- CONFIGURATION ---
max_pages=40
CSV_FILENAME = "scraped_data.csv"
APPEND_MODE = False  # If True, keeps old data. If False, wipes at start.
COOKIE = 'csrftoken=b6vRC5VjlyeFPYyxO9r4UkKp6qQhW503; sessionid=rt7uyd3vlc7d2aj4f4vox2ofzczqn4af'
#Return over 1month   < -9% AND Volume > 100000
#QUERY_URL = "https://www.screener.in/screen/raw/?sort=&order=&source_id=&query=Return+over+1month+++%3C+-9%25+AND%0D%0A%0D%0AVolume+%3E+100000"

QUERY_URL = "https://www.screener.in/screen/raw/?sort=name&order=asc&source_id=&query=Market+capitalization+%3E+378.85"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Cookie': COOKIE
}


def wipe_files_completely():
    """Removes the file to start fresh if APPEND_MODE is False."""
    if os.path.exists(CSV_FILENAME):
        try:
            os.remove(CSV_FILENAME)
            print(f"Wiping existing file: {CSV_FILENAME}... Done.")
        except Exception as e:
            print(f"Error wiping file: {e}")


def get_company_data(base_url):
    """Scrapes all pages from Screener.in."""
    all_names = []

    # 1. Check Auth and get Max Pages
    response = requests.get(f"{base_url}&page=1", headers=HEADERS)
    if "unregistered" in response.text:
        print("⚠️ ERROR: 'unregistered' detected. Your sessionid might be expired!")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    page_info = soup.find('div', class_='sub')
    if not page_info:
        print("No results found or page structure changed.")
        return []

    match = re.search(r'page \d+ of (\d+)', page_info.get_text())
    total_pages = int(match.group(1)) if match else 1
    print(f"Found {total_pages} pages to scrape.")

    # 2. Iterate Pages
    all_companies = []  # Changed to store tuples (name, market_cap)
    for page in range(1, max_pages + 1):
        print(f"Scraping Page {page}/{total_pages}...")
        res = requests.get(f"{base_url}&page={page}", headers=HEADERS)
        page_soup = BeautifulSoup(res.text, 'html.parser')

        rows = page_soup.find_all('tr', attrs={'data-row-company-id': True})
        for row in rows:
            cells = row.find_all('td')

            # Ensure we have enough cells to access index 4
            if len(cells) > 4:
                name = cells[1].get_text(strip=True)

                # Extract and clean Market Cap (removing commas/symbols)
                mcap_raw = cells[4].get_text(strip=True).replace(',', '')
                try:
                    mcap_val = float(mcap_raw)
                except ValueError:
                    mcap_val = 0.0  # Fallback if data is missing

                # Add to list as a dictionary or tuple
                all_companies.append({'name': name, 'mcap': mcap_val})

        time.sleep(1)

    # 1. Sort the list by 'mcap' in descending order
    all_companies.sort(key=lambda x: x['mcap'], reverse=True)

    # 2. Extract just the names for the final return (if you only want names)
    all_names = [company['name'] for company in all_companies]



    return all_names


def save_and_clean_data(new_names):
    """Saves to CSV and ensures no duplicates remain."""
    existing_data = set()

    # 1. If appending, read current file first
    if APPEND_MODE and os.path.exists(CSV_FILENAME):
        with open(CSV_FILENAME, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                if row: existing_data.add(row[0])

    # 2. Add new names to the set (sets automatically ignore duplicates)
    #for name in new_names:
    #    existing_data.add(name)
    existing_data = list(dict.fromkeys(new_names))

    # 3. Write back to file
    with open(CSV_FILENAME, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Company Name"])  # Header
        for name in list(existing_data):  # Sorted alphabetically
            writer.writerow([name])

    print(f"✅ Final file saved with {len(existing_data)} unique companies.")


# --- EXECUTION ---
if __name__ == "__main__":
    # Wipe if we don't want to append
    if not APPEND_MODE:
        wipe_files_completely()

    # Run Scraper
    scraped_names = get_company_data(QUERY_URL)

    if scraped_names:
        # Save and Deduplicate
        save_and_clean_data(scraped_names)
    else:
        print("No names were scraped. Check your Cookie or Query.")