# ====================================================================
#  PROJEKT "ODYSEJA" - MODUŁ NASŁUCHIWACZA SYGNAŁÓW
#  Data modyfikacji: 14.09.2025
#  Opis: Ten moduł działa jako niezależny serwer, który tylko
#  nasłuchuje webhooków i przekazuje polecenia do bot_logic.py.
# ====================================================================
import json
import logging
from flask import Flask, request
from waitress import serve

# Importujemy funkcje z naszego nowego "Mózgu"
from bot_logic import (
    load_state,
    open_long_position,
    open_short_position,
    close_position
)

# --- Inicjalizacja Aplikacji i Logowania ---
app = Flask('webhook_listener')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ====================================================================
#  GŁÓWNY PUNKT NASŁUCHU
# ====================================================================

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Odbiera sygnał, analizuje go i wydaje rozkaz do modułu logiki.
    """
    try:
        data = request.json
        action = data.get('action')
        logging.info(f"Odebrano sygnał webhook: {action}")

        state = load_state()
        
        if not state.get("in_position"):
            if action == 'buy':
                open_long_position()
            elif action == 'sell':
                # Pamiętaj, że logika short jest na razie pusta w bot_logic.py
                open_short_position()
        else: # Jeśli jesteśmy w pozycji
            current_side = state.get("side")
            # Sygnał przeciwny do obecnej pozycji -> zamknij pozycję
            if (action == 'buy' and current_side == 'short') or \
               (action == 'sell' and current_side == 'long'):
                logging.info(f"Odebrano sygnał przeciwny. Zamykam pozycję {current_side.upper()}.")
                close_position(exit_reason="Sygnał przeciwny")

        return "Webhook przetworzony.", 200
    except Exception as e:
        logging.error(f"!!! KRYTYCZNY BŁĄD w obsłudze webhooka: {e}", exc_info=True)
        return "Wewnętrzny błąd serwera", 500

# ====================================================================
#  URUCHOMIENIE SERWERA NASŁUCHIWACZA
# ====================================================================

if __name__ == '__main__':
    # Używamy innego portu niż dla panelu, aby uniknąć konfliktu!
    PORT = 5002
    logging.info(f">>> URUCHAMIANIE SERWERA 'NASŁUCHIWACZA' NA PORCIE {PORT} <<<")
    serve(app, host='0.0.0.0', port=PORT, threads=4)
