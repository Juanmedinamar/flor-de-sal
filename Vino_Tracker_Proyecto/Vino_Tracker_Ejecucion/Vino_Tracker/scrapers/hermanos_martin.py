import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import requests
from bs4 import BeautifulSoup
import re

from scrapers.common import ProductoPrecio


# ============================================================
# OBTENER PRECIO SUPERMERCADOS MAS
# ============================================================

def obtener_hermanos_martin(producto_config):

    if producto_config is None:

        raise ValueError(
            "No se ha recibido configuración de producto."
        )

    nombre = producto_config.nombre
    ean = producto_config.ean

    # --------------------------------------------------------
    # URL
    # --------------------------------------------------------

    url = producto_config.urls.get(
        "Hermanos Martin"
    )

    if not url:

        raise ValueError(
            f"No existe URL de Hermanos Martín "
            f"para {nombre}."
        )

    print("🌐 Abriendo Supermercados MAS...")
    print(f"📦 Producto: {nombre}")
    print(f"🔗 URL: {url}")

    # --------------------------------------------------------
    # HEADERS
    # --------------------------------------------------------

    headers = {

        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/151.0.0.0 Safari/537.36"
        ),

        "Accept-Language": "es-ES,es;q=0.9"
    }

    # --------------------------------------------------------
    # REQUEST
    # --------------------------------------------------------

    respuesta = requests.get(

        url,

        headers=headers,

        timeout=30
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

        raise ValueError(
            f"Supermercados MAS ha devuelto "
            f"HTTP {respuesta.status_code}"
        )

    html = respuesta.text

    # --------------------------------------------------------
    # BEAUTIFULSOUP
    # --------------------------------------------------------

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    texto = soup.get_text(
        " ",
        strip=True
    )

    # --------------------------------------------------------
    # COMPROBAR PRODUCTO
    # --------------------------------------------------------

    if nombre.lower() not in texto.lower():

        print(
            f"⚠️ El nombre exacto "
            f"'{nombre}' no aparece."
        )

        print(
            "🔎 Continuando con la búsqueda..."
        )

    else:

        print(
            f"✅ {nombre} encontrado"
        )

    # ========================================================
    # PRECIO
    # ========================================================

    precio = None

    # --------------------------------------------------------
    # NORMALIZAR HTML PARA LA BÚSQUEDA
    # --------------------------------------------------------

    html_normalizado = re.sub(
        r"\s+",
        " ",
        html
    )

    # ========================================================
    # MÉTODO 1
    #
    # Buscar el patrón:
    #
    #     7.89 instock
    #
    # que aparece en los datos internos de la página.
    # ========================================================

    patrones_precio = [

        r'(\d+[,.]\d{2})\s+instock',

        r'"price"\s*:\s*"?(\d+[,.]\d{2})',

        r'"price"\s*:\s*(\d+[,.]\d{2})',

        r'"sale_price"\s*:\s*"?(\d+[,.]\d{2})',

        r'"regular_price"\s*:\s*"?(\d+[,.]\d{2})',

    ]

    for patron in patrones_precio:

        coincidencia = re.search(

            patron,

            html_normalizado,

            re.IGNORECASE
        )

        if coincidencia:

            candidato = float(

                coincidencia.group(1)
                .replace(",", ".")
            )

            if candidato > 0:

                precio = candidato

                print(
                    "🎯 Precio de producto encontrado: "
                    f"{precio:.2f} €"
                )

                break

    # ========================================================
    # MÉTODO 2
    #
    # Buscar precio asociado a "Precio especial"
    # ========================================================

    if precio is None:

        patrones_especial = [

            r"precio\s+especial.{0,150}?(\d+[,.]\d{2})\s*€",

            r"precio\s+especial.{0,150}?(\d+[,.]\d{2})",

        ]

        for patron in patrones_especial:

            coincidencia = re.search(

                patron,

                texto,

                re.IGNORECASE
            )

            if coincidencia:

                candidato = float(

                    coincidencia.group(1)
                    .replace(",", ".")
                )

                if candidato > 0:

                    precio = candidato

                    print(
                        "🎯 Precio especial encontrado: "
                        f"{precio:.2f} €"
                    )

                    break

    # ========================================================
    # MÉTODO 3
    #
    # Buscar explícitamente:
    #
    #     precio € / Ud
    #
    # ========================================================

    if precio is None:

        patrones_unidad = [

            r"(\d+[,.]\d{2})\s*€\s*/\s*Ud",

            r"(\d+[,.]\d{2})\s*€\s*/\s*ud",

            r"(\d+[,.]\d{2})\s*€\s*por\s*unidad",

            r"(\d+[,.]\d{2})\s*€\s*unidad",

        ]

        for patron in patrones_unidad:

            coincidencia = re.search(

                patron,

                texto,

                re.IGNORECASE
            )

            if coincidencia:

                precio = float(

                    coincidencia.group(1)
                    .replace(",", ".")
                )

                print(
                    "🎯 Precio por unidad encontrado: "
                    f"{precio:.2f} €"
                )

                break

    # ========================================================
    # MÉTODO 4
    #
    # Último recurso:
    #
    # buscar precios en el texto y DESCARTAR €/L.
    # ========================================================

    if precio is None:

        coincidencias = re.finditer(

            r"(\d+[,.]\d{2})\s*€",

            texto
        )

        candidatos = []

        for coincidencia in coincidencias:

            candidato = float(

                coincidencia.group(1)
                .replace(",", ".")
            )

            contexto = texto[
                max(
                    0,
                    coincidencia.start() - 50
                ):
                min(
                    len(texto),
                    coincidencia.end() + 80
                )
            ].lower()

            # No aceptar precios por litro

            if (
                "litro" in contexto
                or "€/l" in contexto
                or "/ l" in contexto
            ):

                continue

            if candidato > 0:

                candidatos.append(
                    candidato
                )

        if candidatos:

            precio = candidatos[0]

            print(
                "💰 Precio encontrado mediante "
                f"fallback: {precio:.2f} €"
            )

    # ========================================================
    # VALIDACIÓN
    # ========================================================

    if precio is None:

        raise ValueError(
            f"No se ha encontrado el precio "
            f"de {nombre} en Supermercados MAS."
        )

    if precio <= 0:

        raise ValueError(
            f"Precio inválido obtenido: {precio}"
        )

    # --------------------------------------------------------
    # MOSTRAR PRECIO
    # --------------------------------------------------------

    print(
        f"💰 Precio encontrado: "
        f"{precio:.2f} €"
    )

    # ========================================================
    # STOCK
    # ========================================================

    texto_normalizado = texto.lower()

    if (
        "sin existencias" in texto_normalizado
        or "agotado" in texto_normalizado
        or "no disponible" in texto_normalizado
    ):

        stock = False

        print(
            "📦 Stock: Sin existencias"
        )

    else:

        stock = True

        print(
            "📦 Stock: Disponible"
        )

    # ========================================================
    # RESULTADO
    # ========================================================

    return ProductoPrecio(

        tienda="Hermanos Martin",

        vendedor="Supermercados MAS",

        ean=ean,

        producto=nombre,

        marca=producto_config.marca,

        formato=producto_config.formato,

        precio=precio,

        stock=stock,

        estado="OK",

        fuente="web",

        url=url
    )

