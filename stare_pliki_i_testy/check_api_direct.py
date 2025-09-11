import os
from binance.client import Client
from binance.exceptions import BinanceAPIException

# === UWAGA: Wklej swoje klucze BEZPOŚREDNIO tutaj, w cudzysłowach ===
API_KEY = "hzdYJbLTaGKoj6wlzSyVjAV55s6XXJzUr05D78Fl0o2WQPrze020kfba7cPpl2PD"
API_SECRET = "srhtg3khc12HrFu7LUjMu3CiCqoFcImzh8wE01XJ8dOpCAkLmTFXIUKK8Rw4XcNh"

# Proste kolory dla lepszej czytelności w terminalu
class Kolory:
    ZIELONY = '\033[92m'
    CZERWONY = '\033[91m'
    RESET = '\033[0m'

def sprawdz_klucze_bezposrednio():
    print("--- Rozpoczynam BEZPOŚREDNI test kluczy API dla konta MARGIN ---")
    print("Ta metoda całkowicie omija plik .env.")

    try:
        client = Client(API_KEY, API_SECRET)
        margin_account_info = client.get_margin_account()
        
        print(f"\n{Kolory.ZIELONY}========== SUKCES =========={Kolory.RESET}")
        print("Klucze wklejone bezpośrednio do kodu są POPRAWNE!")
        print("To ostateczny dowód, że problem leży w sposobie odczytu pliku bot.env.")
        
        for asset in margin_account_info['userAssets']:
            if asset['asset'] == 'USDC':
                print(f"Saldo USDC na koncie Margin: {Kolory.ZIELONY}{asset['free']}{Kolory.RESET}")
                break
        
        print(f"{Kolory.ZIELONY}==========================={Kolory.RESET}")

    except BinanceAPIException as e:
        print(f"\n{Kolory.CZERWONY}========== PORAŻKA =========={Kolory.RESET}")
        print("Nawet z kluczami wklejonymi bezpośrednio, Binance odrzuciło połączenie.")
        print(f"Komunikat błędu od Binance: {Kolory.CZERWONY}{e}{Kolory.RESET}")
        print("To sugeruje, że problem leży w ustawieniach kluczy na stronie Binance (IP/Uprawnienia).")
        print(f"{Kolory.CZERWONY}==========================={Kolory.RESET}")
    except Exception as e:
        print(f"\n{Kolory.CZERWONY}========== PORAŻKA =========={Kolory.RESET}")
        print(f"Wystąpił nieoczekiwany błąd: {e}")
        print(f"{Kolory.CZERWONY}==========================={Kolory.RESET}")

if __name__ == "__main__":
    sprawdz_klucze_bezposrednio()
