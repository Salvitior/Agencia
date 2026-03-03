#!/usr/bin/env python3
"""Test Duffel Payment Intent only."""
import requests, os, sys
sys.path.insert(0, '/var/www/agencia')
os.chdir('/var/www/agencia')
from dotenv import load_dotenv
load_dotenv()

token = os.getenv("DUFFEL_API_TOKEN")
headers = {
    "Authorization": f"Bearer {token}",
    "Duffel-Version": "v2",
    "Content-Type": "application/json",
}

r = requests.post(
    "https://api.duffel.com/payments/payment_intents",
    headers=headers,
    json={"data": {"amount": "10.00", "currency": "EUR"}},
    timeout=15,
)
print(f"Status: {r.status_code}")
import json
try:
    d = r.json()
    print(json.dumps(d, indent=2)[:1000])
except:
    print(r.text[:500])
