
# ==================================================================================================
#  PROJEKT "KOMBAJN" - WERSJA ODYSEJA 4.0 (LOGOWANIE KULOODPORNE)
# ==================================================================================================
import os
import sys
import hmac
import hashlib
import time
import urllib.parse
import requests
import json
import logging
import threading
import csv
import subprocess
from decimal import Decimal, getcontext, ROUND_DOWN
from datetime import datetime
from logging.handlers import RotatingFileHandler
from flask import Flask, request, render_template, jsonify, flash, redirect, url_for
from flask_basicauth import BasicAuth
from waitress import serve

# --- SEKCJA 1: KONFIGURACJA I ZMIENNE GLOBALNE (WERSJA Z DZIENNIKIEM) ---
getcontext().prec = 18
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Konfiguracja logowania do pliku
log_file = os.path.join(BASE_DIR, 'bot.log')
file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=2)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s [wątek:%(threadName)s]'))

# Konfiguracja logowania do konsoli (dla journalctl)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Ustawienie głównego loggera
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)
root_logger.addHandler(stream_handler)

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
STATE_FILE = os.path.join(BASE_DIR, "state.json")
HISTORY_FILE = os.path.join(BASE_DIR, "trades_history.csv")
monitoring_active = threading.Event()

def create_default_config_if_not_exists():
    if not os.path.exists(CONFIG_FILE):
        logging.warning("Plik config.json nie znaleziony. Tworzę domyślną konfigurację.")
        default_config = {
            "api_key": "TWOJ_KLUCZ_API", "secret_key": "TWOJ_SEKRETNY_KLUCZ",
            "dashboard_user": "admin", "dashboard_pass": "password",
            "service_name": "bot.service", "quote_asset": "USDC", "trade_symbol": "WLDUSDC",
            "position_size_percent": 50.0, "sl_percent": 2.0, "exit_strategy": "take_profit", "tp_percent": 5.0,
        }
        with open(CONFIG_FILE, 'w') as f: json.dump(default_config, f, indent=4)
        logging.info(f"Utworzono domyślny plik konfiguracyjny: {CONFIG_FILE}. Uzupełnij klucze API.")
        sys.exit(0)

def load_config():
    with open(CONFIG_FILE) as f: return json.load(f)


# --- SEKCJA 2: FUNKCJE POMOCNICZE I NARZĘDZIOWE ---
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f: return json.load(f)
        except json.JSONDecodeError: return {"in_position": False}
    return {"in_position": False}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)

def send_request(method, path, params={}, signed=False, margin=False):
    base_url = "https://api.binance.com"
    api_path = f"/sapi/v1/margin{path}" if margin else f"/api/v3{path}"
    headers = {'X-MBX-APIKEY': API_KEY}
    params = {k: v for k, v in params.items() if v is not None}
    if signed:
        params['timestamp'] = int(time.time() * 1000)
        query_string = urllib.parse.urlencode(params)
        signature = hmac.new(SECRET_KEY.encode('utf-8'), msg=query_string.encode('utf-8'), digestmod=hashlib.sha256).hexdigest()
        url = f"{base_url}{api_path}?{query_string}&signature={signature}"
    else:
        url = f"{base_url}{api_path}?{urllib.parse.urlencode(params)}"
    try:
        response = requests.request(method, url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Błąd komunikacji z API Binance: {e}")
        try:
            if e.response:
                error_content = e.response.json()
                logging.error(f"Odpowiedź serwera Binance: {error_content}")
                return error_content
            return None
        except json.JSONDecodeError:
            return None

# === NOWE, PRECYZYJNE FUNKCJE FORMATUJĄCE ===
def get_step_precision(step_size_decimal):
    return abs(step_size_decimal.as_tuple().exponent)

def format_price(price, precision):
    tick_size = precision['TICK_SIZE']
    precision_level = get_step_precision(tick_size)
    return f"{price:.{precision_level}f}"

def format_quantity(quantity, precision):
    step_size = precision['STEP_SIZE']
    precision_level = get_step_precision(step_size)
    return f"{quantity:.{precision_level}f}"

def get_precision_data(symbol):
    data = send_request('GET', '/exchangeInfo', {'symbol': symbol})
    if not (data and 'symbols' in data): return None
    s_info = next((s for s in data['symbols'] if s['symbol'] == symbol), None)
    if not s_info: return None
    precision = {}
    for f in s_info['filters']:
        if f['filterType'] == 'PRICE_FILTER': precision['TICK_SIZE'] = Decimal(f['tickSize'])
        if f['filterType'] == 'LOT_SIZE': precision['STEP_SIZE'] = Decimal(f['stepSize'])
    return precision if 'TICK_SIZE' in precision and 'STEP_SIZE' in precision else None

def get_margin_balance(asset):
    data = send_request('GET', '/account', {}, signed=True, margin=True)
    if not (data and 'userAssets' in data): return Decimal('0')
    asset_info = next((a for a in data['userAssets'] if a['asset'] == asset), None)
    return Decimal(asset_info['free']) if asset_info else Decimal('0')

def get_current_price(symbol):
    data = send_request('GET', '/ticker/price', {'symbol': symbol})
    return Decimal(data['price']) if data and 'price' in data else None

def get_debt(asset):
    margin_account = send_request('GET', '/account', {}, signed=True, margin=True)
    if not (margin_account and 'userAssets' in margin_account): return Decimal('0')
    asset_info = next((a for a in margin_account['userAssets'] if a['asset'] == asset), None)
    return Decimal(asset_info['borrowed']) if asset_info else Decimal('0')

# --- SEKCJA 3: RDZEŃ LOGIKI HANDLOWEJ ---
def place_stop_loss_order(symbol, side, quantity, stop_price, precision):
    tick_size = precision['TICK_SIZE']
    stop_price_adjusted = (stop_price / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * tick_size
    
    sl_params = {
        'symbol': symbol,
        'side': side,
        'type': 'STOP_LOSS',
        'quantity': format_quantity(quantity, precision),
        'stopPrice': format_price(stop_price_adjusted, precision)
    }
    sl_response = send_request('POST', '/order', sl_params, signed=True, margin=True)
    
    if sl_response and 'orderId' in sl_response:
        logging.info(f">>> SUKCES! SL (STOP_LOSS) ustawiony [ID: {sl_response['orderId']}] na cenie {stop_price_adjusted}")
        return sl_response['orderId']
    else:
        logging.critical(f"!!! BŁĄD KRYTYCZNY: Nie udało się ustawić zlecenia SL! Odpowiedź Binance: {sl_response}")
        return None

def cancel_order(symbol, order_id):
    if not order_id:
        logging.warning("Próba anulowania zlecenia z pustym ID. Ignoruję.")
        return True
    params = {'symbol': symbol, 'orderId': order_id}
    response = send_request('DELETE', '/order', params, signed=True, margin=True)
    if response and 'orderId' in response:
        logging.info(f"--- SUKCES! Zlecenie [ID:{order_id}] anulowane.")
        return True
    else:
        logging.warning(f"--- OSTRZEŻENIE: Nie udało się anulować zlecenia [ID: {order_id}]. Odpowiedź: {response}")
        return False

def log_trade_history(symbol, side, quantity, entry_price, exit_price, entry_ts, exit_ts, reason, pnl=None, precision=None):
    try:
        write_header = not os.path.exists(HISTORY_FILE) or os.stat(HISTORY_FILE).st_size == 0
        quantity_str = format_quantity(quantity, precision) if precision else str(quantity)
        entry_price_str = format_price(entry_price, precision) if precision else str(entry_price)
        exit_price_str = format_price(exit_price, precision) if precision else str(exit_price)
        
        with open(HISTORY_FILE, 'a', newline='') as csvfile:
            fieldnames = ['symbol', 'side', 'quantity', 'entry_price', 'exit_price', 'pnl', 'entry_timestamp', 'exit_timestamp', 'exit_reason']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if write_header: writer.writeheader()
            writer.writerow({
                'symbol': symbol, 'side': side, 'quantity': quantity_str,
                'entry_price': entry_price_str, 'exit_price': exit_price_str,
                'pnl': f"{pnl:.4f}" if pnl is not None else "0.0",
                'entry_timestamp': datetime.fromtimestamp(entry_ts).isoformat(),
                'exit_timestamp': datetime.fromtimestamp(exit_ts).isoformat(),
                'exit_reason': reason
            })
    except Exception as e:
        logging.error(f"!!! Błąd zapisu historii transakcji: {e}")

def price_monitor():
    logging.info(">>> SOKOLE OKO AKTYWOWANE <<<")
    while monitoring_active.is_set():
        try:
            state = load_state()
            if not state.get("in_position"):
                monitoring_active.clear(); break
            cfg = load_config()
            symbol, side, entry_price = state['symbol'], state['side'], Decimal(state['entry_price'])
            current_price = get_current_price(symbol)
            if not current_price:
                time.sleep(10); continue
            strategy = state.get("exit_strategy")
            precision = get_precision_data(symbol)
            if not precision:
                logging.error(f"Sokole Oko: Nie udało się pobrać precyzji dla {symbol}. Próbuję ponownie za 10s.")
                time.sleep(10); continue
                
            if strategy == "take_profit":
                tp_price = Decimal(state['take_profit_price'])
                if (side == 'long' and current_price >= tp_price) or (side == 'short' and current_price <= tp_price):
                    logging.info("$$$ SOKOLE OKO (TP): CEL OSIĄGNIĘTY! $$$")
                    close_position(state, precision, exit_price=current_price, exit_reason="Take Profit")
                    break
            elif strategy == "trailing_stop":
                ts_activated = state.get('ts_activated', False)
                if not ts_activated:
                    activation_price = Decimal(state['ts_activation_price'])
                    if (side == 'long' and current_price >= activation_price) or (side == 'short' and current_price <= activation_price):
                        logging.info(f"*** TRAILING STOP AKTYWOWANY! ***")
                        state['ts_activated'] = True
                        state['ts_extremum_price'] = str(current_price); save_state(state)
                else:
                    extremum_price = Decimal(state['ts_extremum_price'])
                    if (side == 'long' and current_price > extremum_price) or (side == 'short' and current_price < extremum_price):
                        logging.info(f"[TS] Nowy szczyt/dołek: {format_price(current_price, precision)}. Przesuwam SL.")
                        ts_dist_perc = Decimal(cfg.get('ts_distance_percent', 1.0))
                        distance_factor = Decimal('1') - (ts_dist_perc / Decimal('100'))
                        new_stop_price = current_price * distance_factor if side == 'long' else current_price / distance_factor
                        
                        if cancel_order(symbol, state.get('stop_loss_id')):
                            new_sl_id = place_stop_loss_order(symbol, 'SELL' if side == 'long' else 'BUY', Decimal(state['quantity']), new_stop_price, precision)
                            if new_sl_id:
                                state['stop_loss_id'] = new_sl_id
                                state['ts_extremum_price'] = str(current_price); save_state(state)
            time.sleep(5)
        except Exception as e:
            logging.error(f"!!! BŁĄD w wątku Sokole Oko: {e}", exc_info=True)
            time.sleep(30)
    logging.info(">>> SOKOLE OKO DEZAKTYWOWANE <<<")

def start_monitoring_thread():
    if not monitoring_active.is_set():
        monitoring_active.set()
        thread = threading.Thread(target=price_monitor); thread.daemon = True; thread.start()

def _open_position_helper(side, symbol, precision, reentry_count=0):
    usdc_balance = get_margin_balance(QUOTE_ASSET)
    current_price = get_current_price(symbol)
    if usdc_balance <= 10 or not current_price:
        logging.error("Nie można otworzyć pozycji: za mało środków lub problem z pobraniem ceny."); return
    cfg = load_config()
    investment = usdc_balance * (Decimal(cfg.get("position_size_percent", 50.0)) / Decimal('100'))
    step_size = precision['STEP_SIZE']
    quantity = (investment / current_price / step_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * step_size
    if quantity == 0:
        logging.error("Obliczona ilość do zakupu jest zbyt mała."); return
    if side == 'short':
        base_asset = symbol.replace(QUOTE_ASSET, '')
        debt_amount = get_debt(base_asset)
        if debt_amount > 0:
            logging.warning(f"Wykryto istniejący dług na {base_asset} w wysokości {debt_amount}. Zostanie on spłacony przy zamykaniu tej pozycji.")
        loan_params = {'asset': base_asset, 'amount': format_quantity(quantity, precision)}
        loan_response = send_request('POST', '/loan', loan_params, signed=True, margin=True)
        if not (loan_response and 'tranId' in loan_response):
            logging.error(f"Błąd podczas zaciągania pożyczki dla pozycji SHORT. Odpowiedź: {loan_response}"); return
        logging.info(f"Pożyczka dla SHORT udana [ID: {loan_response['tranId']}]"); time.sleep(2)
    order_side = 'BUY' if side == 'long' else 'SELL'
    order_params = {'symbol': symbol, 'side': order_side, 'type': 'MARKET', 'quantity': format_quantity(quantity, precision)}
    logging.info(f">>> PARAMETRY ZLECENIA MARKET: {json.dumps(order_params)}")
    order_response = send_request('POST', '/order', order_params, signed=True, margin=True)
    if not (order_response and 'orderId' in order_response):
        logging.error(f"Błąd podczas otwierania pozycji {side.upper()}. Odpowiedź: {order_response}"); return
    logging.info(f"Zlecenie {side.upper()} przyjęte [ID: {order_response['orderId']}]")
    logging.info("Czekam 2 sekundy na zaksięgowanie transakcji przez giełdę..."); time.sleep(2)
    entry_price = get_current_price(symbol)
    if not entry_price:
        logging.critical("Nie udało się pobrać ceny wejścia po otwarciu pozycji! Nie ustawiam SL.")
        save_state({"in_position": True, "symbol": symbol, "side": side, "entry_price": "N/A", "quantity": str(quantity), "stop_loss_id": None}); return
    sl_price = entry_price * (Decimal('1') - (Decimal(cfg.get("sl_percent", 2.0)) / Decimal('100'))) if side == 'long' else entry_price * (Decimal('1') + (Decimal(cfg.get("sl_percent", 2.0)) / Decimal('100')))
    sl_order_id = place_stop_loss_order(symbol, 'SELL' if side == 'long' else 'BUY', quantity, sl_price, precision)
    new_state = {
        "in_position": True, "symbol": symbol, "side": side, "entry_price": str(entry_price), "quantity": str(quantity),
        "stop_loss_id": sl_order_id, "exit_strategy": cfg.get("exit_strategy", "take_profit"),
        "entry_timestamp": time.time(), "reentry_count": reentry_count
    }
    if new_state["exit_strategy"] == "take_profit":
        tp_factor = (Decimal('1') + (Decimal(cfg.get("tp_percent", 5.0)) / Decimal('100')))
        new_state["take_profit_price"] = str(entry_price * tp_factor if side == 'long' else entry_price / tp_factor)
    elif new_state["exit_strategy"] == "trailing_stop":
        act_perc = Decimal(cfg.get("ts_activation_percent", 2.0))
        act_factor = Decimal('1') + (act_perc / Decimal('100'))
        new_state["ts_activation_price"] = str(entry_price * act_factor if side == 'long' else entry_price / act_factor)
        new_state["ts_activated"] = False; new_state["ts_extremum_price"] = str(entry_price)
    save_state(new_state); start_monitoring_thread()

def open_long_position(symbol, precision, reentry_count=0):
    logging.info(f">>> Inicjuję otwarcie pozycji LONG (Re-entry: {reentry_count})")
    _open_position_helper('long', symbol, precision, reentry_count)

def open_short_position(symbol, precision, reentry_count=0):
    logging.info(f">>> Inicjuję otwarcie pozycji SHORT (Re-entry: {reentry_count})")
    _open_position_helper('short', symbol, precision, reentry_count)

def close_position(state, precision, exit_price=None, exit_reason="N/A"):
    monitoring_active.clear()
    time.sleep(1)

    symbol = state['symbol']
    side = state['side']
    stop_loss_id = state.get('stop_loss_id')
    quantity = Decimal(state['quantity'])
    entry_price = Decimal(state['entry_price'])
    entry_timestamp = state.get('entry_timestamp', time.time())

    if stop_loss_id:
        try:
            cancel_order(symbol, stop_loss_id)
        except Exception as e:
            logging.warning(f"--- OSTRZEŻENIE: Nie udało się anulować zlecenia SL [ID: {stop_loss_id}], prawdopodobnie już nie istniało. Błąd: {e}")

    if side == 'short':
        base_asset = symbol.replace(QUOTE_ASSET, '')
        debt = get_debt(base_asset)
        if debt > 0:
            logging.info(f">>> ANTY-PYŁEK: Zwiększam ilość do odkupienia o wykryty dług: {debt}")
            quantity += debt

    close_side = 'BUY' if side == 'short' else 'SELL'
    close_params = {'symbol': symbol, 'side': close_side, 'type': 'MARKET', 'quantity': format_quantity(quantity, precision), 'sideEffectType': 'AUTO_REPAY'}
    close_response = send_request('POST', '/order', close_params, signed=True, margin=True)

    if not (close_response and 'orderId' in close_response):
        logging.critical(f"!!! KRYTYCZNY BŁĄD: Nie udało się zamknąć pozycji! Odpowiedź: {close_response}")
        save_state({"in_position": False})
        return

    final_exit_price = exit_price if exit_price else get_current_price(symbol)
    if not final_exit_price: final_exit_price = entry_price # Fallback

    pnl = (final_exit_price - entry_price) * quantity if side == 'long' else (entry_price - final_exit_price) * quantity
    log_trade_history(symbol, side, quantity, entry_price, final_exit_price, entry_timestamp, time.time(), exit_reason, pnl, precision)

    cfg = load_config()

    if exit_reason == "Take Profit" and cfg.get("reentry_enabled", False) and state.get("reentry_count", 0) < cfg.get("reentry_max_count", 0):
        cooldown = cfg.get("reentry_cooldown_seconds", 5)
        logging.info(f"--- Aktywuję OGNISTY PODMUCH! Czekam {cooldown}s na ustabilizowanie salda...")
        time.sleep(cooldown)

        initial_balance = get_margin_balance(QUOTE_ASSET)
        retries = 5
        while retries > 0:
            current_balance = get_margin_balance(QUOTE_ASSET)
            if current_balance >= initial_balance and current_balance > 10:
                logging.info(f"Saldo ({current_balance} {QUOTE_ASSET}) jest gotowe. Kontynuuję 'Ognisty Podmuch'.")
                new_reentry_count = state.get("reentry_count", 0) + 1
                if side == 'long':
                    open_short_position(symbol, precision, reentry_count=new_reentry_count)
                elif side == 'short':
                    open_long_position(symbol, precision, reentry_count=new_reentry_count)
                return

            logging.warning(f"Saldo wciąż nie jest gotowe. Czekam 2s... (Próba {6-retries}/5)")
            time.sleep(2)
            retries -= 1

        logging.error("!!! BŁĄD 'Ognistego Podmuchu': Nie udało się potwierdzić dostępności salda po zamknięciu pozycji. Anuluję ponowne wejście.")
        save_state({"in_position": False})
    else:
        save_state({"in_position": False})

# --- SEKCJA 4: APLIKACJA WEBOWA (FLASK) I ENDPOINTS ---
app = Flask('bot')
app.secret_key = os.urandom(24)
create_default_config_if_not_exists()
config = load_config()
API_KEY = config.get("api_key")
SECRET_KEY = config.get("secret_key")
QUOTE_ASSET = config.get("quote_asset")
app.config['BASIC_AUTH_USERNAME'] = config.get('dashboard_user', 'admin')
app.config['BASIC_AUTH_PASSWORD'] = config.get('dashboard_pass', 'password')
basic_auth = BasicAuth(app)

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json if request.is_json else json.loads(request.data)
        cfg, state = load_config(), load_state()
        action, symbol = data.get('action'), cfg.get('trade_symbol')
        precision = get_precision_data(symbol)
        if not precision:
            logging.error(f"Błąd krytyczny: Nie można pobrać danych o precyzji dla symbolu {symbol}.")
            return "Błąd precyzji.", 500
        if not state.get("in_position"):
            if action == 'buy': open_long_position(symbol, precision)
            elif action == 'sell': open_short_position(symbol, precision)
        else:
            current_side = state.get("side")
            if (action == 'buy' and current_side == 'short') or (action == 'sell' and current_side == 'long'):
                logging.info(f"Odebrano sygnał przeciwny. Zamykam pozycję {current_side.upper()} i otwieram nową.")
                close_position(state, precision, exit_reason="Sygnał przeciwny")
                time.sleep(3)
                if action == 'buy': open_long_position(symbol, precision)
                elif action == 'sell': open_short_position(symbol, precision)
        return "Webhook przetworzony.", 200
    except Exception as e:
        logging.error(f"!!! KRYTYCZNY BŁĄD w obsłudze webhooka: {e}", exc_info=True)
        return "Wewnętrzny błąd serwera", 500

@app.route('/')
@basic_auth.required
def dashboard():
    cfg = load_config()
    stats = {'winrate': 0, 'total_trades': 0, 'total_pnl': 0, 'best_trade': 0, 'worst_trade': 0}
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                trades = [row for row in csv.DictReader(f) if row.get('pnl')]
                stats['total_trades'] = len(trades)
                if stats['total_trades'] > 0:
                    pnls = [float(t['pnl']) for t in trades if t.get('pnl') and t['pnl'] != 'N/A']
                    wins = [p for p in pnls if p > 0]
                    stats['winrate'] = (len(wins) / len(pnls) * 100) if pnls else 0
                    stats['total_pnl'] = sum(pnls)
                    stats['best_trade'] = max(pnls) if pnls else 0
                    stats['worst_trade'] = min(pnls) if pnls else 0
            with open(HISTORY_FILE, 'r') as f:
                reader = csv.DictReader(f)
                history = sorted([row for row in reader], key=lambda x: x.get('exit_timestamp', ''), reverse=True)
        except Exception as e:
            logging.error(f"Błąd odczytu historii/statystyk: {e}")
    return render_template('dashboard.html', config=cfg, history=history, stats=stats)

@app.route('/status')
@basic_auth.required
def get_status():
    state, cfg = load_state(), load_config()
    balance = get_margin_balance(cfg.get('quote_asset'))
    response = {"in_position": state.get("in_position", False), "state": state if state.get("in_position") else {},
                "balance": f"{balance:.2f}" if balance else "Błąd", "quote_asset": cfg.get('quote_asset'),
                "base_asset": state.get('symbol', 'N/A').replace(cfg.get('quote_asset'), ''),
                "status_text": "W POZYCJI" if state.get("in_position") else "OCZEKIWANIE"}
    if state.get("in_position"):
        current_price = get_current_price(state['symbol'])
        if current_price:
            response["current_price"] = float(current_price)
            entry_price, quantity = Decimal(state['entry_price']), Decimal(state['quantity'])
            pnl_val = (current_price - entry_price) * quantity if state['side'] == 'long' else (entry_price - current_price) * quantity
            pnl_perc = (pnl_val / (entry_price * quantity)) * 100 if entry_price > 0 and quantity > 0 else 0
            response["pnl"] = {"value": float(pnl_val), "percent": float(pnl_perc)}
        else:
            response["pnl"] = {"value": "Błąd", "percent": "Błąd"}
    return jsonify(response)

@app.route('/market_data')
@basic_auth.required
def get_market_data():
    try:
        margin_pairs_data = send_request('GET', '/allPairs', {}, signed=True, margin=True)
        if not margin_pairs_data: return jsonify({"usdc_pairs": []})
        usdc_pairs = sorted([p['symbol'] for p in margin_pairs_data if p['symbol'].endswith(QUOTE_ASSET) and p.get('isMarginTrade')])
        return jsonify({"usdc_pairs": usdc_pairs})
    except Exception as e:
        logging.error(f"Błąd w get_market_data: {e}", exc_info=True)
        return jsonify({"usdc_pairs": []})

@app.route('/close_position_emergency', methods=['POST'])
@basic_auth.required
def close_position_emergency():
    state = load_state()
    if state.get("in_position"):
        precision = get_precision_data(state['symbol'])
        if precision:
            threading.Thread(target=close_position, args=(state, precision, None, "Zamknięcie Awaryjne")).start()
            flash("Polecenie zamknięcia pozycji wysłane.", "success")
        else: flash("Błąd: Nie można pobrać precyzji dla symbolu.", "error")
    else: flash("Brak otwartej pozycji do zamknięcia.", "info")
    return redirect(url_for('dashboard'))

@app.route('/emergency_reset', methods=['POST'])
@basic_auth.required
def emergency_reset():
    logging.warning("!!! AWARIA !!! Aktywowano awaryjny reset stanu z panelu.")
    state_file_path = os.path.join(BASE_DIR, "state.json")
    monitoring_active.clear(); time.sleep(1)
    if os.path.exists(state_file_path):
        os.remove(state_file_path); logging.info("Plik state.json został usunięty.")
    flash('Stan bota zresetowany. Restartuję usługę...', 'warning')
    def restart_bot_after_reset():
        time.sleep(2)
        service_name = config.get("service_name", "bot.service")
        subprocess.run(["sudo", "systemctl", "restart", service_name])
    threading.Thread(target=restart_bot_after_reset).start()
    return redirect(url_for('dashboard'))

@app.route('/save_config', methods=['POST'])
@basic_auth.required
def save_config_route():
    try:
        cfg = load_config()
        form_data = request.form
        cfg.update({
            'trade_symbol': form_data.get('trade_symbol'), 'position_size_percent': float(form_data.get('position_size_percent')),
            'sl_percent': float(form_data.get('sl_percent')), 'exit_strategy': form_data.get('exit_strategy'),
            'reentry_max_count': int(form_data.get('reentry_max_count')),
            'reentry_cooldown_seconds': int(form_data.get('reentry_cooldown_seconds'))
        })
        if cfg['exit_strategy'] == 'take_profit': cfg['tp_percent'] = float(form_data.get('tp_percent'))
        elif cfg['exit_strategy'] == 'trailing_stop':
            cfg['ts_activation_percent'] = float(form_data.get('ts_activation_percent'))
            cfg['ts_distance_percent'] = float(form_data.get('ts_distance_percent'))
        cfg['reentry_enabled'] = 'reentry_enabled' in form_data
        with open(CONFIG_FILE, 'w') as f: json.dump(cfg, f, indent=4)
        flash('Konfiguracja zapisana. Restartuję bota...', 'success')
        def restart_bot():
            time.sleep(2); service_name = cfg.get("service_name", "bot.service")
            subprocess.run(["sudo", "systemctl", "restart", service_name])
        threading.Thread(target=restart_bot).start()
    except Exception as e:
        flash(f'Błąd zapisu konfiguracji: {e}', 'error'); logging.error(f"Błąd zapisu konfiguracji: {e}", exc_info=True)
    return redirect(url_for('dashboard'))

# --- SEKCJA 5: URUCHOMIENIE SERWERA ---
if __name__ == '__main__':
    if load_state().get("in_position"): start_monitoring_thread()
    logging.info(">>> URUCHAMIANIE SERWERA PRODUKCYJNEGO WAITRESS NA PORCIE 5001 <<<")
    serve(app, host='0.0.0.0', port=5001, threads=10)
EOF

