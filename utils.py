
import requests
import time

API_KEY = "2c70587e2df4779"
API_SECRET = "56331804ac8ca7b"

def send_to_einvoice_system(invoice_data, retries=3, delay=2):
    url = "https://api.einvoice.example.com/generate"  # Replace with actual endpoint

    headers = {
        "Content-Type": "application/json",
        "API-KEY": API_KEY,
        "API-SECRET": API_SECRET
    }

    for attempt in range(retries):
        try:
            response = requests.post(url, json=invoice_data, headers=headers)

            if response.status_code == 200:
                print(" E-Invoice generated successfully!")
                return response.json()
            else:
                print(f"Failed! Status code: {response.status_code}, Message: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")

        print(f"Retrying in {delay} seconds... ({attempt + 1}/{retries})")
        time.sleep(delay)

    print(" All retries failed.")
    return None
