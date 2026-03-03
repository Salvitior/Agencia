"""
Migración: Añadir columnas faltantes a reservas_vuelo
Ejecutar: python3 migrations/add_missing_columns.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_db_connection


COLUMNS_TO_ADD = [
    ("nombre_cliente",              "VARCHAR(255)"),
    ("booking_reference",           "VARCHAR(100)"),
    ("numero_vuelo",                "VARCHAR(50)"),
    ("fecha_vuelo_ida",             "DATE"),
    ("moneda",                      "VARCHAR(3) DEFAULT 'EUR'"),
    ("duffel_payment_intent_id",    "VARCHAR(255)"),
    ("checkin_recordatorio_enviado", "BOOLEAN DEFAULT FALSE"),
]

INDEXES_TO_ADD = [
    ("idx_rv_booking_ref",          "booking_reference"),
    ("idx_rv_numero_vuelo",         "numero_vuelo"),
    ("idx_rv_fecha_vuelo_ida",      "fecha_vuelo_ida"),
    ("idx_rv_duffel_pi",            "duffel_payment_intent_id"),
]


def migrate():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1. Add columns
        for col_name, col_type in COLUMNS_TO_ADD:
            sql = f"ALTER TABLE reservas_vuelo ADD COLUMN IF NOT EXISTS {col_name} {col_type};"
            print(f"  + {col_name} ({col_type})")
            cursor.execute(sql)

        # 2. Add indexes
        for idx_name, col_name in INDEXES_TO_ADD:
            sql = f"CREATE INDEX IF NOT EXISTS {idx_name} ON reservas_vuelo ({col_name});"
            print(f"  + INDEX {idx_name}")
            cursor.execute(sql)

        # 3. Backfill booking_reference from notas
        cursor.execute("""
            UPDATE reservas_vuelo
            SET booking_reference = TRIM(SPLIT_PART(SPLIT_PART(notas, 'Booking Ref: ', 2), ' ', 1))
            WHERE booking_reference IS NULL
              AND notas LIKE '%Booking Ref:%';
        """)
        backfilled = cursor.rowcount
        print(f"  ✅ Backfilled {backfilled} booking references from notas")

        # 4. Backfill fecha_vuelo_ida from datos_vuelo JSON
        cursor.execute("""
            UPDATE reservas_vuelo
            SET fecha_vuelo_ida = (datos_vuelo::json->>'fecha_ida')::date
            WHERE fecha_vuelo_ida IS NULL
              AND datos_vuelo IS NOT NULL
              AND datos_vuelo::json->>'fecha_ida' IS NOT NULL;
        """)
        backfilled_dates = cursor.rowcount
        print(f"  ✅ Backfilled {backfilled_dates} flight dates from datos_vuelo")

        conn.commit()
        print("\n✅ Migración completada con éxito.")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error en migración: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    print("🔧 Migración: Añadiendo columnas faltantes a reservas_vuelo...")
    migrate()
