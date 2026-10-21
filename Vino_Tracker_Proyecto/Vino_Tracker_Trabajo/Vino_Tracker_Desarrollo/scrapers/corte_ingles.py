# scrapers/corte_ingles.py

from dataclasses import dataclass
from typing import Optional
import re

from playwright.sync_api import sync_playwright


@dataclass
class ProductoPrecio:
    tienda: str
    vendedor: str
    ean: str
    producto: str
    marca: str
    formato: str
    precio: float
    stock: bool
    estado: str
    fuente: str
    url: str


def _extraer_precio_dom(page) -> Optional[float]:
    """
    Busca el precio principal del PDP en:

        .food-prices__price

    En Canasta Cream, por ejemplo, el DOM puede contener:

        7
        ,89 €

    y se convierte en:

        7.89

    """

    try:

        elementos = page.locator(
            ".food-prices__price"
        )

        cantidad = elementos.count()

        if cantidad == 0:

            return None

        print(
            f"💰 Elementos .food-prices__price "
            f"encontrados: {cantidad}"
        )

        precios = []

        for i in range(cantidad):

            try:

                texto = (
                    elementos
                    .nth(i)
                    .inner_text()
                    .strip()
                )

                texto_limpio = (
                    texto
                    .replace("\n", "")
                    .replace(" ", "")
                )

                match = re.search(
                    r"(\d+(?:[.,]\d{2}))\s*€?",
                    texto_limpio
                )

                if match:

                    valor = (
                        match.group(1)
                        .replace(",", ".")
                    )

                    precio = float(valor)

                    precios.append(precio)

                    print(
                        f"   {i + 1}. "
                        f"{texto!r} → "
                        f"{precio:.2f} €"
                    )

            except Exception:
                continue

        if not precios:

            return None

        # El primer precio corresponde al
        # producto principal del PDP.
        return precios[0]

    except Exception as e:

        print(
            f"⚠️ Error extrayendo precio DOM: {e}"
        )

        raise RuntimeError(
            f"Error extrayendo el precio "
            f"de El Corte Inglés: {e}"
        ) from e


def _extraer_stock(
    status_data: dict
) -> tuple[bool, int]:
    """
    Extrae disponibilidad y unidades
    desde STATUS FLOW.
    """

    try:

        offers = (
            status_data
            .get("availability", {})
            .get("offers", [])
        )

        if not offers:

            return False, 0

        oferta = offers[0]

        disponibilidad = (
            oferta.get("availability", {})
        )

        centros = disponibilidad.get(
            "centers",
            []
        )

        if not centros:

            return False, 0

        centro = centros[0]

        stock = centro.get(
            "stock",
            0
        )

        unidades = centro.get(
            "available_units",
            stock
        )

        home_delivery = (
            centro
            .get(
                "shipping_methods",
                {}
            )
            .get(
                "home_delivery",
                {}
            )
            .get(
                "is_available",
                False
            )
        )

        purchase_availability = (
            disponibilidad.get(
                "purchase_availability",
                ""
            )
        )

        disponible = (
            home_delivery
            and purchase_availability == "ADD"
            and unidades > 0
        )

        return (
            bool(disponible),
            int(unidades or 0)
        )

    except Exception as e:

        print(
            f"⚠️ Error leyendo stock: {e}"
        )

        # Un fallo leyendo stock NO debe
        # convertir una consulta con precio
        # válido en ERROR.
        return False, 0


def obtener_corte_ingles(
    producto_config
) -> Optional[ProductoPrecio]:

    """
    Obtiene precio y stock de un producto
    de El Corte Inglés.

    Clasificación:

    - URL inexistente:
        lo gestiona actualizar_todo.py.

    - Producto no encontrado:
        return None.

    - Producto explícitamente no disponible:
        return None.

    - Precio encontrado:
        devuelve ProductoPrecio con estado OK.

    - Error técnico:
        lanza RuntimeError para que
        actualizar_todo.py lo clasifique
        como ERROR.
    """

    if producto_config is None:

        raise ValueError(
            "No se ha recibido configuración "
            "de producto."
        )

    nombre = producto_config.nombre
    ean = str(producto_config.ean)
    marca = producto_config.marca
    formato = producto_config.formato

    url = producto_config.urls.get(
        "El Corte Inglés"
    )

    # --------------------------------------------------------
    # URL
    # --------------------------------------------------------

    if not url:

        print(
            "⚠️ El producto no tiene URL "
            "de El Corte Inglés."
        )

        return None

    print("\n" + "=" * 90)
    print("🏪 EL CORTE INGLÉS")
    print("=" * 90)

    print(
        f"📦 Producto : {nombre}"
    )

    print(
        f"🔢 EAN      : {ean}"
    )

    print(
        f"🔗 URL      : {url}"
    )

    status_data = None

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=False,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled"
            ]
        )

        context = browser.new_context(
            locale="es-ES",
            timezone_id="Europe/Madrid",
            viewport={
                "width": 1440,
                "height": 900
            },
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36"
            ),
            extra_http_headers={
                "Accept-Language":
                    "es-ES,es;q=0.9,en;q=0.8"
            }
        )

        page = context.new_page()

        # ----------------------------------------------------
        # CAPTURAR STATUS FLOW
        # ----------------------------------------------------

        def procesar_response(response):

            nonlocal status_data

            try:

                response_url = response.url

                if (
                    "/api/food-firefly/"
                    "status_flow/"
                    not in response_url
                ):
                    return

                if response.status != 200:

                    print(
                        "\n⚠️ STATUS FLOW "
                        f"HTTP {response.status}"
                    )

                    return

                print("\n📡 STATUS FLOW")

                print(
                    f"   STATUS: "
                    f"{response.status}"
                )

                print(
                    f"   URL   : "
                    f"{response_url}"
                )

                try:

                    data = response.json()

                    if isinstance(
                        data,
                        dict
                    ):

                        status_data = data

                except Exception:

                    pass

            except Exception:

                pass

        page.on(
            "response",
            procesar_response
        )

        try:

            # ------------------------------------------------
            # ABRIR PÁGINA
            # ------------------------------------------------

            print(
                "\n🌐 Abriendo "
                "El Corte Inglés..."
            )

            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            if response:

                print(
                    f"📄 Página HTTP STATUS: "
                    f"{response.status}"
                )

                # ------------------------------------------------
                # HTTP
                # ------------------------------------------------

                if response.status in (
                    404,
                    410
                ):

                    print(
                        "🔴 El producto "
                        "no existe en "
                        "El Corte Inglés "
                        f"(HTTP {response.status})."
                    )

                    return None

                if response.status >= 400:

                    raise RuntimeError(
                        "El Corte Inglés "
                        f"respondió con HTTP "
                        f"{response.status}."
                    )

            # ------------------------------------------------
            # ESPERAR APIs
            # ------------------------------------------------

            print(
                "⏳ Esperando carga "
                "de APIs..."
            )

            page.wait_for_timeout(
                25000
            )

            # ------------------------------------------------
            # ESPERAR PRECIO
            # ------------------------------------------------

            try:

                page.wait_for_selector(
                    ".food-prices__price",
                    timeout=15000
                )

                print(
                    "✅ .food-prices__price "
                    "encontrado"
                )

            except Exception:

                print(
                    "⚠️ No apareció "
                    ".food-prices__price"
                )

            # ------------------------------------------------
            # COMPROBAR TEXTO DE PÁGINA
            # ------------------------------------------------

            try:

                texto_pagina = (
                    page
                    .locator("body")
                    .inner_text()
                    .strip()
                )

            except Exception as e:

                raise RuntimeError(
                    "No se pudo leer el "
                    "contenido de la página "
                    f"de El Corte Inglés: {e}"
                ) from e

            texto_lower = (
                texto_pagina.lower()
            )

            # ------------------------------------------------
            # PRODUCTO NO ENCONTRADO
            # ------------------------------------------------

            nombre_lower = nombre.lower()

            frases_no_disponible = [
                "producto no disponible",
                "no disponible",
                "agotado",
                "sin stock",
                "producto no encontrado",
                "página no encontrada"
            ]

            # ---------------------------------------------------------
            # COMPROBACIÓN DEL PRODUCTO
            # ---------------------------------------------------------
            #
            # No exigimos que el nombre exacto configurado
            # aparezca literalmente en la página.
            #
            # El EAN ya está identificado en la URL/PDP y,
            # además, posteriormente comprobamos que exista
            # el precio del producto.
            #
            # Solo consideramos "no disponible" cuando ECI
            # muestra explícitamente alguna de estas frases.
            # ---------------------------------------------------------

            if any(
                frase in texto_lower
                for frase in frases_no_disponible
            ):
                print(
                    f"🔴 El Corte Inglés: "
                    f"{nombre} "
                    "no está disponible."
                )

                return None

            print(
                f"✅ Página del producto cargada "
                f"correctamente para {nombre}"
            )

            # ------------------------------------------------
            # PRECIO
            # ------------------------------------------------

            print("\n" + "=" * 90)
            print("💰 BUSCANDO PRECIO PDP")
            print("=" * 90)

            precio = _extraer_precio_dom(
                page
            )

            # ------------------------------------------------
            # PRECIO NO ENCONTRADO
            # ------------------------------------------------

            if precio is None:

                frases_no_disponible = [
                    "producto no disponible",
                    "no disponible",
                    "agotado",
                    "sin stock"
                ]

                if any(
                    frase in texto_lower
                    for frase
                    in frases_no_disponible
                ):

                    print(
                        f"🔴 El Corte Inglés: "
                        f"{nombre} "
                        "no está disponible."
                    )

                    return None

                raise RuntimeError(
                    f"No se ha podido identificar "
                    f"el precio de {nombre} "
                    "en El Corte Inglés."
                )

            # ------------------------------------------------
            # STOCK
            # ------------------------------------------------

            stock = False
            unidades = 0

            if status_data:

                stock, unidades = (
                    _extraer_stock(
                        status_data
                    )
                )

                print("\n📦 STOCK")

                print(
                    f"   Disponible : "
                    f"{stock}"
                )

                print(
                    f"   Unidades   : "
                    f"{unidades}"
                )

            else:

                print(
                    "⚠️ No se capturó "
                    "STATUS FLOW."
                )

                print(
                    "   El precio sí ha sido "
                    "obtenido correctamente."
                )

            # ------------------------------------------------
            # RESULTADO
            # ------------------------------------------------

            print("\n" + "=" * 90)
            print("🎉 PRODUCTO IDENTIFICADO")
            print("=" * 90)

            print(
                f"🍷 Producto : {nombre}"
            )

            print(
                f"💶 Precio   : "
                f"{precio:.2f} €"
            )

            print(
                f"📦 Stock    : {stock}"
            )

            print(
                f"🔢 Unidades : {unidades}"
            )

            resultado = ProductoPrecio(

                tienda="El Corte Inglés",

                vendedor="El Corte Inglés",

                ean=ean,

                producto=nombre,

                marca=marca,

                formato=formato,

                precio=precio,

                stock=stock,

                estado="OK",

                fuente="PDP El Corte Inglés",

                url=url
            )

            return resultado

        except Exception as e:

            print(
                "\n❌ ERROR EN EL SCRAPER"
            )

            print(
                f"   {type(e).__name__}: {e}"
            )

            # MUY IMPORTANTE:
            # no devolvemos None.
            #
            # Si devolvemos None,
            # actualizar_todo.py interpreta
            # el fallo técnico como
            # "Producto no disponible".
            raise

        finally:

            try:

                browser.close()

            except Exception:

                pass