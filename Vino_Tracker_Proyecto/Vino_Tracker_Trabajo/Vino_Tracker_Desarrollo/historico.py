from database import obtener_precios


def mostrar_historico(producto):

    datos = obtener_precios()

    datos = [
        dato
        for dato in datos
        if dato[3] == producto
    ]

    if not datos:

        print(
            f"\n❌ No hay histórico para {producto}."
        )

        return

    print()
    print("=" * 80)
    print(f"📈 HISTÓRICO DE PRECIOS — {producto.upper()}")
    print("=" * 80)

    # --------------------------------------------------------
    # Agrupar por tienda
    # --------------------------------------------------------

    tiendas = {}

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

        if tienda not in tiendas:
            tiendas[tienda] = []

        tiendas[tienda].append(dato)

    # --------------------------------------------------------
    # Mostrar cada tienda
    # --------------------------------------------------------

    for tienda, registros in tiendas.items():

        # El histórico viene ordenado descendente.
        # Lo invertimos para mostrarlo cronológicamente.

        registros = list(reversed(registros))

        print()
        print(f"🏪 {tienda}")
        print("-" * 80)

        precio_anterior = None

        for dato in registros:

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

            fecha_mostrar = fecha[:16]

            if precio is None:

                print(
                    f"{fecha_mostrar}  "
                    f"Sin precio"
                )

                continue

            # --------------------------------------------
            # Detectar cambio
            # --------------------------------------------

            cambio = ""

            if precio_anterior is not None:

                diferencia = precio - precio_anterior

                if diferencia > 0:

                    porcentaje = (
                        diferencia /
                        precio_anterior *
                        100
                    )

                    cambio = (
                        f" 📈 +{diferencia:.2f} € "
                        f"(+{porcentaje:.1f}%)"
                    )

                elif diferencia < 0:

                    porcentaje = (
                        abs(diferencia) /
                        precio_anterior *
                        100
                    )

                    cambio = (
                        f" 📉 {diferencia:.2f} € "
                        f"(-{porcentaje:.1f}%)"
                    )

                else:

                    cambio = " ➡️ Sin cambios"

            print(
                f"{fecha_mostrar}  "
                f"{precio:.2f} €"
                f"{cambio}"
            )

            precio_anterior = precio

    print()
    print("=" * 80)


if __name__ == "__main__":

    mostrar_historico("Canasta Cream")