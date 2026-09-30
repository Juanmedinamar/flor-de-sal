import sqlite3

DB = "data/precios.db"

conn = sqlite3.connect(DB)
cur = conn.cursor()

# ============================================================
# TÍO PEPE — MERCADONA
# ============================================================

EAN = "8410023000031"
PRODUCTO = "Tío Pepe"
TIENDA = "Mercadona"

# ------------------------------------------------------------
# Mostrar todos los registros de Tío Pepe en Mercadona
# excepto el último.
# ------------------------------------------------------------

cur.execute("""
    SELECT
        id,
        fecha,
        tienda,
        vendedor,
        ean,
        producto,
        marca,
        formato,
        precio,
        precio_litro,
        stock,
        estado,
        fuente,
        url
    FROM precios
    WHERE tienda = ?
      AND ean = ?
      AND producto = ?
      AND id NOT IN (
          SELECT MAX(id)
          FROM precios
          WHERE tienda = ?
            AND ean = ?
            AND producto = ?
      )
    ORDER BY id
""", (
    TIENDA,
    EAN,
    PRODUCTO,
    TIENDA,
    EAN,
    PRODUCTO
))

registros = cur.fetchall()

print()
print("=" * 100)
print("🔎 DUPLICADOS — TÍO PEPE / MERCADONA")
print("=" * 100)

if registros:

    for registro in registros:
        print()
        print(f"ID          : {registro[0]}")
        print(f"Fecha       : {registro[1]}")
        print(f"Tienda      : {registro[2]}")
        print(f"Vendedor    : {registro[3]}")
        print(f"EAN         : {registro[4]}")
        print(f"Producto    : {registro[5]}")
        print(f"Marca       : {registro[6]}")
        print(f"Formato     : {registro[7]}")
        print(f"Precio      : {registro[8]} €")
        print(f"Precio/litro: {registro[9]} €")
        print(f"Stock       : {registro[10]}")
        print(f"Estado      : {registro[11]}")
        print(f"Fuente      : {registro[12]}")
        print(f"URL         : {registro[13]}")

    print()
    print("-" * 100)
    print(f"Total de duplicados encontrados: {len(registros)}")

    respuesta = input(
        "\n⚠️ ¿Eliminar SOLO estos duplicados? (s/n): "
    )

    if respuesta.lower() == "s":

        cur.execute("""
            DELETE FROM precios
            WHERE tienda = ?
              AND ean = ?
              AND producto = ?
              AND id NOT IN (
                  SELECT MAX(id)
                  FROM precios
                  WHERE tienda = ?
                    AND ean = ?
                    AND producto = ?
              )
        """, (
            TIENDA,
            EAN,
            PRODUCTO,
            TIENDA,
            EAN,
            PRODUCTO
        ))

        conn.commit()

        print()
        print("✅ LIMPIEZA COMPLETADA")
        print(f"🗑️ Registros eliminados: {cur.rowcount}")

    else:
        print()
        print("❌ No se ha eliminado ningún registro.")

else:

    print()
    print("✅ NO HAY DUPLICADOS")
    print("   Tío Pepe → Mercadona")
    print()
    print("ℹ️ Se conserva el registro más reciente.")


# ============================================================
# VERIFICACIÓN FINAL
# ============================================================

print()
print("=" * 100)
print("🔍 VERIFICACIÓN FINAL — TÍO PEPE / MERCADONA")
print("=" * 100)

cur.execute("""
    SELECT
        id,
        fecha,
        tienda,
        vendedor,
        ean,
        producto,
        marca,
        formato,
        precio,
        precio_litro,
        stock,
        estado,
        fuente,
        url
    FROM precios
    WHERE tienda = ?
      AND ean = ?
      AND producto = ?
    ORDER BY id
""", (
    TIENDA,
    EAN,
    PRODUCTO
))

restantes = cur.fetchall()

if restantes:

    for registro in restantes:
        print()
        print(f"ID          : {registro[0]}")
        print(f"Fecha       : {registro[1]}")
        print(f"Tienda      : {registro[2]}")
        print(f"Vendedor    : {registro[3]}")
        print(f"EAN         : {registro[4]}")
        print(f"Producto    : {registro[5]}")
        print(f"Marca       : {registro[6]}")
        print(f"Formato     : {registro[7]}")
        print(f"Precio      : {registro[8]} €")
        print(f"Precio/litro: {registro[9]} €")
        print(f"Stock       : {registro[10]}")
        print(f"Estado      : {registro[11]}")
        print(f"Fuente      : {registro[12]}")
        print(f"URL         : {registro[13]}")

else:

    print("⚠️ No quedan registros de Tío Pepe en Mercadona.")


conn.close()

print()
print("=" * 100)
print("🏁 FIN DE LA LIMPIEZA")
print("=" * 100)