"""
Tasks module - delegates to core.security for all crypto operations.
This avoids duplicating encryption/hashing logic.
"""
from core.security import cifrar as cifrar_dato, descifrar as descifrar_dato, generar_hash_dni
from database import get_db_connection


# Ejemplo de cómo usarlo al guardar un pasajero:
def guardar_pasajero_seguro(id_expediente, nombre, dni):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    dni_cifrado = cifrar_dato(dni)       # Para recuperar (Fernet)
    dni_hash = generar_hash_dni(dni)    # Para buscar (SHA256)
    
    sql = """
        INSERT INTO pasajeros (id_expediente, nombre_completo, dni_pasaporte_encriptado, dni_blind_index)
        VALUES (%s, %s, %s, %s)
    """
    cursor.execute(sql, (id_expediente, nombre, dni_cifrado, dni_hash))
    conn.commit()
    conn.close()