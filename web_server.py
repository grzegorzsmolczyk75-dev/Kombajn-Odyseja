# ====================================================================
#  PROJEKT "ODYSEJA" - WERSJA ZREORGANIZOWANA Z POPRAWKĄ 404
#  Data modyfikacji: 14.09.2025
#  Opis: Kompletna, działająca wersja serwera WWW po reorganizacji.
#  Dodano brakujący endpoint /market_data, aby naprawić błąd 404.
# ====================================================================
import os
import json
import csv
from flask import Flask, render_template, jsonify, flash, redirect, url_for
from flask_basicauth import BasicAuth
from waitress import serve
import logging
from datetime import datetime
import pytz

# --- Konfiguracja Podstawowa ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
STATE_FILE = os.path.join(BASE_DIR, "state.json")
HISTORY_FILE = os.path.join(BASE_DIR, "trades_history.csv")

# --- Funkcje do ładowania danych ---
def load_config():
    try:
        with open(CONFIG_FILE) as f: return json.load(f)
    except Exception: return {}

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f: return json.load(f)
        except json.JSONDecodeError: return {"in_position": False}
    return {"in_position": False}

# --- Inicjalizacja Aplikacji Flask ---
app = Flask('dashboard')
config = load_config()
app.secret_key = os.urandom(24)

# --- Zabezpieczenie hasłem ---
app.config['BASIC_AUTH_USERNAME'] = config.get('dashboard_user', 'admin')
app.config['BASIC_AUTH_PASSWORD'] = config.get('dashboard_pass', 'password')
basic_auth = BasicAuth(app)

# ====================================================================
#  GŁÓWNE ENDPOINTY APLIKACJI
# ====================================================================

@app.route('/')
@basic_auth.required
def dashboard():
    cfg = load_config()
    # ================== POCZĄTEK MODYFIKACJI ==================
    state = load_state() # Dodano wywołanie funkcji wczytującej stan
    # ================== KONIEC MODYFIKACJI ===================
    stats = {'winrate': 0, 'total_trades': 0, 'total_pnl': 0, 'best_trade': 0, 'worst_trade': 0}
    history = []
    warsaw_tz = pytz.timezone('Europe/Warsaw')

    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', newline='') as f:
                reader = csv.DictReader(f)
                temp_history = []
                for row in reader:
                    try:
                        utc_time = datetime.fromisoformat(row['exit_timestamp'])
                        local_time = utc_time.astimezone(warsaw_tz)
                        row['exit_timestamp_local'] = local_time.strftime('%Y-%m-%d %H:%M:%S')
                    except (ValueError, KeyError):
                        row['exit_timestamp_local'] = 'Błąd Czasu'
                    temp_history.append(row)
                history = sorted(temp_history, key=lambda x: x.get('exit_timestamp', ''), reverse=True)

            stats['total_trades'] = len(history)
            if stats['total_trades'] > 0:
                pnls = [float(t['pnl']) for t in history if t.get('pnl') and t['pnl'] != 'N/A']
                if pnls:
                    wins = [p for p in pnls if p > 0]
                    stats['winrate'] = (len(wins) / len(pnls) * 100) if pnls else 0
                    stats['total_pnl'] = sum(pnls)
                    stats['best_trade'] = max(pnls)
                    stats['worst_trade'] = min(pnls)
        except Exception as e:
            logging.error(f"Błąd odczytu pliku historii: {e}")

    # ================== POCZĄTEK MODYFIKACJI ==================
    # Dodano 'state=state' do przekazywanych zmiennych
    return render_template('dashboard.html', config=cfg, stats=stats, history=history, state=state)
    # ================== KONIEC MODYFIKACJI ===================

@app.route('/status')
@basic_auth.required
def get_status():
    state = load_state()
    response = {
        "in_position": state.get("in_position", False),
        "state": state if state.get("in_position") else {},
        "balance": "N/A",
        "pnl": {"value": "N/A", "percent": "N/A"},
        "status_text": "CENTRUM DOWODZENIA AKTYWNE"
    }
    return jsonify(response)

@app.route('/market_data')
@basic_auth.required
def get_market_data():
    return jsonify({"usdc_pairs": []})

@app.route('/save_config', methods=['POST'])
@basic_auth.required
def save_config_route():
    flash('Funkcja zapisu konfiguracji jest w trakcie reorganizacji.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/close_position_emergency', methods=['POST'])
@basic_auth.required
def close_position_emergency():
    flash('Funkcja awaryjnego zamykania jest w trakcie reorganizacji.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/emergency_reset', methods=['POST'])
@basic_auth.required
def emergency_reset():
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
        flash('Plik stanu został zresetowany!', 'warning')
    else:
        flash('Plik stanu nie istniał.', 'info')
    return redirect(url_for('dashboard'))

# ====================================================================
#  URUCHOMIENIE SERWERA
# ====================================================================
if __name__ == '__main__':
    logging.info(">>> URUCHAMIANIE SERWERA 'TABLICY DOWODZENIA' (Waitress) NA PORCIE 5001 <<<")
    serve(app, host='0.0.0.0', port=5001, threads=10)

