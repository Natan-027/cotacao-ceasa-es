# inspect_names.py
import sys
sys.path.append("/opt/.manus/.sandbox-runtime")
import requests
from bs4 import BeautifulSoup
import traceback

url = "http://200.198.51.71/detec/filtro_boletim_es/filtro_boletim_es.php"
headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"
}

try:
    print(f"Fetching URL: {url}")
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    response.encoding = "windows-1252"
    soup = BeautifulSoup(response.text, "html.parser")

    # Find select elements. Assume market is first, date is second.
    all_selects = soup.find_all("select")
    print(f"Found {len(all_selects)} select elements.")

    market_select_name = "Not Found"
    date_select_name = "Not Found"

    if len(all_selects) >= 1:
        market_select = all_selects[0]
        market_select_name = market_select.get("name")
        print(f"Market Select (index 0) Name: {market_select_name}")

    if len(all_selects) >= 2:
        date_select = all_selects[1]
        date_select_name = date_select.get("name")
        print(f"Date Select (index 1) Name: {date_select_name}")

    # Find hidden input fields
    hidden_inputs = soup.find_all("input", {"type": "hidden"})
    print(f"\nFound {len(hidden_inputs)} hidden input elements.")
    for hidden_input in hidden_inputs:
        name = hidden_input.get("name")
        value = hidden_input.get("value")
        print(f"  Name: {name}, Value: {value}")

except requests.exceptions.RequestException as e:
    print(f"Error fetching URL: {e}")
except Exception as e:
    print(f"An error occurred: {e}")
    traceback.print_exc()

