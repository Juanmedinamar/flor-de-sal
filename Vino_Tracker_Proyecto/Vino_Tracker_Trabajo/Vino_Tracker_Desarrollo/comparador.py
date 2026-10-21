from database import obtener_ultimos_precios


def mostrar_comparacion(producto):
    """Muestra la comparación de precios de un producto."""

    datos = obtener_ultimos_precios(producto)

    if not datos:
        print(f"\n❌ No hay precios registrados para {producto}.")
        return

    print()
    print("=" * 70)
    print(f"🍷 COMPARACIÓN DE PRECIOS — {producto.upper()}")
    print("=" * 70)

    precios_validos = []

    for dato in datos:

        (
            fecha,
            tienda,
            vendedor,
            producto_db,
            marca,
            formato,
            precio,
            precio_litro,
            stock,
            estado,
            fuente,
            url
        ) = dato

        # Solo mostramos productos con precio válido
        if precio is None:
            continue

        precios_validos.append(dato)

    if not precios_validos:
        print("❌ No hay precios válidos.")
        return

    # Ordenar por precio de botella
    precios_validos.sort(
        key=lambda x: x[6]
    )

    for posicion, dato in enumerate(precios_validos, start=1):

        (
            fecha,
            tienda,
            vendedor,
            producto_db,
            marca,
            formato,
            precio,
            precio_litro,
            stock,
            estado,
            fuente,
            url
        ) = dato

        if posicion == 1:
            medalla = "🥇"
        elif posicion == 2:
            medalla = "🥈"
        elif posicion == 3:
            medalla = "🥉"
        else:
            medalla = "  "

        vendedor_texto = vendedor or "No indicado"

        stock_texto = "Disponible" if stock else "Sin stock"

        print()
        print(f"{medalla} {tienda}")
        print(f"   Vendedor:       {vendedor_texto}")
        print(f"   Botella:        {precio:.2f} €")

        if precio_litro is not None:
            print(f"   Precio por litro: {precio_litro:.2f} €/L")

        print(f"   Formato:        {formato}")
        print(f"   Stock:          {stock_texto}")
        print(f"   Fuente:         {fuente or 'No indicada'}")

    # --------------------------------------------------------
    # MEJOR PRECIO
    # --------------------------------------------------------

    mejor = precios_validos[0]

    mejor_tienda = mejor[1]
    mejor_vendedor = mejor[2]
    mejor_precio = mejor[6]

    print()
    print("=" * 70)
    print("💰 MEJOR PRECIO")
    print("=" * 70)

    print(f"Tienda:       {mejor_tienda}")
    print(f"Vendedor:     {mejor_vendedor or 'No indicado'}")
    print(f"Precio:       {mejor_precio:.2f} €")

    if mejor[7] is not None:
        print(f"Precio/L:     {mejor[7]:.2f} €/L")

    # --------------------------------------------------------
    # AHORROS
    # --------------------------------------------------------

    print()
    print("📊 AHORRO FRENTE A OTRAS TIENDAS")
    print("-" * 70)

    for dato in precios_validos[1:]:

        tienda = dato[1]
        vendedor = dato[2]
        precio = dato[6]

        ahorro = precio - mejor_precio

        porcentaje = (
            ahorro / precio * 100
            if precio > 0
            else 0
        )

        print(
            f"{tienda} / {vendedor or 'No indicado'}: "
            f"{ahorro:.2f} € más "
            f"({porcentaje:.1f}%)"
        )

    print("=" * 70)


if __name__ == "__main__":

    mostrar_comparacion("Canasta Cream")