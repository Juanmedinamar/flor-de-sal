import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

from scrapers.common import ProductoPrecio


def obtener_bodeboca(producto_config):

    if producto_config is None:

        raise ValueError(
            "No se ha recibido configuración "
            "de producto."
        )

    nombre = producto_config.nombre
    ean = producto_config.ean

    url = producto_config.urls.get(
        "Bodeboca"
    )

    if not url:

        raise ValueError(
            f"No existe URL de Bodeboca "
            f"para {nombre}."
        )

    print(
        "🌐 Abriendo Bodeboca..."
    )

    print(
        f"📦 Producto: {nombre}"
    )

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1400,
                "height": 900
            },
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="es-ES",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )

        try:

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            print(
                "⏳ Esperando a que cargue "
                "la página..."
            )

            for intento in range(6):

                titulo = page.title()

                print(
                    f"Intento {intento + 1}/6 - "
                    f"Título: {titulo}"
                )

                if "Just a moment" not in titulo:

                    break

                page.wait_for_timeout(
                    5000
                )

            titulo = page.title()

            # ------------------------------------------------
            # CLOUDFLARE
            # ------------------------------------------------

            if "Just a moment" in titulo:

                print(
                    "⚠️ Bodeboca está bloqueando "
                    "el acceso mediante Cloudflare."
                )

                raise RuntimeError(
                    "Bodeboca bloquea el acceso "
                    "mediante Cloudflare."
                )

            # ------------------------------------------------
            # TEXTO
            # ------------------------------------------------

            texto = page.locator(
                "body"
            ).inner_text()

            posicion = texto.lower().find(
                nombre.lower()
            )

            if posicion == -1:

                print(
                    f"⚠️ No aparece {nombre} "
                    "en la página de Bodeboca."
                )

                return None

            # ------------------------------------------------
            # ZONA DEL PRODUCTO
            # ------------------------------------------------

            inicio = max(
                0,
                posicion - 500
            )

            fin = min(
                len(texto),
                posicion + 1000
            )

            zona_producto = texto[
                inicio:fin
            ]

            print(
                zona_producto
            )

            # ------------------------------------------------
            # PRECIOS
            # ------------------------------------------------

            precios = re.findall(
                r"\d+[,.]\d{2}\s*€",
                zona_producto
            )

            precios_numericos = []

            for precio_texto in precios:

                valor = (
                    precio_texto
                    .replace("€", "")
                    .strip()
                    .replace(",", ".")
                )

                try:

                    valor = float(
                        valor
                    )

                    if valor > 0:

                        precios_numericos.append(
                            valor
                        )

                except ValueError:

                    continue

            if not precios_numericos:

                texto_lower = texto.lower()

                frases_no_disponible = [
                    "producto no disponible",
                    "no disponible",
                    "agotado",
                    "sin stock"
                ]

                if any(
                    frase in texto_lower
                    for frase in frases_no_disponible
                ):

                    print(
                        f"🔴 Bodeboca: "
                        f"{nombre} no está disponible."
                    )

                    return None

                raise RuntimeError(
                    f"No se ha encontrado el precio "
                    f"de {nombre} en Bodeboca."
                )

            precio = precios_numericos[0]

        except Exception:

            raise

        finally:

            browser.close()

    # --------------------------------------------------------
    # PRODUCTO
    # --------------------------------------------------------

    return ProductoPrecio(

        tienda="Bodeboca",

        vendedor="Bodeboca",

        ean=ean,

        producto=nombre,

        marca=producto_config.marca,

        formato=producto_config.formato,

        precio=precio,

        stock=True,

        estado="OK",

        fuente="Bodeboca web",

        url=url
    )