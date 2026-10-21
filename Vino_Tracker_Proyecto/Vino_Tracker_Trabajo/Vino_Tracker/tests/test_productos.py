import pytest
from productos import (
    Producto,
    obtener_producto,
    obtener_productos,
    obtener_nombres_productos,
    PRODUCTOS,
)


class TestObtenerProducto:
    def test_producto_existente(self):
        producto = obtener_producto("Canasta Cream")
        assert producto is not None
        assert producto.nombre == "Canasta Cream"
        assert producto.marca == "Williams & Humbert"
        assert producto.ean == "8410028030903"
        assert producto.formato == "75 cl"

    def test_producto_no_existente(self):
        assert obtener_producto("Vino Inexistente") is None

    def test_producto_case_sensitive(self):
        assert obtener_producto("canasta cream") is None


class TestObtenerProductos:
    def test_todos_los_productos(self):
        productos = obtener_productos()
        assert len(productos) == 4
        assert "Canasta Cream" in productos
        assert "Gran Duque de Alba" in productos
        assert "Don Zoilo Pedro Ximénez" in productos
        assert "Tío Pepe" in productos

    def test_tipos_correctos(self):
        productos = obtener_productos()
        for producto in productos.values():
            assert isinstance(producto, Producto)


class TestObtenerNombres:
    def test_nombres_productos(self):
        nombres = obtener_nombres_productos()
        assert len(nombres) == 4
        assert "Canasta Cream" in nombres
        assert "Tío Pepe" in nombres


class TestCatalogo:
    def test_canasta_cream_urls(self):
        producto = obtener_producto("Canasta Cream")
        assert "Carrefour" in producto.urls
        assert "Alcampo" in producto.urls
        assert "Makro" in producto.urls
        assert "Mercadona" in producto.urls

    def test_gran_duque_urls_parciales(self):
        producto = obtener_producto("Gran Duque de Alba")
        assert producto.urls["Carrefour"] is not None
        assert producto.urls["Alcampo"] is None
        assert producto.urls["Bodeboca"] is None

    def test_tio_pepe_urls_parciales(self):
        producto = obtener_producto("Tío Pepe")
        assert producto.urls["Carrefour"] is not None
        assert producto.urls["Vinoselección"] is not None
        assert producto.urls["Alcampo"] is None

    def test_ean_unicos(self):
        eans = [p.ean for p in PRODUCTOS.values()]
        assert len(eans) == len(set(eans))

    def test_marcas_correctas(self):
        assert obtener_producto("Canasta Cream").marca == "Williams & Humbert"
        assert obtener_producto("Gran Duque de Alba").marca == "Williams & Humbert"
        assert obtener_producto("Don Zoilo Pedro Ximénez").marca == "Williams & Humbert"
        assert obtener_producto("Tío Pepe").marca == "González Byass"
