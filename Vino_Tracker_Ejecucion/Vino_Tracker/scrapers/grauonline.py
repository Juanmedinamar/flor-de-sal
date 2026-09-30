import re
import requests
from bs4 import BeautifulSoup

from .common import ProductoPrecio


URL_BASE = "https://www.grauonline.es"


def obtener_grauonline(producto_config):
    """
    Obtiene el precio y stock de un producto desde Grau Online.

    Devuelve:
        ProductoPrecio si la consulta es correcta.
        None si se produce un error o no se puede validar el producto.
    """

    nombre = producto_config.nombre
    marca = producto_config.marca
    formato = producto_config.formato
    ean = producto_config.ean

    # ---------------------------------------------------------
    # URL DEL PRODUCTO
    # ---------------------------------------------------------
    url = producto_config.urls.get("Grau Online")

    if not url:
        print(f"❌ Grau Online: no hay URL configurada para {nombre}")
        return None

    print("=" * 80)
    print("🍷 GRAU ONLINE")
    print("=" * 80)
    print(f"🌐 URL: {url}")
    print(f"📦 Producto: {nombre}")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/151.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,image/avif,image/webp,"
            "*/*;q=0.8"
        ),
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Referer": "https://www.google.com/",
    }

    try:
        # -----------------------------------------------------
        # PETICIÓN HTTP
        # -----------------------------------------------------
        response = requests.get(
            url,
            headers=headers,
            timeout=30
        )

        print(f"📡 HTTP: {response.status_code}")

        if response.status_code != 200:
            print(
                f"❌ Grau Online: HTTP {response.status_code}"
            )
            return None

        html = response.text

        print(f"📄 HTML recibido: {len(html):,} caracteres")

        soup = BeautifulSoup(html, "html.parser")

        texto = soup.get_text(" ", strip=True)

        # -----------------------------------------------------
        # COMPROBAR QUE EL PRODUCTO EXISTE
        # -----------------------------------------------------
        nombre_busqueda = nombre.lower().strip()

        if nombre_busqueda not in texto.lower():
            print(
                f"❌ Grau Online: no se ha encontrado "
                f"'{nombre}' en la página"
            )
            return None

        print(f"✅ Producto encontrado: {nombre}")

        # -----------------------------------------------------
        # PRECIO
        # -----------------------------------------------------
        precio = None

        # Primero intentamos localizar JSON-LD,
        # que suele ser la fuente más fiable.
        scripts = soup.find_all(
            "script",
            type="application/ld+json"
        )

        for script in scripts:
            contenido = script.string

            if not contenido:
                continue

            # Buscamos precios con formato:
            # "price": "8.46"
            # "price": 8.46
            coincidencias = re.findall(
                r'"price"\s*:\s*"?(\d+[.,]\d{2})"?',
                contenido,
                re.IGNORECASE
            )

            if coincidencias:
                try:
                    precio = float(
                        coincidencias[0].replace(",", ".")
                    )
                    break
                except ValueError:
                    pass

        # -----------------------------------------------------
        # SEGUNDO MÉTODO: TEXTO DE LA PÁGINA
        # -----------------------------------------------------
        if precio is None:

            # Buscamos precios con formato español:
            # 8,46 €
            # 8.46 €
            patrones = [
                r'(\d+[.,]\d{2})\s*€',
                r'(\d+[.,]\d{2})\s*EUR',
            ]

            candidatos = []

            for patron in patrones:
                encontrados = re.findall(
                    patron,
                    texto,
                    re.IGNORECASE
                )

                for valor in encontrados:
                    try:
                        candidatos.append(
                            float(valor.replace(",", "."))
                        )
                    except ValueError:
                        continue

            # Eliminamos precios absurdos para este contexto
            candidatos = [
                p for p in candidatos
                if 0.50 <= p <= 1000
            ]

            if candidatos:
                precio = candidatos[0]

        if precio is None:
            print("❌ Grau Online: no se ha podido obtener el precio")
            return None

        print(f"💰 Precio encontrado: {precio:.2f} €")

        # -----------------------------------------------------
        # FORMATO
        # -----------------------------------------------------
        formato_encontrado = None

        patrones_formato = [
            r'0[,.]75\s*L',
            r'75\s*cl',
            r'0[,.]750\s*L',
        ]

        for patron in patrones_formato:
            match = re.search(
                patron,
                texto,
                re.IGNORECASE
            )

            if match:
                formato_encontrado = match.group(0)
                break

        if formato_encontrado:
            print(
                f"📏 Formato encontrado: "
                f"{formato_encontrado}"
            )
        else:
            print("⚠️ No se ha podido confirmar el formato")

        # -----------------------------------------------------
        # STOCK
        # -----------------------------------------------------
        texto_lower = texto.lower()

        expresiones_sin_stock = [
            "producto no disponible",
            "no disponible",
            "sin stock",
            "agotado",
            "fuera de stock",
            "descatalogado",
        ]

        sin_stock = any(
            expresion in texto_lower
            for expresion in expresiones_sin_stock
        )

        # Si aparece "Añadir al carrito", consideramos
        # que está disponible.
        tiene_carrito = (
            "añadir al carrito" in texto_lower
            or "añadir en carrito" in texto_lower
        )

        if sin_stock:
            stock = False
            print("📦 Stock: SIN STOCK")

        elif tiene_carrito:
            stock = True
            print("📦 Stock: DISPONIBLE")

        else:
            # Si no encontramos ninguna señal clara,
            # no damos por disponible el producto.
            stock = False
            print(
                "⚠️ Stock: no se ha podido confirmar "
                "disponibilidad"
            )

        # -----------------------------------------------------
        # VENDEDOR
        # -----------------------------------------------------
        vendedor = "Grau Online"

        # -----------------------------------------------------
        # RESULTADO
        # -----------------------------------------------------
        resultado = ProductoPrecio(
            tienda="Grau Online",
            vendedor=vendedor,
            ean=ean,
            producto=nombre,
            marca=marca,
            formato=formato,
            precio=precio,
            stock=stock,
            estado="OK",
            fuente="Grau Online web",
            url=url
        )

        print()
        print("✅ RESULTADO GRAU ONLINE")
        print(resultado)
        print("=" * 80)

        return resultado

    except requests.RequestException as e:

        print(
            f"❌ Error de conexión con Grau Online: {e}"
        )
        return None

    except Exception as e:

        print(
            f"❌ Error inesperado en Grau Online: {e}"
        )
        return None
