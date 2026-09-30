from productos import obtener_producto
from scrapers.hermanos_martin import obtener_corte_ingles
producto = obtener_producto(
    "Canasta Cream"
)

resultado = obtener_corte_ingles(obtener_producto(
    "Canasta Cream")
)

print()
print("=" * 60)
print("RESULTADO")
print("=" * 60)

print(
    "Tienda:",
    resultado.tienda
)

print(
    "Producto:",
    resultado.producto
)

print(
    "Marca:",
    resultado.marca
)

print(
    "Formato:",
    resultado.formato
)

print(
    "Precio:",
    resultado.precio
)

print(
    "Stock:",
    resultado.stock
)

print(
    "Vendedor:",
    resultado.vendedor
)

print(
    "URL:",
    resultado.url
)