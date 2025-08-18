import requests
import time

API_URL = "https://buildwithhussain.com/api/v2/method/get_arn_number"
API_KEY = "2c70587e2df4779"
API_SECRET = "56331804ac8ca7b" 

HEADERS = {
    "Authorization": f"token {API_KEY}:{API_SECRET}",
    "Content-Type": "application/json"
}

payload = {
    "user_name": "Sanku Sodhi",
    "invoice_number": "INV-2025-001"
}

def make_request_with_retries(url, headers, data, retries=3, delay=2):
    for attempt in range(1, retries + 1):
        try:
            print(f"Attempt {attempt}...")
            response = requests.post(url, json=data, headers=headers)

            if response.status_code == 200:
                print(" Success!")
                return response.json()

            print(f" Failed with status code {response.status_code}: {response.text}")
        except requests.RequestException as e:
            print(f" Exception: {e}")

        if attempt < retries:
            print(f" Retrying in {delay} seconds...\n")
            time.sleep(delay)
    print(" All retry attempts failed.")
    return None

result = make_request_with_retries(API_URL, HEADERS, payload)

if result:
    print("\n Response from API:")
    print(result)
else:
    print("\n Could not retrieve ARN.")

