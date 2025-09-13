import sqlite3
import json
import os
import logging

# --- KONFIGURACJA ---
DB_NAME = 'biblioteka.db'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, DB_NAME)

# Ustawienie logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def save_test_results_to_db():
    """
    Zapisuje strategię, jej genom (parametry) oraz wynik backtestu
    do bazy danych 'biblioteka.db'.
    """

    # --- DANE Z NASZEGO OSTATNIEGO TESTU ---
    strategy_name = "Przecięcie Średnich Kroczących"
    strategy_desc = "Kupno, gdy krótka MA (20) przecina od dołu długą MA (50). Sprzedaż w odwrotnej sytuacji."
    genome_params = {"short_ma": 20, "long_ma": 50}

    backtest_result_data = {
        "pnl_net": 187.31,
        "win_rate": 31.91,
        "total_trades": 94,
        "start_date": "2024-09-14",
        "end_date": "2025-09-12"
    }

    if not os.path.exists(DB_PATH):
        logging.error(f"Baza danych '{DB_NAME}' nie istnieje! Uruchom najpierw skrypt tworzący bazę.")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        logging.info(f"Połączono z bazą danych '{DB_NAME}'.")

        # Krok 1: Zapisz strategię (lub zignoruj, jeśli już istnieje)
        cursor.execute("INSERT OR IGNORE INTO strategies (name, description) VALUES (?, ?)", 
                       (strategy_name, strategy_desc))

        # Pobierz ID strategii (istniejące lub nowo utworzone)
        cursor.execute("SELECT id FROM strategies WHERE name = ?", (strategy_name,))
        strategy_id_tuple = cursor.fetchone()
        if not strategy_id_tuple:
            logging.error("Nie udało się znaleźć ani stworzyć strategii w bazie danych.")
            return
        strategy_id = strategy_id_tuple[0]
        logging.info(f"Przetwarzam strategię '{strategy_name}' (ID: {strategy_id}).")

        # Krok 2: Zapisz genom (konkretny zestaw parametrów)
        params_json = json.dumps(genome_params)
        cursor.execute("INSERT INTO genomes (strategy_id, parameters) VALUES (?, ?)", 
                       (strategy_id, params_json))
        genome_id = cursor.lastrowid
        logging.info(f"Zapisano nowy Genom z parametrami {params_json} (ID: {genome_id}).")

        # Krok 3: Zapisz wynik testu i powiąż go z genomem
        cursor.execute("""
        INSERT INTO backtest_results (genome_id, pnl_net, win_rate, total_trades, start_date, end_date)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            genome_id,
            backtest_result_data['pnl_net'],
            backtest_result_data['win_rate'],
            backtest_result_data['total_trades'],
            backtest_result_data['start_date'],
            backtest_result_data['end_date']
        ))
        result_id = cursor.lastrowid
        logging.info(f"Zapisano wyniki testu w bazie danych (ID: {result_id}).")

        conn.commit()
        logging.info("\nDane zostały pomyślnie zarchiwizowane w 'Bibliotece Genetycznej'.")

    except sqlite3.Error as e:
        logging.error(f"Wystąpił błąd bazy danych: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    save_test_results_to_db()
