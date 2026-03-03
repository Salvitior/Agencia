"""
Configuración de conexión a PostgreSQL Docker
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
import os
from dotenv import load_dotenv

load_dotenv()

# Configuración desde variables de entorno
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME', 'agencia_db')

if not DB_PASSWORD:
    raise RuntimeError("❌ DB_PASSWORD no está configurado en .env. Es obligatorio.")

# URL de conexión PostgreSQL
DATABASE_URL = f'postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'

# Engine con configuración optimizada
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,              # Conexiones en pool
    max_overflow=40,           # Conexiones extra cuando hace falta
    pool_pre_ping=True,        # Verificar conexión antes de usar
    pool_recycle=3600,         # Reciclar conexiones cada hora
    echo=False,                # True para debug SQL
    connect_args={
        "options": "-c timezone=utc",
        "application_name": "agencia_tours"
    }
)

# Session factory con scoped_session para thread-safety
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)

def get_db():
    """
    Generador para usar con context manager o FastAPI Depends
    
    Uso:
        with get_db() as db:
            tours = db.query(Tour).all()
    """
    db = Session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def get_db_session():
    """
    Método legacy para compatibilidad con código existente
    IMPORTANTE: Cerrar manualmente con db.close()
    """
    return Session()

def close_session():
    """Cierra la sesión scoped"""
    Session.remove()

def get_db_connection():
    """
    Conexión raw de PostgreSQL para código legacy que usa cursors
    IMPORTANTE: Cerrar manualmente con conn.close()
    
    Uso:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM tabla")
        results = cursor.fetchall()
        conn.close()
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            port=int(DB_PORT),
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME,
            options="-c timezone=utc",
            application_name="agencia_tours"
        )
        return connection
    except Exception as e:
        print(f"❌ Error conectando a PostgreSQL: {e}")
        raise

def test_connection():
    """Verifica que la conexión a PostgreSQL funciona"""
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print(f"✅ Conectado a PostgreSQL:")
            print(f"   {version}")
            return True
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False
