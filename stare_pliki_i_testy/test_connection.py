import os
from binance.client import Client
from dotenv import load_dotenv

print("--- Rozpoczynam prosty test połączenia z Binance ---")

# Ładowanie kluczy z pliku .env
load_dotenv()
api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_SECRET_KEY')

if not api_key or not api_secret:
    print("BŁĄD: Nie znaleziono kluczy API w pliku .env. Upewnij się, że plik istnieje i ma poprawny format.")
else:
    print("Klucze API wczytane pomyślnie.")
    
    try:
        # Tworzenie klienta Binance
        client = Client(api_key, api_secret)
        
        # Najprostsze możliwe zapytanie wymagające uwierzytelnienia: pobranie informacji o koncie
        account_info = client.get_account()
        
        # Jeśli powyższa linia nie zwróci błędu, to znaczy, że jest SUKCES
        print("\n*** SUKCES! Połączenie z API Binance działa poprawnie! ***")
        print("Pomyślnie pobrano informacje o koncie.")
        
        # Dla pewności, spróbujmy jeszcze pobrać saldo USDC
        usdc_balance = client.get_asset_balance(asset='USDC')
        print(f"Twoje saldo USDC: {usdc_balance['free']}")

    except Exception as e:
        print(f"\n--- OSTATECZNY BŁĄD ---")
        print(f"Niestety, nawet najprostszy test połączenia nie powiódł się.")
        print(f"Otrzymany błąd: {e}")
        print("\nTo jest ostateczny dowód, że problem leży po stronie Binance.")

