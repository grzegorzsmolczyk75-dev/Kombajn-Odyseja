# ====================================================================
#  PROJEKT "ODYSEJA" - FAZA I: MODUŁ LOGIKI HANDLOWEJ
#  Plik: bot_logic.py
# ====================================================================
import os
import hmac
import hashlib
import time
import urllib.parse
import requests
import json
import logging
from decimal import Decimal, getcontext, ROUND_DOWN

# --- Konfiguracja i Zmienne Globalne ---
getcontext().prec = 18
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
STATE_FILE = os.path.join(BASE_DIR, "state.json")
HISTORY_FILE = os.path.join(BASE_DIR, "trades_history.csv")

# --- Funkcje Narzędziowe (ładowanie, zapis) ---
def load_config():
    with open(CONFIG_FILE) as f: return json.load(f)

def save_state(state):
    with open(STATE_FILE, 'w') as f: json.dump(state, f, indent=4)

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f: return json.load(f)
        except json.JSONDecodeError: return {"in_position": False}
    return {"in_position": False}

# ====================================================================
#  RDZEŃ KOMUNIKACJI Z API BINANCE
# ====================================================================
def send_request(method, path, params={}, signed=False, margin=False):
    config = load_config()
    API_KEY = config.get("api_key")
    SECRET_KEY = config.get("secret_key")
    
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

# ====================================================================
#  FUNKCJE POMOCNICZE (Precyzja, Saldo, Cena itp.)
# ====================================================================

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
# ====================================================================
#  PROJEKT "ODYSEJA" - MODUŁ LOGIKI HANDLOWEJ (CZĘŚĆ 2 - OPERACJE)
#  Data modyfikacji: 14.09.2025
# ====================================================================
import threading
from datetime import datetime
import csv

# Zmienna globalna do kontrolowania wątku monitorującego
monitoring_active = threading.Event()

# ====================================================================
#  LOGIKA ZLECEŃ (SL, Anulowanie, Historia)
# ====================================================================

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
        logging.info(f">>> SUKCES! SL ustawiony [ID: {sl_response['orderId']}] na cenie {stop_price_adjusted}")
        return sl_response['orderId']
    else:
        logging.critical(f"!!! BŁĄD KRYTYCZNY: Nie udało się ustawić zlecenia SL! Odpowiedź: {sl_response}")
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
        with open(HISTORY_FILE, 'a', newline='') as csvfile:
            fieldnames = ['symbol', 'side', 'quantity', 'entry_price', 'exit_price', 'pnl', 'entry_timestamp', 'exit_timestamp', 'exit_reason']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if write_header: writer.writeheader()
            writer.writerow({
                'symbol': symbol, 'side': side,
                'quantity': format_quantity(quantity, precision) if precision else str(quantity),
                'entry_price': format_price(entry_price, precision) if precision else str(entry_price),
                'exit_price': format_price(exit_price, precision) if precision else str(exit_price),
                'pnl': f"{pnl:.4f}" if pnl is not None else "0.0",
                'entry_timestamp': datetime.fromtimestamp(entry_ts).isoformat(),
                'exit_timestamp': datetime.fromtimestamp(exit_ts).isoformat(),
                'exit_reason': reason
            })
        logging.info(f"=== KRONIKA BITWY ZAPISANA: Symbol={symbol}, Strona={side}, PnL={pnl:.4f}, Powód Wyjścia='{reason}' ===")
    except Exception as e:
        logging.error(f"!!! Błąd zapisu historii transakcji: {e}")

# ====================================================================
#  "SOKOLE OKO" - RDZEŃ MONITOROWANIA POZYCJI
# ====================================================================

def price_monitor():
    logging.info(">>> SOKOLE OKO AKTYWOWANE <<<")
    while monitoring_active.is_set():
        try:
            state = load_state()
            if not state.get("in_position"):
                monitoring_active.clear()
                break
            
            symbol = state['symbol']
            side = state['side']
            tp_price = Decimal(state['take_profit_price'])
            current_price = get_current_price(symbol)

            if not current_price:
                time.sleep(10)
                continue

            if (side == 'long' and current_price >= tp_price) or \
               (side == 'short' and current_price <= tp_price):
                logging.info("$$$ SOKOLE OKO (TP): CEL OSIĄGNIĘTY! $$$")
                precision = get_precision_data(symbol)
                if precision:
                    close_position(exit_price=current_price, exit_reason="Take Profit")
                break
            
            time.sleep(5)
        except Exception as e:
            logging.error(f"!!! BŁĄD w wątku Sokole Oko: {e}", exc_info=True)
            time.sleep(30)
    logging.info(">>> SOKOLE OKO DEZAKTYWOWANE <<<")

def start_monitoring_thread():
    if not monitoring_active.is_set():
        monitoring_active.set()
        thread = threading.Thread(target=price_monitor, name="SokoleOkoThread")
        thread.daemon = True
        thread.start()

# ====================================================================
#  GŁÓWNE FUNKCJE HANDLOWE (Otwieranie / Zamykanie)
# ====================================================================

def _open_position_helper(side):
    state = load_state()
    if state.get("in_position"):
        logging.warning("Próba otwarcia nowej pozycji, gdy już jesteśmy w pozycji. Ignoruję.")
        return

    cfg = load_config()
    symbol = cfg['trade_symbol']
    quote_asset = cfg['quote_asset']
    
    precision = get_precision_data(symbol)
    if not precision:
        logging.error(f"Krytyczny błąd: Nie można otworzyć pozycji. Brak danych o precyzji dla {symbol}.")
        return

    usdc_balance = get_margin_balance(quote_asset)
    current_price = get_current_price(symbol)

    if usdc_balance <= 10 or not current_price:
        logging.error("Nie można otworzyć pozycji: za mało środków lub problem z pobraniem ceny.")
        return

    investment = usdc_balance * (Decimal(cfg.get("position_size_percent", 50.0)) / Decimal('100'))
    step_size = precision['STEP_SIZE']
    quantity = (investment / current_price / step_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * step_size
    
    if quantity == 0:
        logging.error("Obliczona ilość do zakupu jest zbyt mała.")
        return

    order_side = 'BUY' if side == 'long' else 'SELL'
    order_params = {'symbol': symbol, 'side': order_side, 'type': 'MARKET', 'quantity': format_quantity(quantity, precision)}
    
    logging.info(f">>> Składam zlecenie MARKET {order_side} dla {quantity} {symbol}")
    order_response = send_request('POST', '/order', order_params, signed=True, margin=True)
    
    if not (order_response and 'orderId' in order_response):
        logging.error(f"Błąd podczas otwierania pozycji {side.upper()}. Odpowiedź: {order_response}")
        return

    logging.info(f"Zlecenie {side.upper()} przyjęte [ID: {order_response['orderId']}]. Czekam 2s na zaksięgowanie...")
    time.sleep(2)
    
    entry_price = get_current_price(symbol)
    if not entry_price:
        logging.critical("Nie udało się pobrać ceny wejścia po otwarciu pozycji! Nie ustawiam SL i TP.")
        save_state({"in_position": True, "symbol": symbol, "side": side, "entry_price": "N/A", "quantity": str(quantity)})
        return

    sl_price = entry_price * (Decimal('1') - (Decimal(cfg.get("sl_percent", 2.0)) / Decimal('100'))) if side == 'long' else entry_price * (Decimal('1') + (Decimal(cfg.get("sl_percent", 2.0)) / Decimal('100')))
    sl_order_id = place_stop_loss_order(symbol, 'SELL' if side == 'long' else 'BUY', quantity, sl_price, precision)

    tp_factor = (Decimal('1') + (Decimal(cfg.get("tp_percent", 5.0)) / Decimal('100')))
    tp_price = entry_price * tp_factor if side == 'long' else entry_price / tp_factor

    new_state = {
        "in_position": True, "symbol": symbol, "side": side, "entry_price": str(entry_price), 
        "quantity": str(quantity), "stop_loss_id": sl_order_id,
        "take_profit_price": str(tp_price), "entry_timestamp": time.time()
    }
    save_state(new_state)
    start_monitoring_thread()
    logging.info(f"Pozycja {side.upper()} otwarta. Cena wejścia: {entry_price}, SL: {sl_price}, TP: {tp_price}")


def open_long_position():
    logging.info("--- Odebrano sygnał BUY. Inicjuję otwarcie pozycji LONG. ---")
    _open_position_helper('long')

def open_short_position():
    logging.info("--- Odebrano sygnał SELL. Inicjuję otwarcie pozycji SHORT. ---")
    # Logika dla short będzie wymagała zaciągnięcia pożyczki - do implementacji
    logging.warning("Logika pozycji SHORT nie jest jeszcze w pełni zaimplementowana w tym module.")
    # Na razie zostawiamy to puste, aby skupić się na reorganizacji
    # _open_position_helper('short')


def close_position(exit_price=None, exit_reason="N/A"):
    monitoring_active.clear()
    time.sleep(1)

    state = load_state()
    if not state.get("in_position"):
        logging.warning("Próba zamknięcia pozycji, gdy nie jesteśmy w pozycji. Ignoruję.")
        return

    symbol = state['symbol']
    side = state['side']
    quantity = Decimal(state['quantity'])
    entry_price = Decimal(state['entry_price'])
    entry_timestamp = state.get('entry_timestamp', time.time())
    
    if state.get('stop_loss_id'):
        cancel_order(symbol, state['stop_loss_id'])

    close_side = 'SELL' if side == 'long' else 'BUY'
    
    # Dla SHORTów, logika spłaty długu będzie tu potrzebna
    # Na razie uproszczona wersja
    
    precision = get_precision_data(symbol)
    if not precision:
        logging.error(f"Krytyczny błąd: Nie można zamknąć pozycji. Brak danych o precyzji dla {symbol}.")
        save_state({"in_position": False}) # Reset stanu, aby uniknąć blokady
        return

    close_params = {'symbol': symbol, 'side': close_side, 'type': 'MARKET', 'quantity': format_quantity(quantity, precision)}
    close_response = send_request('POST', '/order', close_params, signed=True, margin=True)

    if not (close_response and 'orderId' in close_response):
        logging.critical(f"!!! KRYTYCZNY BŁĄD: Nie udało się zamknąć pozycji! Odpowiedź: {close_response}")
        save_state({"in_position": False})
        return

    final_exit_price = exit_price if exit_price else get_current_price(symbol)
    if not final_exit_price: final_exit_price = entry_price 

    pnl = (final_exit_price - entry_price) * quantity if side == 'long' else (entry_price - final_exit_price) * quantity
    log_trade_history(symbol, side, quantity, entry_price, final_exit_price, entry_timestamp, time.time(), exit_reason, pnl, precision)
    
    logging.info(f"Pozycja {side.upper()} została zamknięta z powodu: '{exit_reason}'. PnL: {pnl:.4f}")
    save_state({"in_position": False})
