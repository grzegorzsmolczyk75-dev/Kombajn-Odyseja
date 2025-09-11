import os
import json
from binance.client import Client
from binance.exceptions import BinanceAPIException

# Zdefiniuj ścieżkę do pliku config.json
CONFIG_FILE = 'config.json'

# Proste kolory dla lepszej czytelności w terminalu
class Kolory:
    ZIELONY = '\033[92m'
    CZERWONY = '\033[91m'
    ZOLTY = '\033[93m'
    RESET = '\033[0m'

def sprawdz_klucze_z_json():
    """Funkcja testująca połączenie przy użyciu kluczy z pliku config.json."""
    print("--- Rozpoczynam test kluczy API z pliku config.json ---")

    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        
        # Klucze API w starym config.json prawdopodobnie nie mają prefiksu BINANCE_
        api_key = config.get('api_key') or config.get('API_KEY')
        api_secret = config.get('api_secret') or config.get('API_SECRET')

        if not api_key or not api_secret:
            print(f"{Kolory.CZERWONY}[PORAŻKA]{Kolory.RESET} Nie znaleziono kluczy API w pliku {CONFIG_FILE}.")
            return

        print(f"Klucze API wczytane z {CONFIG_FILE}. Próbuję połączyć się z Binance...")

        client = Client(api_key, api_secret)
        client.futures_account_balance()
        
        print(f"\n{Kolory.ZIELONY}========== SUKCES =========={Kolory.RESET}")
        print(f"Klucze z pliku {Kolory.ZOLTY}{CONFIG_FILE}{Kolory.RESET} są POPRAWNE i udało się pomyślnie połączyć z Twoim kontem Binance.")
        print("To dowodzi, że problemem jest formatowanie lub wczytywanie pliku bot.env!")
        print(f"{Kolory.ZIELONY}==========================={Kolory.RESET}")

    except FileNotFoundError:
        print(f"{Kolory.CZERWONY}[PORAŻKA]{Kolory.RESET} Nie znaleziono pliku konfiguracyjnego: {CONFIG_FILE}")
    except BinanceAPIException as e:
        print(f"\n{Kolory.CZERWONY}========== PORAŻKA =========={Kolory.RESET}")
        print(f"Binance odrzuciło połączenie przy użyciu kluczy z {Kolory.ZOLTY}{CONFIG_FILE}{Kolory.RESET}.")
        print(f"Komunikat błędu od Binance: {Kolory.CZERWONY}{e}{Kolory.RESET}")
        print(f"{Kolory.CZERWONY}==========================={Kolory.RESET}")
    except Exception as e:
        print(f"\n{Kolory.CZERWONY}========== PORAŻKA =========={Kolory.RESET}")
        print(f"Wystąpił nieoczekiwany błąd: {e}")
        print(f"{Kolory.CZERWONY}==========================={Kolory.RESET}")

if __name__ == "__main__":
    sprawdz_klucze_z_json()
