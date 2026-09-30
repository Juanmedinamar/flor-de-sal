import re
import unicodedata

from playwright.sync_api import sync_playwright

from scrapers.common import ProductoPrecio

from urllib.parse import quote

# ==============================================================
# UTILIDADES
# ==============================================================

def normalizar_texto(texto):
    """
    Elimina tildes, convierte a minúsculas y elimina espacios
    sobrantes para facilitar las comparaciones.
    """
    if not texto:
        return ""

    texto = unicodedata.normalize("NFD", texto)

    texto = "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )

    return texto.lower().strip()


def convertir_precio(valor):
    """
    Convierte precios españoles:

        4,95       -> 4.95
        1.234,95   -> 1234.95
        4.95       -> 4.95
    """

    if not valor:
        return None

    valor = valor.strip()

    try:
        # Formato español: 1.234,95
        if "," in valor:
            valor = valor.replace(".", "")
            valor = valor.replace(",", ".")

        return float(valor)

    except ValueError:
        return None


# ==============================================================
# SCRAPER CARREFOUR
# ==============================================================

def obtener_carrefour(producto_config):

    nombre_producto = producto_config.nombre
    ean_esperado = producto_config.ean

    # ==========================================================
    # OBTENER URL DIRECTA DE CARREFOUR
    # ==========================================================

    url_carrefour = producto_config.urls.get("Carrefour")

    print()
    print("=" * 80)
    print("🌐 CARREFOUR")
    print("=" * 80)
    print(f"📦 Producto: {nombre_producto}")
    print(f"🏷️ EAN: {ean_esperado}")

    # ==========================================================
    # COMPROBAR URL
    # ==========================================================

    if not url_carrefour:

        raise ValueError(
            f"❌ No existe una URL directa de Carrefour "
            f"para {nombre_producto}."
        )

    print()
    print("🔗 URL directa Carrefour:")
    print(url_carrefour)

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=False
        )

        page = browser.new_page(
            viewport={
                "width": 1400,
                "height": 900
            }
        )

        try:

            # ==================================================
            # ABRIR FICHA DIRECTAMENTE
            # ==================================================

            print()
            print("🌐 Abriendo ficha directa Carrefour...")

            respuesta = page.goto(
                url_carrefour,
                wait_until="domcontentloaded",
                timeout=60000
            )

            page.wait_for_timeout(5000)

            print("✅ Página Carrefour cargada")

            # ==================================================
            # INFORMACIÓN DE LA RESPUESTA
            # ==================================================

            if respuesta:

                print()
                print("📡 Estado HTTP:")
                print(respuesta.status)

            print()
            print("📍 URL final:")
            print(page.url)

            print()
            print("📄 Título:")
            print(page.title())

            # ==================================================
            # 🍪 COOKIES
            # ==================================================

            print()
            print("🍪 Comprobando cookies...")

            try:

                botones_cookies = [
                    "Aceptar todas",
                    "Aceptar",
                    "Aceptar cookies",
                ]

                cookies_aceptadas = False

                for texto_boton in botones_cookies:

                    try:

                        boton = page.get_by_role(
                            "button",
                            name=texto_boton,
                            exact=True
                        )

                        if (
                            boton.count() > 0
                            and boton.first.is_visible()
                        ):

                            print(
                                f"🍪 Pulsando: {texto_boton}"
                            )

                            boton.first.click(
                                timeout=5000
                            )

                            page.wait_for_timeout(1500)

                            cookies_aceptadas = True

                            print(
                                "✅ Cookies aceptadas"
                            )

                            break

                    except Exception:
                        pass

                if not cookies_aceptadas:

                    print(
                        "ℹ️ No se ha encontrado "
                        "botón de cookies"
                    )

            except Exception as e:

                print(
                    "⚠️ Error gestionando cookies:",
                    e
                )

            # ==================================================
            # LEER TEXTO DE LA PÁGINA
            # ==================================================

            print()
            print("📄 Leyendo ficha del producto...")

            texto_producto = (
                page.locator("body").inner_text()
            )

            print()
            print("=" * 80)
            print("📄 FICHA CARREFOUR")
            print("=" * 80)

            print(
                texto_producto[:12000]
            )

            print(
                "=" * 80
            )

            # ==================================================
            # NORMALIZAR TEXTO
            # ==================================================

            texto_normalizado = normalizar_texto(
                texto_producto
            )

            nombre_normalizado = normalizar_texto(
                nombre_producto
            )

            # ==================================================
            # VALIDAR PRODUCTO
            # ==================================================

            print()
            print("=" * 80)
            print("🔎 VALIDACIÓN DEL PRODUCTO")
            print("=" * 80)

            producto_confirmado = (
                nombre_normalizado
                in texto_normalizado
            )

            print(
                "¿Aparece el nombre?:",
                producto_confirmado
            )

            # --------------------------------------------------
            # Si el nombre completo no aparece exactamente,
            # comprobamos palabras importantes del producto.
            # --------------------------------------------------

            if not producto_confirmado:

                palabras_producto = [
                    palabra
                    for palabra
                    in nombre_normalizado.split()
                    if len(palabra) >= 4
                ]

                palabras_encontradas = [
                    palabra
                    for palabra
                    in palabras_producto
                    if palabra in texto_normalizado
                ]

                print(
                    "Palabras encontradas:",
                    palabras_encontradas
                )

                # Necesitamos al menos la mitad de las
                # palabras relevantes para considerar válida
                # la ficha.

                minimo_palabras = max(
                    1,
                    len(palabras_producto) // 2
                )

                if (
                    len(palabras_encontradas)
                    < minimo_palabras
                ):

                    raise ValueError(
                        f"❌ La ficha de Carrefour "
                        f"no parece corresponder a "
                        f"{nombre_producto}."
                    )

            print()
            print(
                f"✅ Producto confirmado: "
                f"{nombre_producto}"
            )

            # ==================================================
            # VALIDAR EAN
            # ==================================================

            print()
            print("🏷️ Comprobando EAN...")

            if (
                ean_esperado
                and ean_esperado != "PENDIENTE"
            ):

                if ean_esperado in texto_producto:

                    print(
                        f"✅ EAN confirmado: "
                        f"{ean_esperado}"
                    )

                else:

                    print(
                        "ℹ️ EAN no aparece "
                        "directamente en el texto."
                    )

            else:

                print(
                    "ℹ️ EAN pendiente."
                )

            # ==================================================
            # VENDEDOR
            # ==================================================

            print()
            print("🏪 Detectando vendedor...")

            vendedor = "Carrefour"

            marcador = "Vendido por"

            posicion = texto_producto.find(
                marcador
            )

            if posicion != -1:

                bloque = texto_producto[
                    posicion:
                    posicion + 500
                ]

                lineas = [
                    linea.strip()
                    for linea
                    in bloque.splitlines()
                    if linea.strip()
                ]

                for i, linea in enumerate(
                    lineas
                ):

                    if (
                        linea.lower()
                        == "vendido por"
                    ):

                        if (
                            i + 1
                            < len(lineas)
                        ):

                            vendedor = (
                                lineas[i + 1]
                            )

                        break

            print(
                "🏪 Vendedor:",
                vendedor
            )

            # ==================================================
            # EXTRAER PRECIOS
            # ==================================================

            print()
            print("💰 Buscando precio...")

            precios = re.findall(
                r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})\s*€",
                texto_producto
            )

            print(
                "💰 Valores encontrados:",
                precios
            )

            if not precios:

                raise ValueError(
                    "❌ No se ha encontrado "
                    "el precio en Carrefour."
                )

            # ==================================================
            # CONVERTIR PRECIOS
            # ==================================================

            precios_float = []

            for valor in precios:

                precio = convertir_precio(
                    valor
                )

                if precio is not None:

                    if 0 < precio < 10000:

                        precios_float.append(
                            precio
                        )

            print(
                "💰 Precios convertidos:",
                precios_float
            )

            if not precios_float:

                raise ValueError(
                    "❌ No se han podido "
                    "convertir los precios."
                )

            # ==================================================
            # ELEGIR PRECIO
            # ==================================================

            precio = precios_float[0]

            print()
            print(
                "💰 PRECIO DETECTADO:",
                precio,
                "€"
            )

            # ==================================================
            # RESULTADO
            # ==================================================

            resultado = ProductoPrecio(
                tienda="Carrefour",
                vendedor=vendedor,
                ean=ean_esperado,
                producto=nombre_producto,
                marca=producto_config.marca,
                formato=producto_config.formato,
                precio=precio,
                stock=True,
                estado="OK",
                fuente="Carrefour web",
                url=url_carrefour
            )

            # ==================================================
            # RESULTADO FINAL
            # ==================================================

            print()
            print("=" * 80)
            print("✅ CARREFOUR COMPLETADO")
            print("=" * 80)

            print(
                resultado
            )

            return resultado

        except Exception as e:

            print()
            print("=" * 80)
            print("❌ ERROR EN CARREFOUR")
            print("=" * 80)

            print(
                type(e).__name__,
                ":",
                e
            )

            raise

        finally:

            browser.close()
            
# ==============================================================
# PRUEBA DIRECTA
# ==============================================================

if __name__ == "__main__":

    from productos import obtener_producto

    producto = obtener_producto(
        "Gran Duque de Alba"
    )

    resultado = obtener_carrefour(
        producto
    )

    print()
    print("=" * 80)
    print("🍷 RESULTADO FINAL")
    print("=" * 80)
    print(resultado)
