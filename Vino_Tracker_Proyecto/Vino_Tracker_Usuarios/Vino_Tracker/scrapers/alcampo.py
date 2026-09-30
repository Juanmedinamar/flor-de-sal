import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import requests
from bs4 import BeautifulSoup
import re

from playwright.sync_api import sync_playwright

from scrapers.common import ProductoPrecio


def extraer_precio(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    texto = soup.get_text(
        " ",
        strip=True
    )

    precios = re.findall(
        r"\d+[,.]\d{2}\s*€",
        texto
    )

    precios_numericos = []

    for precio in precios:

        valor = (
            precio
            .replace("€", "")
            .strip()
            .replace(",", ".")
        )

        try:

            valor = float(valor)

            if valor > 0:

                precios_numericos.append(
                    valor
                )

        except ValueError:

            continue

    if not precios_numericos:

        return None

    return precios_numericos[0]


def obtener_con_requests(url):

    headers = {

        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/151.0.0.0 Safari/537.36"
        )
    }

    respuesta = requests.get(
        url,
        headers=headers,
        timeout=20
    )

    print(
        "Código HTTP:",
        respuesta.status_code
    )

    print(
        "Tamaño HTML:",
        len(respuesta.text)
    )

    if respuesta.status_code != 200:

        return None

    if not respuesta.text:

        return None

    return extraer_precio(
        respuesta.text
    )


def obtener_con_playwright(url):

    print()
    print(
        "⚠️ Requests no ha conseguido "
        "el contenido."
    )

    print(
        "🌐 Intentando con Playwright..."
    )

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36"
            )
        )

        try:

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            page.wait_for_timeout(
                5000
            )

            html = page.content()

            print(
                "HTML obtenido con Playwright:",
                len(html)
            )

            return extraer_precio(html)

        finally:

            browser.close()


def obtener_alcampo(producto_config):

    if producto_config is None:

        raise ValueError(
            "No se ha recibido configuración "
            "de producto."
        )

    nombre = producto_config.nombre

    url = producto_config.urls.get(
        "Alcampo"
    )

    if not url:

        raise ValueError(
            f"No existe URL de Alcampo "
            f"para {nombre}."
        )

    print(
        "🌐 Abriendo Alcampo..."
    )

    print(
        f"📦 Producto: {nombre}"
    )

    # --------------------------------------------------------
    # REQUESTS
    # --------------------------------------------------------

    precio = obtener_con_requests(
        url
    )

    # --------------------------------------------------------
    # PLAYWRIGHT
    # --------------------------------------------------------

    if precio is None:

        precio = obtener_con_playwright(
            url
        )

    # --------------------------------------------------------
    # ERROR
    # --------------------------------------------------------

    if precio is None:

        raise ValueError(
            f"No se ha encontrado ningún precio "
            f"para {nombre}."
        )

    # --------------------------------------------------------
    # PRODUCTO
    # --------------------------------------------------------

    return ProductoPrecio(

        tienda="Alcampo",

        vendedor="Alcampo",

        ean=producto_config.ean,

        producto=nombre,

        marca=producto_config.marca,

        formato=producto_config.formato,

        precio=precio,

        stock=True,

        estado="OK",

        fuente="web",

        url=url
    )