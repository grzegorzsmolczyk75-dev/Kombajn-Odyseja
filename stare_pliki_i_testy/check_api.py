import os
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException

# Załaduj zmienne środowiskowe z pliku .env
load_dotenv('bot.env')

# Odczytaj klucze API
api_key = os.environ.get('BINANCE_API_KEY')
api_secret = os.environ.get('BINANCE_API_SECRET')

# Proste kolory dla lepszej czytelności w terminalu
class Kolory:
    ZIELONY = '\033[92m'
    CZERWONY = '\033[91m'
    RESET = '\033[0m'

def sprawdz_klucze():
    """Funkcja testująca połączenie z API Binance."""
    print("--- Rozpoczynam test kluczy API Binance ---")

    if not api_key or not api_secret:
        print(f"{Kolory.CZERWONY}[PORAŻKA]{Kolory.RESET} Nie znaleziono kluczy API w pliku bot.env. Upewnij się, że plik istnieje i zawiera poprawne wpisy.")
        return

    print("Klucze API wczytane. Próbuję połączyć się z Binance...")

    try:
        # Inicjalizacja klienta
        client = Client(api_key, api_secret)
        
        # Wykonanie testowego zapytania (pobranie salda, tak jak w bocie)
        client.futures_account_balance()
        
        # Jeśli powyższa linia nie zwróci błędu, to znaczy, że klucze są poprawne
        print(f"\n{Kolory.ZIELONY}========== SUKCES =========={Kolory.RESET}")
        print("Klucze API są POPRAWNE i udało się pomyślnie połączyć z Twoim kontem Binance.")
        print(f"{Kolory.ZIELONY}==========================={Kolory.RESET}")

    except BinanceAPIException as e:
        # Jeśli wystąpi błąd API, wyświetlamy go
        print(f"\n{Kolory.CZERWONY}========== PORAŻKA =========={Kolory.RESET}")
        print("Binance odrzuciło połączenie. Klucze są NIEPRAWIDŁOWE lub wystąpił inny błąd.")
        print(f"Komunikat błędu od Binance: {Kolory.CZERWONY}{e}{Kolory.RESET}")
        print(f"{Kolory.CZERWONY}==========================={Kolory.RESET}")
        print("\nSprawdź dokładnie, czy klucze w pliku bot.env nie mają literówek / dodatkowych znaków.")

    except Exception as e:
        # Obsługa innych błędów, np. z połączeniem internetowym
        print(f"\n{Kolory.CZERWONY}========== PORAŻKA =========={Kolory.RESET}")
        print(f"Wystąpił nieoczekiwany błąd: {e}")
        print(f"{Kolory.CZERWONY}==========================={Kolory.RESET}")

if __name__ == "__main__":
    sprawdz_klucze()
