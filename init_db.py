from pathlib import Path
from db import get_connection


def aplicar_script(caminho):
    sql = Path(caminho).read_text(encoding="utf-8")
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
        print(f"Script aplicado com sucesso: {caminho}")
    finally:
        conn.close()


if __name__ == "__main__":
    aplicar_script("banco/schema.sql")
