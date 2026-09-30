import sqlite3

conn = sqlite3.connect("data/precios.db")
cur = conn.cursor()

cur.execute("""
    SELECT
        tienda,
        vendedor,
        ean,
        producto,
        precio,
        precio_litro
    FROM precios
    WHERE producto = ?
    ORDER BY precio
""", ("Canasta Cream",))

print()
print("PRODUCTOS EN LA BASE DE DATOS")
print("=" * 70)

for fila in cur.fetchall():
    print(fila)

conn.close()