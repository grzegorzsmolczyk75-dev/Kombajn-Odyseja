import os
import json
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException

load_dotenv('bot.env')

api_key = os.environ.get('BINANCE_API_KEY')
api_secret = os.environ.get('BINANCE_API_SECRET')

class Kolory:
    ZIELONY = '\033[92m'
    CZERWONY = '\033[91m'
    RESET = '\033[0m'

def sprawdz_klucze_margin():
    print("--- Rozpoczynam test kluczy API dla konta MARGIN ---")

    if not api_key or not api_secret:
        print(f"{Kolory.CZERWONY}[PORAŻKA]{Kolory.RESET} Nie znaleziono kluczy API w pliku bot.env.")
        return

    print("Klucze API wczytane. Próbuję połączyć się z kontem MARGIN na Binance...")

    try:
        client = Client(api_key, api_secret)
        
        # === KLUCZOWA ZMIANA: Używamy zapytania o konto MARGIN, a nie FUTURES ===
        margin_account_info = client.get_margin_account()
        
        print(f"\n{Kolory.ZIELONY}========== SUKCES =========={Kolory.RESET}")
        print("Klucze API są POPRAWNE i udało się pomyślnie połączyć z Twoim kontem MARGIN.")
        print("Twoja teoria była w 100% trafna. Problem leżał w błędnym zapytaniu API.")
        
        # Wyświetlmy saldo dla pewności
        for asset in margin_account_info['userAssets']:
            if asset['asset'] == 'USDC':
                print(f"Saldo USDC na koncie Margin: {Kolory.ZIELONY}{asset['free']}{Kolory.RESET}")
                break
        
        print(f"{Kolory.ZIELONY}==========================={Kolory.RESET}")

    except BinanceAPIException as e:
        print(f"\n{Kolory.CZERWONY}========== PORAŻKA =========={Kolory.RESET}")
        print("Binance odrzuciło połączenie. Mimo zmiany zapytania, problem nadal występuje.")
        print(f"Komunikat błędu od Binance: {Kolory.CZERWONY}{e}{Kolory.RESET}")
        print(f"{Kolory.CZERWONY}==========================={Kolory.RESET}")
    except Exception as e:
        print(f"\n{Kolory.CZERWONY}========== PORAŻKA =========={Kolory.RESET}")
        print(f"Wystąpił nieoczekiwany błąd: {e}")
        print(f"{Kolory.CZERWONY}==========================={Kolory.RESET}")

if __name__ == "__main__":
    sprawdz_klucze_margin()
