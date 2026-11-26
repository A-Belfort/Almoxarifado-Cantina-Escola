import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise psycopg2.OperationalError("DATABASE_URL não configurada.")

    # Garante TLS/SSL ao conectar no Azure PostgreSQL caso não esteja na URL
    if "azure.com" in database_url and "sslmode=" not in database_url:
        return psycopg2.connect(database_url, sslmode="require", cursor_factory=RealDictCursor)

    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)
