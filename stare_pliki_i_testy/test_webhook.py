import requests
import time

url = "http://localhost:5000/webhook"  # adres lokalny bota

def send_signal(action):
    data = {"action": action}
    try:
        r = requests.post(url, json=data)
        print(f"Wysłano sygnał {action}, status: {r.status_code}, odpowiedź: {r.text}")
    except Exception as e:
        print(f"Błąd wysyłania sygnału {action}: {e}")

if __name__ == "__main__":
    print("Testowanie webhooka bota...")
    send_signal("buy")
    time.sleep(3)
    send_signal("sell")
    time.sleep(3)
    # Ponowne wysłanie, sprawdzenie blokowania duplikatu
    send_signal("sell")
    time.sleep(3)
    send_signal("buy")

