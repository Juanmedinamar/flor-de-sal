import requests
from bs4 import BeautifulSoup

from scrapers.common import ProductoPrecio


URL_BODEGA = "https://www.vinissimus.com/es/bodega/williams-humbert/"


def convertir_precio(texto):
    if not texto:
        return None

    texto = texto.replace("€", "").strip()

    # Formato español: 10,35 / 1.234,56
    texto = texto.replace(".", "").replace(",", ".")

    try:
        return float(texto)
    except ValueError:
        return None


def obtener_vinissimus(producto_config):

    print("=" * 80)
    print("🍷 VINISSIMUS")
    print("=" * 80)

    nombre = producto_config.nombre
    ean = producto_config.ean
    formato = producto_config.formato

    print(f"📦 Producto: {nombre}")
    print(f"🏷️ EAN: {ean}")
    print(f"🔗 URL: {URL_BODEGA}")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/151.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "es-ES,es;q=0.9",
        "Referer": "https://www.vinissimus.com/es/",
    }

    try:

        # ==========================================================
        # DESCARGAR PÁGINA
        # ==========================================================

        print("\n🌐 Consultando Vinissimus...")

        respuesta = requests.get(
            URL_BODEGA,
            headers=headers,
            timeout=30
        )

        print(f"📡 HTTP: {respuesta.status_code}")
        print(f"📍 URL: {respuesta.url}")
        print(f"📏 HTML: {len(respuesta.text)} caracteres")

        respuesta.raise_for_status()

        soup = BeautifulSoup(
            respuesta.text,
            "html.parser"
        )

        print("\n========== DIAGNÓSTICO VINISSIMUS ==========")
        print("NOMBRE CONFIGURADO:", repr(nombre))

        todos_h2 = soup.find_all("h2")
        print("TOTAL H2:", len(todos_h2))

        for i, elemento in enumerate(todos_h2):
            print()
            print(f"----- H2 #{i} -----")
            print("TEXTO:", repr(elemento.get_text(" ", strip=True)))
            print("HTML:", str(elemento)[:1000])

        print()
        print("========== BÚSQUEDA GLOBAL CANASTA ==========")

        texto_completo = soup.get_text(" ", strip=True)

        print("¿CANASTA EN HTML?:", "canasta" in r.text.lower())
        print("¿CANASTA EN TEXTO?:", "canasta" in texto_completo.lower())
        print("¿CREAM EN HTML?:", "cream" in r.text.lower())
        print("¿CREAM EN TEXTO?:", "cream" in texto_completo.lower())

        pos = r.text.lower().find("canasta")

        if pos != -1:
            print()
            print("🎯 CANASTA ENCONTRADA EN HTML")
            print("POSICIÓN:", pos)
            print("CONTEXTO:")
            print(r.text[max(0, pos-1000):pos+3000])

        print("============================================")

        # ==========================================================
        # BUSCAR PRODUCTO
        # ==========================================================

        print("\n🔎 Buscando producto...")

        producto_encontrado = None

        # ==========================================================
        # BUSCAR EXACTAMENTE EL H2 DE CANASTA CREAM
        # ==========================================================

        h2 = soup.find(
            "h2",
            class_="title",
            string=lambda x: x and "Canasta Cream" in x
        )

        if h2:

            producto_encontrado = h2

            print("✅ Producto localizado mediante H2:")
            print(h2.get_text(" ", strip=True))

        # ==========================================================
        # SEGUNDO INTENTO: CUALQUIER H2 QUE CONTENGA CANASTA + CREAM
        # ==========================================================

        if producto_encontrado is None:

            for h2 in soup.find_all("h2"):

                texto = h2.get_text(
                    " ",
                    strip=True
                ).lower()

                if "canasta" in texto and "cream" in texto:

                    producto_encontrado = h2

                    print("✅ Producto localizado mediante búsqueda flexible:")
                    print(h2.get_text(" ", strip=True))

                    break

        # ==========================================================
        # TERCER INTENTO: BLOQUE COMPLETO DEL PRODUCTO
        # ==========================================================

        if producto_encontrado is None:

            for bloque in soup.select("div.product-list-item"):

                texto = bloque.get_text(
                    " ",
                    strip=True
                ).lower()

                if "canasta" in texto and "cream" in texto:

                    producto_encontrado = bloque

                    print("✅ Producto localizado mediante bloque:")
                    print(bloque.get_text(" ", strip=True))

                    break

        # ==========================================================
        # NO ENCONTRADO
        # ==========================================================

        if producto_encontrado is None:

            raise ValueError(
                f"❌ No se ha encontrado '{nombre}' en Vinissimus."
            )

        # ==========================================================
        # OBTENER BLOQUE DEL PRODUCTO
        # ==========================================================

        if producto_encontrado.name == "h2":

            bloque = producto_encontrado.find_parent(
                class_="product-list-item"
            )

        else:

            bloque = producto_encontrado

        if bloque is None:

            raise ValueError(
                "❌ No se ha encontrado el bloque del producto."
            )

        texto_bloque = bloque.get_text(
            " ",
            strip=True
        )

        print("\n📦 BLOQUE DEL PRODUCTO:")
        print(texto_bloque)

        # ==========================================================
        # STOCK
        # ==========================================================

        texto_normalizado = texto_bloque.lower()

        frases_sin_stock = [
            "sin stock",
            "agotado",
            "no disponible",
            "producto agotado",
            "actualmente no disponible",
        ]

        if any(
            frase in texto_normalizado
            for frase in frases_sin_stock
        ):

            print("❌ Producto sin stock")

            return ProductoPrecio(
                tienda="Vinissimus",
                vendedor="Vinissimus",
                ean=ean,
                producto=nombre,
                marca=producto_config.marca,
                formato=formato,
                precio=None,
                stock=False,
                estado="NO_DISPONIBLE",
                fuente="Vinissimus web",
                url=URL_BODEGA,
            )

        stock = "en stock" in texto_normalizado

        print(f"📦 Stock: {stock}")

        # ==========================================================
        # PRECIO
        # ==========================================================

        precio_elemento = bloque.find(
            "p",
            class_="price"
        )

        if precio_elemento is None:

            raise ValueError(
                "❌ No se ha encontrado el precio del producto."
            )

        texto_precio = precio_elemento.get_text(
            " ",
            strip=True
        )

        precio = convertir_precio(
            texto_precio
        )

        if precio is None:

            raise ValueError(
                f"❌ No se ha podido convertir el precio: "
                f"{texto_precio}"
            )

        print(f"💰 Precio encontrado: {precio:.2f} €")

        # ==========================================================
        # RESULTADO
        # ==========================================================

        resultado = ProductoPrecio(
            tienda="Vinissimus",
            vendedor="Vinissimus",
            ean=ean,
            producto=nombre,
            marca=producto_config.marca,
            formato=formato,
            precio=precio,
            stock=stock,
            estado="OK",
            fuente="Vinissimus web",
            url=URL_BODEGA,
        )

        print("\n" + "=" * 80)
        print("✅ VINISSIMUS OK")
        print("=" * 80)
        print(f"📦 Producto: {resultado.producto}")
        print(f"💰 Precio: {resultado.precio:.2f} €")
        print(f"📦 Stock: {resultado.stock}")
        print(f"🍾 Formato: {resultado.formato}")
        print(f"🏷️ EAN: {resultado.ean}")

        return resultado

    except Exception as e:

        print("\n" + "=" * 80)
        print("❌ ERROR EN VINISSIMUS")
        print("=" * 80)

        print(type(e).__name__, ":", e)

        raise


if __name__ == "__main__":

    from productos import obtener_producto

    producto = obtener_producto("Canasta Cream")

    resultado = obtener_vinissimus(producto)

    print("\nRESULTADO FINAL:")
    print(resultado)