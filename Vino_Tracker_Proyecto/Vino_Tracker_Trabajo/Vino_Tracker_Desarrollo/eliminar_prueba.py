import sqlite3

conn = sqlite3.connect("data/precios.db")
cur = conn.cursor()

cur.execute("""
    DELETE FROM precios
    WHERE tienda = ?
      AND ean = ?
      AND precio = ?
""", (
    "Carrefour",
    "8410028030903",
    5.25
))

conn.commit()

print("Registros de prueba eliminados:", cur.rowcount)

conn.close()