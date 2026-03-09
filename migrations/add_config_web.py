"""
Crea la tabla config_web e inserta claves por defecto para contenido editable.
Ejecutar: python migrations/add_config_web.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULTS = [
    ("hero_etiqueta", "DISEÑAMOS TUS SUEÑOS", "Etiqueta pequeña sobre el título (portada)"),
    ("hero_titulo", "El mundo te espera.", "Título principal de la portada (línea 1)"),
    ("hero_titulo_2", "Nosotros te llevamos.", "Título principal de la portada (línea 2)"),
    ("contacto_direccion", "Calle Mayor, 12, Carcaixent", "Dirección de la oficina"),
    ("contacto_telefono", "+34 961 234 567", "Teléfono de contacto"),
    ("contacto_whatsapp", "+34961234567", "Número WhatsApp (sin espacios)"),
    ("contacto_mapa_url", "https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d12365.111!2d-0.45!3d39.12!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0xd6196...!2sCarcaixent!5e0!3m2!1ses!2ses!4v1700000000000", "URL iframe de Google Maps"),
    ("contacto_titulo_form", "The Briefing", "Título del formulario de contacto"),
    ("contacto_subtitulo_form", "Rellena los detalles para que Andrea prepare una propuesta a medida.", "Subtítulo del formulario"),
    ("contacto_imagen_url", "https://images.unsplash.com/photo-1497366216548-37526070297c?q=80&w=1000", "URL imagen de la oficina"),
    ("footer_texto", "© Viatges Carcaixent. Todos los derechos reservados.", "Texto del pie de página"),
    ("nombre_agencia", "Viatges Carcaixent", "Nombre de la agencia (títulos, etc.)"),
]


def run():
    from database.connection import engine
    from database.models import Base, ConfigWeb
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        Base.metadata.create_all(engine, tables=[ConfigWeb.__table__])
        print("  Tabla config_web creada o ya existe.")
        for clave, valor, desc in DEFAULTS:
            existing = session.query(ConfigWeb).filter_by(clave=clave).first()
            if not existing:
                session.add(ConfigWeb(clave=clave, valor=valor, descripcion=desc))
                print(f"  + {clave}")
        session.commit()
        print("\n✅ Migración config_web completada.")
    except Exception as e:
        session.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        session.close()


if __name__ == '__main__':
    print("🔧 Creando config_web e insertando valores por defecto...")
    run()
