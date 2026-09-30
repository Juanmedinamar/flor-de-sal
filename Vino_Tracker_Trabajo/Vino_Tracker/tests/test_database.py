import pytest
import sqlite3
from pathlib import Path
from unittest.mock import patch

from database import (
    conectar,
    crear_tablas,
    guardar_precio,
    obtener_precios,
    obtener_ultimos_precios,
    calcular_precio_litro,
)


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """Configura una base de datos temporal para cada test."""
    test_db = tmp_path / "test_precios.db"
    monkeypatch.setattr("database.DB_PATH", test_db)
    monkeypatch.setattr("database.DATA_DIR", tmp_path)
    crear_tablas()
    return test_db


class TestCalcularPrecioLitro:
    def test_botella_75cl(self):
        assert calcular_precio_litro(8.20, "75 cl") == pytest.approx(10.9333, rel=1e-3)

    def test_botella_50cl(self):
        assert calcular_precio_litro(6.50, "50 cl") == pytest.approx(13.0, rel=1e-3)

    def test_litro(self):
        assert calcular_precio_litro(12.00, "1 L") == pytest.approx(12.0, rel=1e-3)

    def test_precio_none(self):
        assert calcular_precio_litro(None, "75 cl") is None

    def test_formato_none(self):
        assert calcular_precio_litro(8.20, None) is None

    def test_formato_invalido(self):
        assert calcular_precio_litro(8.20, "caja") is None

    def test_cantidad_cero(self):
        assert calcular_precio_litro(8.20, "0 cl") is None


class TestCrearTablas:
    def test_tabla_creada(self, db_path):
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='precios'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_columnas_existen(self, db_path):
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(precios)")
        columnas = {fil[1] for fil in cursor.fetchall()}
        esperadas = {
            "id", "fecha", "tienda", "vendedor", "ean", "producto",
            "marca", "formato", "precio", "precio_litro", "stock",
            "estado", "fuente", "url"
        }
        assert esperadas.issubset(columnas)
        conn.close()


class TestGuardarPrecio:
    def test_guardar_correcto(self, db_path):
        resultado = guardar_precio(
            tienda="Carrefour",
            producto="Canasta Cream",
            marca="Williams & Humbert",
            formato="75 cl",
            precio=8.20,
            stock=1,
            url="https://www.carrefour.es/test",
            vendedor="Carrefour",
            estado="OK",
            fuente="web",
            ean="8410028030903"
        )
        assert resultado is True

    def test_no_guardar_estado_error(self, db_path):
        resultado = guardar_precio(
            tienda="Carrefour",
            producto="Canasta Cream",
            marca="Williams & Humbert",
            formato="75 cl",
            precio=8.20,
            stock=1,
            url="https://www.carrefour.es/test",
            estado="ERROR",
            ean="8410028030903"
        )
        assert resultado is False

    def test_no_guardar_precio_none(self, db_path):
        resultado = guardar_precio(
            tienda="Carrefour",
            producto="Canasta Cream",
            marca="Williams & Humbert",
            formato="75 cl",
            precio=None,
            stock=1,
            url="https://www.carrefour.es/test",
            estado="OK",
            ean="8410028030903"
        )
        assert resultado is False

    def test_actualizar_sin_cambios(self, db_path):
        # Guardar inicial
        guardar_precio(
            tienda="Carrefour",
            producto="Canasta Cream",
            marca="Williams & Humbert",
            formato="75 cl",
            precio=8.20,
            stock=1,
            url="https://www.carrefour.es/test",
            estado="OK",
            ean="8410028030903"
        )
        # Mismo precio y stock -> actualiza, no duplica
        guardar_precio(
            tienda="Carrefour",
            producto="Canasta Cream",
            marca="Williams & Humbert",
            formato="75 cl",
            precio=8.20,
            stock=1,
            url="https://www.carrefour.es/test",
            estado="OK",
            ean="8410028030903"
        )
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM precios WHERE tienda='Carrefour'")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 1

    def test_nuevo_registro_cambio_precio(self, db_path):
        # Guardar inicial
        guardar_precio(
            tienda="Carrefour",
            producto="Canasta Cream",
            marca="Williams & Humbert",
            formato="75 cl",
            precio=8.20,
            stock=1,
            url="https://www.carrefour.es/test",
            estado="OK",
            ean="8410028030903"
        )
        # Precio diferente -> nuevo registro
        guardar_precio(
            tienda="Carrefour",
            producto="Canasta Cream",
            marca="Williams & Humbert",
            formato="75 cl",
            precio=9.50,
            stock=1,
            url="https://www.carrefour.es/test",
            estado="OK",
            ean="8410028030903"
        )
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM precios WHERE tienda='Carrefour'")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 2


class TestObtenerPrecios:
    def test_obtener_todos_vacio(self, db_path):
        assert obtener_precios() == []

    def test_obtener_todos_con_datos(self, db_path):
        guardar_precio(
            tienda="Carrefour",
            producto="Canasta Cream",
            marca="Williams & Humbert",
            formato="75 cl",
            precio=8.20,
            stock=1,
            url="https://www.carrefour.es/test",
            estado="OK",
            ean="8410028030903"
        )
        datos = obtener_precios()
        assert len(datos) == 1
        assert datos[0][1] == "Carrefour"  # tienda
        assert datos[0][6] == 8.20  # precio

    def test_obtener_ultimos_precios_producto(self, db_path):
        guardar_precio(
            tienda="Carrefour",
            producto="Canasta Cream",
            marca="Williams & Humbert",
            formato="75 cl",
            precio=8.20,
            stock=1,
            url="https://www.carrefour.es/test",
            estado="OK",
            ean="8410028030903"
        )
        guardar_precio(
            tienda="Alcampo",
            producto="Canasta Cream",
            marca="Williams & Humbert",
            formato="75 cl",
            precio=9.00,
            stock=1,
            url="https://www.alcampo.es/test",
            estado="OK",
            ean="8410028030903"
        )
        datos = obtener_ultimos_precios("Canasta Cream")
        assert len(datos) == 2

    def test_obtener_ultimos_precios_ordenados(self, db_path):
        guardar_precio(
            tienda="Carrefour",
            producto="Canasta Cream",
            marca="Williams & Humbert",
            formato="75 cl",
            precio=10.00,
            stock=1,
            url="https://www.carrefour.es/test",
            estado="OK",
            ean="8410028030903"
        )
        guardar_precio(
            tienda="Alcampo",
            producto="Canasta Cream",
            marca="Williams & Humbert",
            formato="75 cl",
            precio=8.00,
            stock=1,
            url="https://www.alcampo.es/test",
            estado="OK",
            ean="8410028030903"
        )
        datos = obtener_ultimos_precios("Canasta Cream")
        assert datos[0][1] == "Alcampo"  # Más barato primero
        assert datos[1][1] == "Carrefour"
