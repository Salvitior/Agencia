"""
Migración: Añadir columnas de oferta a la tabla tours.
Ejecutar: python migrations/add_tour_oferta_columns.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def migrate():
    from database.connection import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    columns = [
        ("es_oferta", "BOOLEAN DEFAULT FALSE"),
        ("descuento_pct", "DOUBLE PRECISION"),
        ("texto_oferta", "VARCHAR(120)"),
        ("fecha_fin_oferta", "DATE"),
    ]
    try:
        for col, col_type in columns:
            try:
                cursor.execute(f"ALTER TABLE tours ADD COLUMN IF NOT EXISTS {col} {col_type};")
                print(f"  + {col}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print(f"  (columna {col} ya existe)")
                else:
                    raise
        conn.commit()
        print("\n✅ Migración tours oferta completada.")
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    print("🔧 Añadiendo columnas de oferta a tours...")
    migrate()
