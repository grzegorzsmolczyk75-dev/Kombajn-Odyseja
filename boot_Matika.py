# --- Importowanie niezbędnych bibliotek ---
from flask import Flask, request
import json

# --- Konfiguracja aplikacji Flask ---
# Tworzymy instancję aplikacji. To jest nasz główny serwer.
app = Flask(__name__)

# --- Główny punkt wejścia dla alertów z TradingView ---
# Definiujemy, co ma się stać, gdy ktoś wyśle dane na adres serwera,
# np. http://45.130.167.19:5000/webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        # Pobieramy surowe dane wysłane w alercie
        data = request.data.decode('utf-8')
        
        # Wyświetlamy otrzymane dane w konsoli serwera
        # To kluczowy krok do debugowania! Zobaczysz tutaj, co wysyła TradingView.
        print("--- Otrzymano nowy alert: ---")
        print(data)
        print("------------------------------")

        # Tutaj w przyszłości będzie logika składania zleceń na Binance
        # Na przykład:
        # if "buy" in data:
        #     print("Wykryto sygnał KUPNA. Składam zlecenie...")
        # elif "sell" in data:
        #     print("Wykryto sygnał SPRZEDAŻY. Składam zlecenie...")

        # Zwracamy odpowiedź "OK", żeby TradingView wiedziało, że alert dotarł
        return 'Alert received successfully', 200
        
    except Exception as e:
        # Obsługa ewentualnych błędów
        print(f"Wystąpił błąd: {e}")
        return 'Error processing request', 400

# --- Uruchomienie serwera ---
# Ten fragment sprawia, że serwer startuje, gdy uruchamiamy plik `python3 bot.py`
# Nasłuchuje na wszystkich interfejsach sieciowych (host='0.0.0.0') na porcie 5000
if __name__ == "__main__":
    print("Serwer bota tradingowego został uruchomiony.")
    print("Oczekuje na alerty pod adresem /webhook...")
    app.run(host='0.0.0.0', port=5000)
