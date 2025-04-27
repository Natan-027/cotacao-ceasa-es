# inspect_form.py
import sys
sys.path.append('/opt/.manus/.sandbox-runtime')
# No data_api needed here, using requests directly
import requests
from bs4 import BeautifulSoup
import traceback

url = "http://200.198.51.71/detec/filtro_boletim_es/filtro_boletim_es.php"
headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36'
}

try:
    print(f"Fetching URL: {url}")
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status() # Raise an exception for bad status codes
    print(f"Status Code: {response.status_code}")
    # The page uses windows-1252 encoding based on meta tag in browser output
    response.encoding = 'windows-1252'
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find the form element
    form = soup.find('form')
    form_action = form.get('action') if form else 'Not Found'
    form_method = form.get('method') if form else 'get' # Default to GET if not specified

    # Find the market select element by looking for the option text
    market_select = None
    market_value = None
    all_selects = soup.find_all('select')
    print(f"Found {len(all_selects)} select elements.")

    for select_tag in all_selects:
        options = select_tag.find_all('option')
        for option in options:
            if 'CEASA GRANDE VITÓRIA' in option.text:
                market_select = select_tag
                market_value = option.get('value')
                break
        if market_select:
            break

    # Find the date select element (assuming it's the next select after market)
    date_select = None
    latest_date_value = None
    if market_select and market_select in all_selects:
        try:
            market_index = all_selects.index(market_select)
            if market_index + 1 < len(all_selects):
                date_select = all_selects[market_index + 1]
        except ValueError:
            pass # market_select not found in list, should not happen if found earlier

    # Try finding date select by a potential name if the positional assumption fails
    if not date_select:
        date_select = soup.find('select', {'name': 'data'}) # Common name guess

    if date_select:
        options = date_select.find_all('option')
        # Find the first non-placeholder option value
        for option in options:
            value = option.get('value')
            # Check if value is not empty or a placeholder indicator
            if value and value.strip() and "Selecione" not in option.text:
                latest_date_value = value
                break # Found the first valid date

    print(f"Form Action: {form_action}")
    print(f"Form Method: {form_method.upper()}") # Convert to upper for clarity
    print(f"Market Select Name: {market_select.get('name') if market_select else 'Not Found'}")
    print(f"Market Value for 'CEASA GRANDE VITÓRIA': {market_value}")
    print(f"Date Select Name: {date_select.get('name') if date_select else 'Not Found'}")
    print(f"Latest Date Value (from initial load): {latest_date_value}") # Expecting None or empty

    # Check for JavaScript that might populate the date field or handle submission
    scripts = soup.find_all('script')
    print(f"Found {len(scripts)} script tags.")
    # for script in scripts:
    #     print(f"Script content (first 100 chars): {script.text[:100]}") # Be careful printing large scripts

except requests.exceptions.RequestException as e:
    print(f"Error fetching URL: {e}")
except Exception as e:
    print(f"An error occurred: {e}")
    traceback.print_exc()

