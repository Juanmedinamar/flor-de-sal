import sqlite3

DB = "data/precios.db"

conn = sqlite3.connect(DB)
cursor = conn.cursor()

# Actualizar Alcampo
cursor.execute("""
    UPDATE precios
    SET
        vendedor = 'Alcampo',
        estado = 'verificado',
        fuente = 'web'
    WHERE tienda = 'Alcampo'
      AND producto = 'Canasta Cream'
""")

print("Alcampo actualizado:", cursor.rowcount)


# Actualizar Carrefour
cursor.execute("""
    UPDATE precios
    SET
        vendedor = 'Vinopremier',
        estado = 'verificado',
        fuente = 'marketplace'
    WHERE tienda = 'Carrefour'
      AND producto = 'Canasta Cream'
""")

print("Carrefour actualizado:", cursor.rowcount)


conn.commit()
conn.close()

print("✅ Actualización terminada.")