import sys
import argparse
import inspect
import asyncio


# ============================================================
# UTF-8 WINDOWS
# ============================================================

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


# ============================================================
# IMPORTS
# ============================================================

from scrapers.carrefour import obtener_carrefour
from scrapers.alcampo import obtener_alcampo
from scrapers.bodeboca import obtener_bodeboca
from scrapers.hermanos_martin import obtener_hermanos_martin
from scrapers.corte_ingles import obtener_corte_ingles
from scrapers.hipercor import obtener_hipercor
from scrapers.makro import obtener_makro, MakroScraper
from scrapers.mercadona import obtener_mercadona
from scrapers.decantalo import obtener_decantalo
from scrapers.grauonline import obtener_grauonline
from scrapers.vinoseleccion import obtener_vinoseleccion


from database import (
    guardar_precio,
    obtener_ultimos_precios
)

from productos import (
    obtener_producto,
    obtener_nombres_productos
)


# ============================================================
# CONFIGURACIÓN DE TIENDAS
# ============================================================

TIENDAS = {
    "Carrefour": obtener_carrefour,
    "Alcampo": obtener_alcampo,
    "Bodeboca": obtener_bodeboca,
    "Hermanos Martin": obtener_hermanos_martin,
    "El Corte Inglés": obtener_corte_ingles,
    "Hipercor": obtener_hipercor,
    "Makro": obtener_makro,
    "Mercadona": obtener_mercadona,
    "Decántalo": obtener_decantalo,
    "Grau Online": obtener_grauonline,
    "Vinoselección": obtener_vinoseleccion,
}


# ============================================================
# GUARDAR PRODUCTO
# ============================================================

def guardar_producto(
    producto,
    producto_config
):

    # --------------------------------------------------------
    # SOLO GUARDAR RESULTADOS CORRECTOS
    # --------------------------------------------------------

    if producto.estado != "OK":

        print()
        print(
            f"⏭️ NO SE GUARDA EN BD: "
            f"{producto.producto}"
        )

        print(
            f"   🏪 Tienda: {producto.tienda}"
        )

        print(
            f"   📊 Estado: {producto.estado}"
        )

        print(
            f"   ℹ️ El historial de precios "
            f"se mantiene sin cambios."
        )
        

        return False

    # --------------------------------------------------------
    # COMPROBAR EAN
    # --------------------------------------------------------

    if producto.ean != producto_config.ean:

        raise ValueError(
            f"EAN incorrecto para "
            f"{producto.producto}: "
            f"{producto.ean} "
            f"(esperado {producto_config.ean})"
        )

    # --------------------------------------------------------
    # COMPROBAR PRECIO
    # --------------------------------------------------------

    if producto.precio is None:

        print()
        print(
            f"⏭️ NO SE GUARDA EN BD: "
            f"{producto.producto}"
        )

        print(
            f"   🏪 Tienda: {producto.tienda}"
        )

        print(
            f"   ⚠️ El resultado tiene "
            f"estado OK pero precio None."
        )

        return False

    # --------------------------------------------------------
    # GUARDAR EN BASE DE DATOS
    # --------------------------------------------------------

    guardar_precio(
        tienda=producto.tienda,
        producto=producto.producto,
        marca=producto.marca,
        formato=producto.formato,
        precio=producto.precio,
        stock=producto.stock,
        url=producto.url,
        vendedor=producto.vendedor,
        estado=producto.estado,
        fuente=producto.fuente,
        ean=producto.ean
    )

    return True


# ============================================================
# MOSTRAR RESULTADO
# ============================================================

def mostrar_resultado(producto):

    print()

    if producto.precio is not None:

        print(
            f"   💰 Precio: "
            f"{producto.precio:.2f} €"
        )

    print(
        f"   🏪 Vendedor: "
        f"{producto.vendedor or 'No indicado'}"
    )

    print(
        f"   📦 Formato: "
        f"{producto.formato}"
    )

    print(
        f"   📊 Stock: "
        f"{'Disponible' if producto.stock else 'Sin stock'}"
    )

    print(
        f"   🔗 Fuente: "
        f"{producto.fuente}"
    )


# ============================================================
# MOSTRAR ÚLTIMO PRECIO
# ============================================================

def mostrar_ultimo_precio(
    nombre_producto,
    tienda
):

    datos = obtener_ultimos_precios(
        nombre_producto
    )

    for dato in datos:

        (
            fecha,
            tienda_db,
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
        ) = dato

        if tienda_db != tienda:
            continue

        
        if precio is None:

            print()
            print(
                "   ℹ️ No existe ningún "
                "precio anterior válido."
            )

        else:

            print()
            print(
                "   ℹ️ Último precio conocido:"
            )

            print(
                f"      💰 Precio: "
                f"{precio:.2f} €"
            )

            print(
                f"      🏪 Vendedor: "
                f"{vendedor or 'No indicado'}"
            )

            print(
                f"      📦 Formato: "
                f"{formato or 'No indicado'}"
            )

            print(
                f"      📊 Stock: "
                f"{'Disponible' if stock else 'Sin stock'}"
            )

            print(
                f"      📅 Fecha: "
                f"{fecha}"
            )


        return

    print(
        "   ℹ️ No existe todavía ningún "
        "precio registrado para esta tienda."
    )


# ============================================================
# PROCESAR TIENDA
# ============================================================

def procesar_tienda(
    nombre_tienda,
    funcion,
    producto_config
):

    nombre_producto = producto_config.nombre

    print()
    print("=" * 80)

    print(
        f"🏪 {nombre_tienda.upper()} "
        f"→ {nombre_producto}"
    )

    print("=" * 80)

    # --------------------------------------------------------
    # COMPROBAR URL
    #
    # Makro es una excepción:
    # no necesitamos una URL específica del producto.
    # El scraper realiza la búsqueda directamente.
    # --------------------------------------------------------

    if nombre_tienda != "Makro":

        url = producto_config.urls.get(
            nombre_tienda
        )

        if not url:

            print()
            print(
                f"⏭️ {nombre_tienda}: "
                f"no existe URL configurada "
                f"para {nombre_producto}."
            )

            mostrar_ultimo_precio(
                nombre_producto,
                nombre_tienda
            )

            return "SIN_URL"

    # --------------------------------------------------------
    # EJECUTAR SCRAPER
    # --------------------------------------------------------

    try:

        resultado = funcion(
            producto_config
        )

        if inspect.iscoroutine(resultado):

            producto = asyncio.run(
                resultado
            )

        else:

            producto = resultado

        # ----------------------------------------------------
        # NO ENCONTRADO
        # ----------------------------------------------------

        if producto is None:

            print()
            print(
                f"🔴 {nombre_tienda}: "
                f"Producto no disponible → "
                f"{nombre_producto}"
            )

            mostrar_ultimo_precio(
                nombre_producto,
                nombre_tienda
            )

            return "NO_DISPONIBLE"

        # ----------------------------------------------------
        # COMPROBAR EAN
        # ----------------------------------------------------

        if not producto.ean:

            print(
                f"⚠️ {nombre_tienda}: "
                f"el producto no tiene EAN."
            )

        # ----------------------------------------------------
        # GUARDAR
        # ----------------------------------------------------

        guardado = guardar_producto(
            producto,
            producto_config
        )

        if not guardado:

            print()
            print(
                f"⚠️ {nombre_tienda}: "
                f"no se ha guardado ningún precio."
            )

            mostrar_resultado(
                producto
            )

            mostrar_ultimo_precio(
                nombre_producto,
                nombre_tienda
            )

            return "ERROR"

        print()
        print(
            f"✅ {nombre_tienda} "
            f"actualizado correctamente"
        )

        mostrar_resultado(
            producto
        )

        return "OK"
    

    # --------------------------------------------------------
    # ERROR
    # --------------------------------------------------------

    except Exception as e:

        print()
        print(
            f"⚠️ No se ha podido actualizar "
            f"{nombre_tienda}."
        )

        print(
            f"   Motivo: {e}"
        )

        mostrar_ultimo_precio(
            nombre_producto,
            nombre_tienda
        )

        return "ERROR"


# ============================================================
# PROCESAR MAKRO
# ============================================================

def procesar_makro(
    productos_config
):

    print()
    print("=" * 80)
    print("🏪 MAKRO — ACTUALIZACIÓN DE PRODUCTOS")
    print("=" * 80)

    print()
    print(
        f"🍷 Productos a buscar en Makro: "
        f"{len(productos_config)}"
    )

    scraper = MakroScraper(
        headless=False
    )

    resultados = {}

    try:

        # ----------------------------------------------------
        # ABRIR MAKRO UNA SOLA VEZ
        # ----------------------------------------------------

        if not scraper.abrir():

            print()
            print(
                "❌ No se pudo abrir Makro."
            )

            for producto_config in productos_config:

                resultados[
                    producto_config.nombre
                ] = False

            return resultados

        print()
        print("✅ MAKRO PREPARADO")

        # ----------------------------------------------------
        # BUSCAR TODOS LOS PRODUCTOS
        # ----------------------------------------------------

        for numero, producto_config in enumerate(
            productos_config,
            start=1
        ):

            nombre_producto = (
                producto_config.nombre
            )

            print()
            print("#" * 80)

            print(
                f"🍷 PRODUCTO "
                f"{numero}/{len(productos_config)}"
            )

            print("#" * 80)

            try:

                producto = scraper.buscar_producto(
                    producto_config
                )

                # ------------------------------------------------
                # NO ENCONTRADO
                # ------------------------------------------------

                if producto is None:

                    print()
                    print(
                        f"⚠️ Makro: "
                        f"no se ha podido obtener "
                        f"{nombre_producto}."
                    )

                    mostrar_ultimo_precio(
                        nombre_producto,
                        "Makro"
                    )

                    resultados[
                        nombre_producto
                    ] = False

                    continue

                # ------------------------------------------------
                # COMPROBAR EAN
                # ------------------------------------------------

                if not producto.ean:

                    print()
                    print(
                        f"⚠️ Makro: "
                        f"el producto no tiene EAN."
                    )

                # ------------------------------------------------
                # GUARDAR SOLO SI ES CORRECTO
                # ------------------------------------------------

                guardado = guardar_producto(
                    producto,
                    producto_config
                )

                if not guardado:

                    print()
                    print(
                        f"⚠️ Makro → "
                        f"{nombre_producto}: "
                        f"no se ha guardado ningún precio."
                    )

                    mostrar_resultado(
                        producto
                    )

                    mostrar_ultimo_precio(
                        nombre_producto,
                        "Makro"
                    )

                    resultados[
                        nombre_producto
                    ] = False

                    continue


                print()
                print(
                    f"✅ Makro → "
                    f"{nombre_producto} "
                    f"actualizado correctamente"
                )

                mostrar_resultado(
                    producto
                )

                resultados[
                    nombre_producto
                ] = True

            except Exception as e:

                print()
                print(
                    f"⚠️ Makro: error procesando "
                    f"{nombre_producto}"
                )

                print(
                    f"   Motivo: {e}"
                )

                mostrar_ultimo_precio(
                    nombre_producto,
                    "Makro"
                )

                resultados[
                    nombre_producto
                ] = False

    finally:

        # ----------------------------------------------------
        # CERRAR MAKRO UNA SOLA VEZ
        # ----------------------------------------------------

        scraper.cerrar()

    # --------------------------------------------------------
    # RESUMEN MAKRO
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("📊 RESUMEN MAKRO")
    print("=" * 80)

    for nombre_producto, correcto in resultados.items():

        if correcto:

            print(
                f"✅ {nombre_producto}: actualizado"
            )

        else:

            print(
                f"⚠️ {nombre_producto}: "
                f"no actualizado"
            )

    return resultados


# ============================================================
# ACTUALIZAR PRODUCTO
# ============================================================

def actualizar_producto(
    nombre_producto,
    tiendas
):

    producto_config = obtener_producto(
        nombre_producto
    )

    # --------------------------------------------------------
    # PRODUCTO NO EXISTE
    # --------------------------------------------------------

    if producto_config is None:

        print()
        print(
            f"❌ Producto no encontrado: "
            f"{nombre_producto}"
        )

        print()
        print(
            "Productos disponibles:"
        )

        for nombre in obtener_nombres_productos():

            print(
                f"   • {nombre}"
            )

        return

    # --------------------------------------------------------
    # CABECERA
    # --------------------------------------------------------

    print()
    print()
    print("#" * 80)

    print(
        f"🍷 PRODUCTO: "
        f"{producto_config.nombre}"
    )

    print(
        f"🏷️ Marca: "
        f"{producto_config.marca}"
    )

    print(
        f"📦 Formato: "
        f"{producto_config.formato}"
    )

    print(
        f"🔢 EAN: "
        f"{producto_config.ean or 'PENDIENTE'}"
    )

    print("#" * 80)

    resultados = {}

    # --------------------------------------------------------
    # TIENDAS
    # --------------------------------------------------------

    for nombre_tienda in tiendas:

        # ----------------------------------------------------
        # MAKRO SE PROCESA APARTE
        #
        # Se omite aquí.
        # Se procesa después de reunir todos los productos.
        # ----------------------------------------------------

        if nombre_tienda == "Makro":

            continue

        funcion = TIENDAS.get(
            nombre_tienda
        )

        if funcion is None:

            print(
                f"⚠️ Tienda no configurada: "
                f"{nombre_tienda}"
            )

            resultados[
                nombre_tienda
            ] = "ERROR"

            continue

        resultados[
            nombre_tienda
        ] = procesar_tienda(

            nombre_tienda,

            funcion,

            producto_config
        )

    # --------------------------------------------------------
    # RESUMEN
    # --------------------------------------------------------

    print()
    print("=" * 80)

    print(
        f"📊 RESUMEN — "
        f"{nombre_producto}"
    )

    print("=" * 80)

    for tienda, estado in resultados.items():

        if estado == "OK":

            print(
                f"✅ {tienda}: actualizado"
            )

        elif estado == "SIN_URL":

            print(
                f"⚪ {tienda}: Sin URL configurada"
            )

        elif estado == "NO_DISPONIBLE":

            print(
                f"🔴 {tienda}: Producto no disponible"
            )

        elif estado == "ERROR":

            print(
                f"⚠️ {tienda}: Error durante la consulta"
            )

        else:

            print(
                f"⚠️ {tienda}: {estado}"
            )


# ============================================================
# MOSTRAR AYUDA
# ============================================================

def mostrar_ayuda():

    print()
    print("=" * 80)
    print("🍷 VINO TRACKER")
    print("=" * 80)

    print()
    print("Uso:")

    print()
    print(
        '   python actualizar_todo.py '
        '"Canasta Cream"'
    )

    print()
    print(
        '   python actualizar_todo.py '
        '"Canasta Cream" '
        '"Don Zoilo Pedro Ximénez"'
    )

    print()
    print(
        "Productos disponibles:"
    )

    for nombre in obtener_nombres_productos():

        print(
            f"   • {nombre}"
        )

    print()
    print(
        "Tiendas:"
    )

    for tienda in TIENDAS:

        print(
            f"   • {tienda}"
        )

    print()
    print("=" * 80)


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # ARGUMENTOS
    # --------------------------------------------------------

    parser = argparse.ArgumentParser(
        description="Vino Tracker - actualización de precios"
    )

    parser.add_argument(
        "--productos",
        type=str,
        default=None,
        help="Productos separados por |"
    )

    parser.add_argument(
        "--tiendas",
        type=str,
        default=None,
        help="Tiendas separadas por |"
    )

    args = parser.parse_args()

    # --------------------------------------------------------
    # PRODUCTOS
    # --------------------------------------------------------

    if args.productos:

        productos = [
            p.strip()
            for p in args.productos.split("|")
            if p.strip()
        ]

    else:

        productos = obtener_nombres_productos()

    # --------------------------------------------------------
    # TIENDAS
    # --------------------------------------------------------

    if args.tiendas:

        tiendas = [
            t.strip()
            for t in args.tiendas.split("|")
            if t.strip()
        ]

    else:

        tiendas = list(
            TIENDAS.keys()
        )

    # --------------------------------------------------------
    # CABECERA
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("🍷 VINO TRACKER")
    print("=" * 80)

    print()
    print("Productos seleccionados:")

    for producto in productos:

        print(
            f"   • {producto}"
        )

    print()
    print("Tiendas:")

    for tienda in tiendas:

        print(
            f"   • {tienda}"
        )

    # ========================================================
    # MAKRO
    #
    # Primero reunimos todos los productos y después
    # abrimos Makro una sola vez.
    # ========================================================

    if "Makro" in tiendas:

        productos_makro = []

        for nombre_producto in productos:

            producto_config = obtener_producto(
                nombre_producto
            )

            if producto_config is None:

                print()
                print(
                    f"⚠️ No se puede procesar Makro: "
                    f"producto no encontrado → "
                    f"{nombre_producto}"
                )

                continue

            productos_makro.append(
                producto_config
            )

        if productos_makro:

            procesar_makro(
                productos_makro
            )

    # ========================================================
    # RESTO DE TIENDAS
    # ========================================================

    for nombre_producto in productos:

        actualizar_producto(
            nombre_producto,
            tiendas
        )

    # --------------------------------------------------------
    # FIN
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("✅ VINO TRACKER HA TERMINADO")
    print("=" * 80)


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":

    main()