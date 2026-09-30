import re
import requests
from bs4 import BeautifulSoup

from scrapers.common import ProductoPrecio


def obtener_vinoseleccion(producto_config):

    url = producto_config.urls.get("Vinoselección")

    if not url:
        print("⚠️ Vinoselección: no hay URL configurada")
        return None

    try:
        print(f"🌐 Vinoselección: {url}")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "es-ES,es;q=0.9",
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=20
        )

        print(f"📡 HTTP: {response.status_code}")

        if response.status_code != 200:
            raise RuntimeError(
                f"HTTP {response.status_code} "
                f"al consultar Vinoselección"
            )

        soup = BeautifulSoup(response.text, "html.parser")

        texto = soup.get_text(" ", strip=True)

        # --------------------------------------------------
        # COMPROBAR PRODUCTO
        # --------------------------------------------------

        nombre = producto_config.nombre.lower()

        if nombre not in texto.lower():
            print(
                f"⚠️ No se encuentra '{producto_config.nombre}' "
                "en la página"
            )
            return None

        # --------------------------------------------------
        # PRECIO
        # --------------------------------------------------

        precio = None

        # Intentamos primero JSON-LD
        for script in soup.find_all(
            "script",
            type="application/ld+json"
        ):

            contenido = script.get_text(strip=True)

            coincidencias = re.findall(
                r'"price"\s*:\s*"?(?:€\s*)?(\d+[.,]\d+)',
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

        # --------------------------------------------------
        # PRECIO COMO FALLBACK
        # --------------------------------------------------

        if precio is None:

            patrones = [
                r'(\d{1,3}[.,]\d{2})\s*€',
                r'(\d{1,3}[.,]\d{2})\s*euros',
            ]

            for patron in patrones:

                encontrados = re.findall(
                    patron,
                    texto,
                    re.IGNORECASE
                )

                for valor in encontrados:

                    try:
                        candidato = float(
                            valor.replace(",", ".")
                        )

                        if 1 <= candidato <= 10000:
                            precio = candidato
                            break

                    except ValueError:
                            continue

                

        if precio is None:

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
                    "🔴 Vinoselección: "
                    "producto no disponible"
                )

                return None

            raise RuntimeError(
                "No se ha podido localizar el precio "
                "en la página de Vinoselección"
            )

        # --------------------------------------------------
        # FORMATO
        # --------------------------------------------------

        formato = producto_config.formato

        coincidencia = re.search(
            r'Botella\s*(\d+(?:[.,]\d+)?)\s*cl',
            texto,
            re.IGNORECASE
        )

        if coincidencia:
            formato = (
                coincidencia.group(1).replace(",", ".")
                + " cl"
            )

        # --------------------------------------------------
        # STOCK
        # --------------------------------------------------

        texto_lower = texto.lower()

        sin_stock = any(
            frase in texto_lower
            for frase in [
                "producto no disponible",
                "no disponible",
                "agotado",
                "sin stock"
            ]
        )

        stock = not sin_stock

        # --------------------------------------------------
        # RESULTADO
        # --------------------------------------------------

        resultado = ProductoPrecio(
            tienda="Vinoselección",
            vendedor="Vinoselección",
            ean=producto_config.ean,
            producto=producto_config.nombre,
            marca=producto_config.marca,
            formato=formato,
            precio=precio,
            stock=stock,
            estado="OK",
            fuente="Vinoselección web",
            url=url
        )

        print(
            f"✅ Vinoselección: "
            f"{producto_config.nombre} → "
            f"{precio:.2f} €"
        )

        print(f"📦 Formato: {formato}")

        print(
            f"📦 Stock: "
            f"{'Disponible' if stock else 'Sin stock'}"
        )

        return resultado

    except Exception as e:

        print(
            f"❌ Error en Vinoselección: {e}"
        )

        raise