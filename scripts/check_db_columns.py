#!/usr/bin/env python3
"""Verify duffel_payment_intent_id column exists after migration."""
import sys, os
sys.path.insert(0, '/var/www/agencia')
os.chdir('/var/www/agencia')

from database import get_db_session
from sqlalchemy import text

s = get_db_session()
r = s.execute(text(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name='reservas_vuelo' AND column_name LIKE '%payment%'"
))
cols = [row[0] for row in r]
print("Payment columns in reservas_vuelo:", cols)

if 'duffel_payment_intent_id' in cols:
    print("OK: duffel_payment_intent_id EXISTS")
else:
    print("MISSING: duffel_payment_intent_id NOT FOUND")

s.close()
