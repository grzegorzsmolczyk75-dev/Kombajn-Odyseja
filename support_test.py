import requests
import hmac
import hashlib
import time
import urllib.parse

# !!! WAŻNE: Wklej tutaj swoje PRAWDZIWE klucze API !!!
api_key = "KlU0TAKpDg5qWqx3De3rWFNFnUBjNIRjmWRxPoFFMJ5Fb8f8tY2zYpyE6Wpt5vcx"
secret_key ="cH9K3QdSxOIYJKcdYxHUIz8zYSaSAROPZ1GpKzePL4bKnBtPZPILO5U4JCBXs70j"

base_url = "https://api.binance.com"
path = '/api/v3/account'
timestamp = round(time.time() * 1000)
params = {
    "timestamp": timestamp
}
querystring = urllib.parse.urlencode(params)
signature = hmac.new(secret_key.encode('utf-8'), msg=querystring.encode('utf-8'), digestmod=hashlib.sha256).hexdigest()
url = base_url + path + '?' + querystring + '&signature=' + signature

print("--- Uruchamiam skrypt od supportu Binance ---")
print(f"Wygenerowany URL: {url}")

headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'X-MBX-APIKEY': api_key
}
response = requests.request("GET", url, headers=headers)
result = response.json()

print("--- Otrzymany wynik ---")
print(result)
