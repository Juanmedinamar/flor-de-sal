import sqlite3
from pathlib import Path


# ============================================================
# CONFIGURACIÓN
# ============================================================

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "precios.db"


# ============================================================
# CONEXIÓN
# ============================================================

def conectar():
    """Conecta con la base de datos SQLite."""
    return sqlite3.connect(DB_PATH)


# ============================================================
# CREACIÓN / ACTUALIZACIÓN DE TABLAS
# ============================================================

def crear_tablas():
    """
    Crea la tabla de precios si no existe.

    También añade las columnas nuevas si estamos
    actualizando una base de datos antigua.
    """

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS precios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            tienda TEXT NOT NULL,
            vendedor TEXT,
            ean TEXT,
            producto TEXT NOT NULL,
            marca TEXT,
            formato TEXT,
            precio REAL,
            precio_litro REAL,
            stock INTEGER,
            estado TEXT,
            fuente TEXT,
            url TEXT
        )
    """)

    # --------------------------------------------------------
    # Comprobar columnas existentes
    # --------------------------------------------------------

    cursor.execute("PRAGMA table_info(precios)")

    columnas = {
        fila[1]
        for fila in cursor.fetchall()
    }

    columnas_nuevas = {
        "vendedor": "TEXT",
        "ean": "TEXT",
        "estado": "TEXT",
        "fuente": "TEXT"
    }

    for columna, tipo in columnas_nuevas.items():

        if columna not in columnas:

            cursor.execute(
                f"ALTER TABLE precios ADD COLUMN {columna} {tipo}"
            )

    conn.commit()
    conn.close()


# ============================================================
# PRECIO POR LITRO
# ============================================================

def calcular_precio_litro(precio, formato):
    """
    Calcula el precio por litro a partir del formato.

    Ejemplos:

        8.20 + 75 cl  -> 10.9333 €/L
        6.50 + 50 cl  -> 13.00 €/L
        12.00 + 1 L   -> 12.00 €/L
    """

    if precio is None or formato is None:
        return None

    texto = formato.lower().strip()

    try:

        if "cl" in texto:

            cantidad = float(
                texto
                .replace("cl", "")
                .strip()
                .replace(",", ".")
            )

            litros = cantidad / 100

        elif "ml" in texto:

            cantidad = float(
                texto
                .replace("ml", "")
                .strip()
                .replace(",", ".")
            )

            litros = cantidad / 1000

        elif "l" in texto:

            cantidad = float(
                texto
                .replace("l", "")
                .strip()
                .replace(",", ".")
            )

            litros = cantidad

        else:
            return None

        if litros <= 0:
            return None

        return round(precio / litros, 4)

    except (ValueError, TypeError):

        return None


# ============================================================
# GUARDAR PRECIO
# ============================================================

def guardar_precio(
    tienda,
    producto,
    marca,
    formato,
    precio,
    stock,
    url,
    vendedor=None,
    estado="actualizado",
    fuente="web",
    ean=None
):
    """
    Guarda un precio en la base de datos.

    Comportamiento:

    - Si el resultado NO es válido, no se guarda.
    - Si no existe un registro anterior, se crea.
    - Si cambia precio o stock, se crea un nuevo registro.
    - Si precio y stock no cambian, se actualizan los metadatos
      del último registro y NO se crea un duplicado.
    """

    # --------------------------------------------------------
    # Validaciones
    # --------------------------------------------------------

    if estado != "OK":
        print(
            f"⏭️ No se guarda el resultado de {tienda}: "
            f"estado={estado}"
        )
        return False

    if precio is None:
        print(
            f"⏭️ No se guarda el resultado de {tienda}: "
            f"precio=None"
        )
        return False

    # --------------------------------------------------------
    # Conexión
    # --------------------------------------------------------

    conn = conectar()
    cursor = conn.cursor()

    # --------------------------------------------------------
    # Calcular precio por litro
    # --------------------------------------------------------

    precio_litro = calcular_precio_litro(
        precio,
        formato
    )

    # --------------------------------------------------------
    # Buscar último registro de esta tienda + EAN
    # --------------------------------------------------------

    cursor.execute("""
        SELECT
            id,
            precio,
            stock
        FROM precios
        WHERE tienda = ?
          AND ean = ?
        ORDER BY id DESC
        LIMIT 1
    """, (
        tienda,
        ean
    ))

    ultimo = cursor.fetchone()

    # --------------------------------------------------------
    # Si existe un registro anterior
    # --------------------------------------------------------

    if ultimo is not None:

        ultimo_id, ultimo_precio, ultimo_stock = ultimo

        # ----------------------------------------------------
        # PRECIO Y STOCK NO HAN CAMBIADO
        # ----------------------------------------------------

        if (
            ultimo_precio == precio
            and ultimo_stock == int(stock)
        ):

            cursor.execute("""
                UPDATE precios
                SET
                    fecha = datetime('now', 'localtime'),
                    vendedor = ?,
                    ean = ?,
                    producto = ?,
                    marca = ?,
                    formato = ?,
                    precio_litro = ?,
                    stock = ?,
                    estado = ?,
                    fuente = ?,
                    url = ?
                WHERE id = ?
            """, (
                vendedor,
                ean,
                producto,
                marca,
                formato,
                precio_litro,
                int(stock),
                estado,
                fuente,
                url,
                ultimo_id
            ))

            conn.commit()
            conn.close()

            print(
                "ℹ️ Precio y stock sin cambios. "
                "Registro existente actualizado correctamente."
            )

            # IMPORTANTE:
            # True significa que el resultado del scraper
            # se ha procesado correctamente.
            return True

    # --------------------------------------------------------
    # PRECIO O STOCK HAN CAMBIADO
    # --------------------------------------------------------

    cursor.execute("""
        INSERT INTO precios (
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
        )
        VALUES (
            datetime('now', 'localtime'),
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """, (
        tienda,
        vendedor,
        ean,
        producto,
        marca,
        formato,
        precio,
        precio_litro,
        int(stock),
        estado,
        fuente,
        url
    ))

    conn.commit()
    conn.close()

    print("✅ Nuevo precio guardado.")

    return True


# ============================================================
# OBTENER HISTÓRICO
# ============================================================

def obtener_precios():
    """
    Obtiene todos los precios almacenados.
    """

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            fecha,
            tienda,
            vendedor,
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
        ORDER BY fecha DESC
    """)

    datos = cursor.fetchall()

    conn.close()

    return datos


# ============================================================
# ÚLTIMOS PRECIOS
# ============================================================

def obtener_ultimos_precios(producto=None):
    """
    Obtiene el último precio registrado
    para cada tienda y EAN.
    """

    conn = conectar()
    cursor = conn.cursor()

    if producto:

        cursor.execute("""
            SELECT
                p.fecha,
                p.tienda,
                p.vendedor,
                p.producto,
                p.marca,
                p.formato,
                p.precio,
                p.precio_litro,
                p.stock,
                p.estado,
                p.fuente,
                p.url

            FROM precios p

            INNER JOIN (
                SELECT
                    tienda,
                    ean,
                    MAX(id) AS ultimo_id

                FROM precios

                WHERE producto = ?

                GROUP BY tienda, ean

            ) ultimos

            ON p.id = ultimos.ultimo_id

            ORDER BY p.precio ASC
        """, (producto,))

    else:

        cursor.execute("""
            SELECT
                p.fecha,
                p.tienda,
                p.vendedor,
                p.producto,
                p.marca,
                p.formato,
                p.precio,
                p.precio_litro,
                p.stock,
                p.estado,
                p.fuente,
                p.url

            FROM precios p

            INNER JOIN (
                SELECT
                    tienda,
                    ean,
                    MAX(id) AS ultimo_id

                FROM precios

                GROUP BY tienda, ean

            ) ultimos

            ON p.id = ultimos.ultimo_id

            ORDER BY p.precio ASC
        """)

    datos = cursor.fetchall()

    conn.close()

    return datos


# ============================================================
# PRUEBA
# ============================================================

if __name__ == "__main__":

    crear_tablas()

    print("✅ Base de datos preparada:")
    print(DB_PATH)