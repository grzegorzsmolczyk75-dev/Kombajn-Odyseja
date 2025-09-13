import pandas as pd
from binance.client import Client
from datetime import datetime
import logging
import os

# --- KONFIGURACJA ---
SYMBOL = 'WLDUSDC'
INTERVAL = Client.KLINE_INTERVAL_1HOUR  # Możesz zmienić na: 1m, 5m, 15m, 1d etc.
START_DATE = "1 year ago UTC"          # Okres do pobrania, np. "1 day ago UTC", "1 month ago UTC"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILENAME = os.path.join(BASE_DIR, f"{SYMBOL}_{INTERVAL}_data_1_rok.csv")

# Ustawienie logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_all_historical_data(symbol, interval, start_str):
    """
    Pobiera wszystkie dostępne dane historyczne dla danego symbolu i interwału,
    automatycznie obsługując limit 1000 świec na zapytanie.
    """
    client = Client()
    klines = []

    logging.info("Nawiązuję połączenie z Binance...")
    # Używamy generatora, który automatycznie obsługuje pobieranie danych w pętlach
    for k in client.get_historical_klines_generator(symbol, interval, start_str):
        klines.append(k)
        # Opcjonalnie: informacja o postępie
        if len(klines) % 1000 == 0:
            logging.info(f"Pobrano już {len(klines)} świec...")

    return klines

def process_and_save_data(klines, filename):
    """
    Przetwarza surowe dane, czyści je i zapisuje do pliku CSV.
    """
    if not klines:
        logging.warning("Nie pobrano żadnych danych. Zatrzymuję przetwarzanie.")
        return

    # Tworzymy DataFrame i nadajemy czytelne nazwy kolumnom
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])

    # Konwersja na odpowiednie typy danych
    numeric_cols = ['open', 'high', 'low', 'close', 'volume']
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')

    # Konwersja timestamp na czytelną datę
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

    # Wybieramy i porządkujemy tylko te kolumny, których potrzebujemy
    final_df = df[['datetime', 'open', 'high', 'low', 'close', 'volume']]

    try:
        # Zapis do pliku CSV
        final_df.to_csv(filename, index=False)
        logging.info(f"Pomyślnie zapisano {len(final_df)} rekordów do pliku '{filename}'.")
    except Exception as e:
        logging.error(f"Nie udało się zapisać pliku: {e}")

if __name__ == '__main__':
    logging.info(f"Rozpoczynam pobieranie danych historycznych dla {SYMBOL}...")
    logging.info(f"Interwał: {INTERVAL}, Okres: {START_DATE}")

    historical_data = fetch_all_historical_data(SYMBOL, INTERVAL, START_DATE)
    process_and_save_data(historical_data, FILENAME)

    logging.info("Zadanie zakończone.")
