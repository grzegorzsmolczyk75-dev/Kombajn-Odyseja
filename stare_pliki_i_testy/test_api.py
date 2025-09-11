import hmac
import hashlib
import time
import urllib.parse
import requests
import json
import os

# --- SKRYPT DIAGNOSTYCZNY "CHOCHLIK HUNTER" ---

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

print("--- [START DIAGNOSTYKI] ---")

try:
    # 1. Ładowanie konfiguracji
    print("\n[INFO] Ładuję plik config.json...")
    with open(CONFIG_FILE) as f:
        config = json.load(f)
    print("[OK] Konfiguracja załadowana.")

    API_KEY = config.get("api_key")
    SECRET_KEY = config.get("secret_key")

    # 2. Prześwietlenie kluczy (szukanie ukrytych znaków)
    print("\n[INFO] Prześwietlam klucze API...")
    print(f"   > Długość API Key: {len(API_KEY)}")
    print(f"   > Długość Secret Key: {len(SECRET_KEY)}")
    print(f"   > Secret Key w nawiasach: [{SECRET_KEY}]")
    if " " in SECRET_KEY or "\n" in SECRET_KEY or "\r" in SECRET_KEY:
        print("\n   [!!! ALERT !!!] WYKRYTO PODEJRZANE ZNAKI (spacje/nowe linie) W SECRET KEY!")
    else:
        print("   [OK] Wygląda na to, że klucze są czyste.")

    # 3. Próba połączenia z Binance
    base_url = "https://api.binance.com"
    api_path = "/sapi/v1/margin/account"
    params = {'timestamp': int(time.time() * 1000)}
    
    query_string = urllib.parse.urlencode(params)
    signature = hmac.new(SECRET_KEY.encode('utf-8'), msg=query_string.encode('utf-8'), digestmod=hashlib.sha256).hexdigest()
    
    url = f"{base_url}{api_path}?{query_string}&signature={signature}"
    headers = {'X-MBX-APIKEY': API_KEY}

    print(f"\n[INFO] Wysyłam zapytanie testowe do Binance...")
    print(f"   > URL: {url.split('?')[0]}?timestamp=...") # Ukrywam szczegóły
    
    response = requests.get(url, headers=headers)

    # 4. Analiza odpowiedzi od Binance
    print("\n[INFO] Otrzymano odpowiedź od serwera:")
    print(f"   > Status HTTP: {response.status_code}")
    print(f"   > Treść odpowiedzi (RAW):")
    print(response.text)

except FileNotFoundError:
    print("\n[!!! BŁĄD KRYTYCZNY !!!] Nie znaleziono pliku config.json!")
except Exception as e:
    print(f"\n[!!! BŁĄD KRYTYCZNY !!!] Wystąpił nieoczekiwany błąd: {e}")

print("\n--- [KONIEC DIAGNOSTYKI] ---")
