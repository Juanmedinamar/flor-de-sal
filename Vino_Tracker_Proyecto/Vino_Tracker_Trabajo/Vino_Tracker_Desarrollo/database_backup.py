import sqlite3
from pathlib import Path

# Carpeta donde guardaremos la base de datos
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "precios.db"


def conectar():
    """Conecta con la base de datos."""
    return sqlite3.connect(DB_PATH)


def crear_tablas():
    """Crea las tablas necesarias si no existen."""

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS precios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            tienda TEXT NOT NULL,
            producto TEXT NOT NULL,
            marca TEXT,
            formato TEXT,
            precio REAL,
            precio_litro REAL,
            stock INTEGER,
            url TEXT
        )
    """)

    conn.commit()
    conn.close()

def calcular_precio_litro(precio, formato):
    """Calcula el precio por litro a partir del formato."""

    if precio is None or formato is None:
        return None

    texto = formato.lower().strip()

    try:
        if "cl" in texto:
            cantidad = float(
                texto.replace("cl", "").strip().replace(",", ".")
            )

            litros = cantidad / 100

        elif "ml" in texto:
            cantidad = float(
                texto.replace("ml", "").strip().replace(",", ".")
            )

            litros = cantidad / 1000

        elif "l" in texto:
            cantidad = float(
                texto.replace("l", "").strip().replace(",", ".")
            )

            litros = cantidad

        else:
            return None

        if litros <= 0:
            return None

        return precio / litros

    except (ValueError, TypeError):
        return None


def guardar_precio(
    tienda,
    producto,
    marca,
    formato,
    precio,
    stock,
    url
):
    """Guarda el precio solamente si ha cambiado."""

    conn = conectar()
    cursor = conn.cursor()

    # Comprobar el último registro de este producto en esta tienda
    cursor.execute("""
        SELECT precio, stock
        FROM precios
        WHERE tienda = ?
          AND producto = ?
        ORDER BY id DESC
        LIMIT 1
    """, (
        tienda,
        producto
    ))

    ultimo = cursor.fetchone()

    # Si existe un registro y no ha cambiado ni precio ni stock,
    # no creamos un duplicado.
    if ultimo is not None:
        ultimo_precio, ultimo_stock = ultimo

        if (
            ultimo_precio == precio
            and ultimo_stock == stock
        ):
            conn.close()

            print("ℹ️ El precio no ha cambiado. No se ha creado un duplicado.")

            return False

    # Calculamos precio por litro
    precio_litro = calcular_precio_litro(precio, formato)

    cursor.execute("""
        INSERT INTO precios (
            fecha,
            tienda,
            producto,
            marca,
            formato,
            precio,
            precio_litro,
            stock,
            url
        )
        VALUES (
            datetime('now', 'localtime'),
            ?, ?, ?, ?, ?, ?, ?, ?
        )
    """, (
        tienda,
        producto,
        marca,
        formato,
        precio,
        precio_litro,
        stock,
        url
    ))

    conn.commit()
    conn.close()

    print("✅ Nuevo precio guardado.")

    return True

def obtener_precios():
    """Obtiene todos los precios almacenados."""

    conn = conectar()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            fecha,
            tienda,
            producto,
            marca,
            formato,
            precio,
            precio_litro,
            stock,
            url
        FROM precios
        ORDER BY fecha DESC
    """)

    datos = cursor.fetchall()

    conn.close()

    return datos