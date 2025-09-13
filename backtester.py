import pandas as pd
import logging
import os
import sqlite3
import json
import sys

# --- KONFIGURACJA ---
DATA_FILE = 'WLDUSDC_1h_data_1_rok.csv'
DB_NAME = 'biblioteka.db'
INITIAL_EQUITY = 1000.0
FEE_PERCENT = 0.075

# Ścieżki
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, DATA_FILE)
DB_PATH = os.path.join(BASE_DIR, DB_NAME)

# Logowanie
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_genome_parameters(genome_id):
    """Pobiera parametry dla danego genomu z bazy danych."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT parameters FROM genomes WHERE id = ?", (genome_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return json.loads(result[0])
        else:
            logging.error(f"Nie znaleziono genomu o ID: {genome_id}")
            return None
    except sqlite3.Error as e:
        logging.error(f"Błąd odczytu z bazy danych: {e}")
        return None

def save_results_to_db(genome_id, results):
    """Zapisuje wyniki backtestu do bazy danych."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE backtest_results
        SET pnl_net = ?, win_rate = ?, total_trades = ?
        WHERE genome_id = ?
        """, (
            results['pnl_net'],
            results['win_rate'],
            results['total_trades'],
            genome_id
        ))
        # Jeśli UPDATE nie zmodyfikował żadnego wiersza (bo go nie ma), zrób INSERT
        if cursor.rowcount == 0:
            cursor.execute("""
            INSERT INTO backtest_results (genome_id, pnl_net, win_rate, total_trades, start_date, end_date)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                genome_id,
                results['pnl_net'],
                results['win_rate'],
                results['total_trades'],
                results['start_date'],
                results['end_date']
            ))
        conn.commit()
        conn.close()
        logging.info(f"Wyniki dla genomu ID {genome_id} zostały zapisane w bazie danych.")
    except sqlite3.Error as e:
        logging.error(f"Błąd zapisu do bazy danych: {e}")


def run_backtest(genome_id):
    """Główna funkcja silnika backtestera, sterowana przez ID genomu."""
    
    # --- Krok 1: Pobierz "DNA" strategii z bazy danych ---
    params = get_genome_parameters(genome_id)
    if not params:
        return

    short_ma_period = params.get('short_ma', 20)
    long_ma_period = params.get('long_ma', 50)
    
    logging.info(f"Rozpoczynam backtest dla Genomu ID: {genome_id} z parametrami MA({short_ma_period}/{long_ma_period})")

    # --- Krok 2: Wczytaj dane historyczne ---
    if not os.path.exists(DATA_PATH):
        logging.error(f"Nie znaleziono pliku z danymi: {DATA_PATH}.")
        return

    df = pd.read_csv(DATA_PATH, parse_dates=['datetime'], index_col='datetime')

    # --- Krok 3: Przygotuj wskaźniki ---
    df['short_ma'] = df['close'].rolling(window=short_ma_period).mean()
    df['long_ma'] = df['close'].rolling(window=long_ma_period).mean()
    df.dropna(inplace=True)

    # --- Krok 4: Pętla symulacji ---
    in_position = False
    trades = []

    for i in range(1, len(df)):
        if df['short_ma'].iloc[i-1] < df['long_ma'].iloc[i-1] and \
           df['short_ma'].iloc[i] > df['long_ma'].iloc[i] and \
           not in_position:
            entry_price = df['close'].iloc[i]
            in_position = True

        elif df['short_ma'].iloc[i-1] > df['long_ma'].iloc[i-1] and \
             df['short_ma'].iloc[i] < df['long_ma'].iloc[i] and \
             in_position:
            exit_price = df['close'].iloc[i]
            trade_return = (exit_price / entry_price) - 1
            trade_return -= (FEE_PERCENT / 100) * 2
            trades.append(trade_return)
            in_position = False

    # --- Krok 5: Generowanie raportu ---
    if not trades:
        logging.warning("Strategia nie wygenerowała żadnych transakcji.")
        return

    total_trades = len(trades)
    wins = sum(1 for t in trades if t > 0)
    win_rate = (wins / total_trades) * 100
    net_pnl_percent = sum(trades) * 100
    
    results = {
        "pnl_net": round(net_pnl_percent, 2),
        "win_rate": round(win_rate, 2),
        "total_trades": total_trades,
        "start_date": df.index[0].date().isoformat(),
        "end_date": df.index[-1].date().isoformat()
    }

    print("\n" + "="*50)
    print("--- RAPORT Z BITWY W KOLOSEUM ---")
    print("="*50)
    print(f"Testowany Genom ID:    {genome_id}")
    print(f"Parametry:             MA({short_ma_period})/MA({long_ma_period})")
    print(f"Okres:                 od {results['start_date']} do {results['end_date']}")
    print("-"*50)
    print(f"Wynik Netto (PnL):     {results['pnl_net']}%")
    print(f"Liczba transakcji:     {results['total_trades']}")
    print(f"Współczynnik Zwycięstw: {results['win_rate']}%")
    print("="*50)

    # Zapisz wyniki do bazy danych
    save_results_to_db(genome_id, results)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("BŁĄD: Podaj ID genomu do przetestowania.")
        print("Przykład użycia: python3 backtester.py 1")
    else:
        try:
            genome_to_test_id = int(sys.argv[1])
            run_backtest(genome_to_test_id)
        except ValueError:
            print("BŁĄD: ID genomu musi być liczbą całkowitą.")
