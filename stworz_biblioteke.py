import sqlite3
import os

# --- KONFIGURACJA ---
DB_NAME = 'biblioteka.db'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, DB_NAME)

def create_database():
    """
    Tworzy plik bazy danych SQLite i definiuje strukturę tabel,
    jeśli nie istnieją.
    """
    try:
        # Połączenie z bazą danych (plik zostanie utworzony, jeśli nie istnieje)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        print(f"Pomyślnie połączono z bazą danych '{DB_NAME}'...")

        # --- Tabela 1: strategies (Główne Strategie) ---
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT
        )
        ''')

        # --- Tabela 2: genomes (Genomy - konkretne parametry) ---
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS genomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER NOT NULL,
            parameters TEXT NOT NULL, -- Przechowywane jako tekst w formacie JSON
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (strategy_id) REFERENCES strategies (id)
        )
        ''')

        # --- Tabela 3: backtest_results (Wyniki z "Koloseum") ---
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS backtest_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            genome_id INTEGER NOT NULL,
            pnl_net REAL,
            win_rate REAL,
            total_trades INTEGER,
            start_date DATETIME,
            end_date DATETIME,
            report_details TEXT, -- Przechowywane jako tekst w formacie JSON
            FOREIGN KEY (genome_id) REFERENCES genomes (id)
        )
        ''')
        
        # Zatwierdzenie zmian
        conn.commit()
        print("Struktura tabel 'strategies', 'genomes' i 'backtest_results' została pomyślnie utworzona/zweryfikowana.")

    except sqlite3.Error as e:
        print(f"Wystąpił błąd bazy danych: {e}")
    finally:
        if conn:
            conn.close()
            print("Połączenie z bazą danych zostało zamknięte.")

if __name__ == '__main__':
    print("Rozpoczynam tworzenie fundamentów 'Biblioteki Genetycznej'...")
    create_database()
    print("\nZakończono. Fundamenty gotowe!")
