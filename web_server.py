import os
import sys
import json
import logging
import csv
import subprocess
import time
from flask import Flask, render_template, jsonify, flash, redirect, url_for, request
from flask_basicauth import BasicAuth
from waitress import serve

# --- KONFIGURACJA SERWERA WWW ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
STATE_FILE = os.path.join(BASE_DIR, "state.json")
HISTORY_FILE = os.path.join(BASE_DIR, "trades_history.csv")

def load_config():
    with open(CONFIG_FILE) as f: return json.load(f)

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f: return json.load(f)
        except json.JSONDecodeError: return {"in_position": False}
    return {"in_position": False}

app = Flask('web_server')
app.secret_key = os.urandom(24)
config = load_config()
app.config['BASIC_AUTH_USERNAME'], app.config['BASIC_AUTH_PASSWORD'] = config.get('dashboard_user'), config.get('dashboard_pass')
basic_auth = BasicAuth(app)

# --- ENDPOINTY (PRZEPISY KELNERKI) ---
@app.route('/')
@basic_auth.required
def dashboard():
    cfg = load_config()
    stats = {'winrate': 0, 'total_trades': 0, 'total_pnl': 0, 'best_trade': 0, 'worst_trade': 0}
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                history = [row for row in csv.DictReader(f)]
                stats['total_trades'] = len(history)
                if stats['total_trades'] > 0:
                    pnls = [float(t['pnl']) for t in history if t.get('pnl')]
                    if pnls:
                        wins = [p for p in pnls if p > 0]
                        stats['winrate'] = (len(wins) / len(pnls) * 100) if pnls else 0
                        stats['total_pnl'], stats['best_trade'], stats['worst_trade'] = sum(pnls), max(pnls), min(pnls)
        except Exception as e: logging.error(f"Błąd odczytu historii: {e}")
    return render_template('dashboard.html', config=cfg, history=history, stats=stats)

@app.route('/status')
@basic_auth.required
def get_status():
    state = load_state()
    # Celowo nie pobieramy tu danych z API, aby serwer był niezależny
    balance_info = "N/A (logika bota wyłączona)"
    response = {"in_position": state.get("in_position", False), "state": state, "balance": balance_info, "status_text": "SERWER WWW AKTYWNY"}
    return jsonify(response)

@app.route('/save_config', methods=['POST'])
@basic_auth.required
def save_config_route():
    try:
        cfg = load_config()
        form_data = request.form
        cfg.update({
            'trade_symbol': form_data.get('trade_symbol'), 
            'position_size_percent': float(form_data.get('position_size_percent')), 
            'sl_percent': float(form_data.get('sl_percent')), 
            'exit_strategy': form_data.get('exit_strategy'), 
            'tp_percent': float(form_data.get('tp_percent'))
        })
        with open(CONFIG_FILE, 'w') as f: json.dump(cfg, f, indent=4)
        flash('Konfiguracja zapisana. Restart usługi bota jest teraz wymagany manualnie.', 'success')
    except Exception as e:
        flash(f'Błąd zapisu: {e}', 'error')
        logging.error(f"Błąd zapisu config: {e}", exc_info=True)
    return redirect(url_for('dashboard'))

@app.route('/emergency_reset', methods=['POST'])
@basic_auth.required
def emergency_reset():
    logging.warning("!!! AWARIA !!! Reset stanu z panelu.")
    if os.path.exists(STATE_FILE): os.remove(STATE_FILE)
    flash('Stan bota zresetowany. Restart usługi bota jest teraz wymagany manualnie.', 'warning')
    return redirect(url_for('dashboard'))

# --- URUCHOMIENIE SERWERA ---
if __name__ == '__main__':
    logging.info(">>> URUCHAMIANIE NIEZALEŻNEGO SERWERA WWW NA PORCIE 5000 <<<")
    serve(app, host='0.0.0.0', port=5000, threads=10)
