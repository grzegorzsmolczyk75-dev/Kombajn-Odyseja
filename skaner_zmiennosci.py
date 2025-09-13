import pandas as pd
from binance.client import Client
import logging

# --- KONFIGURACJA ---
# Aktywo, do którego porównujemy (np. USDC, USDT)
QUOTE_ASSET = 'USDC'
# Ile ostatnich dni analizujemy
DAYS_TO_ANALYZE = 30
# Minimalny średni wolumen w QUOTE_ASSET, aby odfiltrować mało płynne coiny
MIN_AVG_VOLUME = 1000000 # 1 milion USDC

# Ustawienie logowania, aby ukryć niepotrzebne komunikaty biblioteki
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def analyze_volatility():
    """
    Pobiera wszystkie pary z danym aktywem kwotowanym, analizuje ich
    dzienną zmienność z ostatnich N dni i zwraca posortowaną listę.
    """
    client = Client()
    logging.info("Pobieram listę wszystkich par handlowych z Binance...")
    
    try:
        exchange_info = client.get_exchange_info()
    except Exception as e:
        logging.error(f"Nie udało się pobrać informacji z giełdy: {e}")
        return

    # Filtrujemy tylko te pary, które są w obrocie i kończą się na nasze QUOTE_ASSET
    symbols = [
        s['symbol'] for s in exchange_info['symbols'] 
        if s['status'] == 'TRADING' and s['symbol'].endswith(QUOTE_ASSET)
    ]
    
    logging.info(f"Znaleziono {len(symbols)} par z {QUOTE_ASSET}. Rozpoczynam analizę zmienności...")
    
    results = []
    
    for i, symbol in enumerate(symbols, 1):
        try:
            # Pobieramy dane dzienne (1d) z ostatnich N dni
            klines = client.get_historical_klines(
                symbol, Client.KLINE_INTERVAL_1DAY, f"{DAYS_TO_ANALYZE} days ago UTC"
            )
            
            if len(klines) < DAYS_TO_ANALYZE:
                logging.warning(f"[{i}/{len(symbols)}] Pomijam {symbol}: za mało danych historycznych ({len(klines)} dni).")
                continue

            # Tworzymy DataFrame z danymi
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
                'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume',
                'taker_buy_quote_asset_volume', 'ignore'
            ])

            # Konwertujemy kolumny na typ numeryczny
            df[['high', 'low', 'quote_asset_volume']] = df[['high', 'low', 'quote_asset_volume']].apply(pd.to_numeric)
            
            # Sprawdzamy, czy średni wolumen jest wystarczający
            avg_volume = df['quote_asset_volume'].mean()
            if avg_volume < MIN_AVG_VOLUME:
                logging.info(f"[{i}/{len(symbols)}] Pomijam {symbol}: zbyt niski wolumen ({avg_volume:,.0f} {QUOTE_ASSET}).")
                continue

            # Obliczamy dzienny zakres w procentach: ((high - low) / low) * 100
            df['daily_range_percent'] = ((df['high'] - df['low']) / df['low']) * 100
            
            # Obliczamy średnią zmienność
            avg_volatility = df['daily_range_percent'].mean()
            
            results.append({'symbol': symbol, 'avg_volatility': avg_volatility})
            logging.info(f"[{i}/{len(symbols)}] {symbol} - Średnia zmienność: {avg_volatility:.2f}%")

        except Exception as e:
            logging.error(f"[{i}/{len(symbols)}] Błąd podczas przetwarzania {symbol}: {e}")

    # Sortujemy wyniki od najwyższej zmienności
    sorted_results = sorted(results, key=lambda x: x['avg_volatility'], reverse=True)
    
    return sorted_results

if __name__ == '__main__':
    volatility_report = analyze_volatility()
    if volatility_report:
        print("\n--- RAPORT ZMIENNOŚCI (OSTATNIE 30 DNI) ---")
        print(f"{'Symbol':<15} | {'Średnia Zmienność Dzienna':<30}")
        print("-" * 50)
        for item in volatility_report:
            print(f"{item['symbol']:<15} | {item['avg_volatility']:.2f}%")
