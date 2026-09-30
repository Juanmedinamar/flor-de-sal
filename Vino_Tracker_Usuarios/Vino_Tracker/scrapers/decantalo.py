import re
import unicodedata

from playwright.sync_api import sync_playwright

from scrapers.common import ProductoPrecio


# ==============================================================
# UTILIDADES
# ==============================================================

def normalizar_texto(texto):
    """
    Elimina tildes y convierte el texto a minúsculas.
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

        8,25      -> 8.25
        1.234,95  -> 1234.95
    """

    if not valor:
        return None

    valor = valor.strip()

    try:
        if "," in valor:
            valor = valor.replace(".", "")
            valor = valor.replace(",", ".")

        return float(valor)

    except ValueError:
        return None


# ==============================================================
# SCRAPER DECÁNTALO
# ==============================================================

def obtener_decantalo(producto_config):

    nombre_producto = producto_config.nombre
    ean_esperado = producto_config.ean

    url_decantalo = producto_config.urls.get("Decántalo")

    print()
    print("=" * 80)
    print("🍷 DECÁNTALO")
    print("=" * 80)
    print(f"📦 Producto: {nombre_producto}")
    print(f"🏷️ EAN: {ean_esperado}")
    print(f"🔗 URL: {url_decantalo}")

    # ----------------------------------------------------------
    # COMPROBAR URL
    # ----------------------------------------------------------

    if not url_decantalo:
        raise ValueError(
            f"❌ No existe URL de Decántalo para "
            f"{nombre_producto}."
        )

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
            # ABRIR PRODUCTO
            # ==================================================

            print()
            print("🌐 Abriendo Decántalo...")

            respuesta = page.goto(
                url_decantalo,
                wait_until="domcontentloaded",
                timeout=60000
            )

            page.wait_for_timeout(5000)

            print("✅ Decántalo cargado")

            if respuesta:
                print(
                    "📡 HTTP:",
                    respuesta.status
                )

            print(
                "📍 URL final:",
                page.url
            )

            print(
                "📄 Título:",
                page.title()
            )

            # ==================================================
            # LEER TEXTO
            # ==================================================

            print()
            print("📄 Leyendo contenido...")

            texto_producto = page.locator(
                "body"
            ).inner_text()

            print()
            print(
                "📏 Caracteres encontrados:",
                len(texto_producto)
            )

            print()
            print(
                "========== CONTENIDO PRODUCTO =========="
            )

            print(
                texto_producto[:12000]
            )

            print(
                "========================================"
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
            print(
                "🔎 Comprobando producto..."
            )

            if nombre_normalizado not in texto_normalizado:

                # Intentamos una comprobación más flexible
                palabras = [
                    palabra
                    for palabra in nombre_normalizado.split()
                    if len(palabra) >= 4
                ]

                encontradas = [
                    palabra
                    for palabra in palabras
                    if palabra in texto_normalizado
                ]

                if (
                    not palabras
                    or len(encontradas)
                    < max(1, len(palabras) // 2)
                ):
                    raise ValueError(
                        f"❌ La página no parece corresponder "
                        f"a {nombre_producto}."
                    )

                print(
                    "⚠️ Coincidencia parcial del nombre."
                )

            else:

                print(
                    f"✅ Producto confirmado: "
                    f"{nombre_producto}"
                )

            # ==================================================
            # EAN
            # ==================================================

            print()
            print("🔎 Comprobando EAN...")

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
                        "⚠️ El EAN no aparece "
                        "directamente en la ficha."
                    )

            # ==================================================
            # FORMATO
            # ==================================================

            print()
            print("🍾 Comprobando formato...")

            formato_normalizado = normalizar_texto(
                producto_config.formato
            )

            if formato_normalizado in texto_normalizado:

                print(
                    f"✅ Formato confirmado: "
                    f"{producto_config.formato}"
                )

            else:

                print(
                    f"⚠️ No se ha confirmado directamente "
                    f"el formato {producto_config.formato}."
                )

            # ==================================================
            # IVA
            # ==================================================

            print()
            print("💶 Comprobando IVA...")

            iva_incluido = (
                "iva incl"
                in texto_normalizado
            )

            if iva_incluido:

                print(
                    "✅ Precio con IVA incluido."
                )

            else:

                print(
                    "⚠️ No se ha encontrado "
                    "'IVA incluido'."
                )

            # ==================================================
            # STOCK
            # ==================================================

            print()
            print("📦 Comprobando stock...")

            sin_stock = (
                "producto sin stock"
                in texto_normalizado
                or "sin stock"
                in texto_normalizado
            )

            if sin_stock:

                stock = False
                estado = "Sin stock"

                print(
                    "⚠️ Producto actualmente "
                    "sin stock."
                )

            else:

                stock = True
                estado = "OK"

                print(
                    "✅ Producto disponible."
                )

            # ==================================================
            # PRECIO
            # ==================================================

            print()
            print("💰 Buscando precio...")

            # Primero buscamos precios próximos a
            # "IVA incl", para evitar confundirlos
            # con gastos de envío u otros importes.

            precios_iva = re.findall(
                r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})"
                r"\s*€\s*iva\s*incl",
                texto_producto,
                flags=re.IGNORECASE
            )

            precios_float = []

            for valor in precios_iva:

                precio = convertir_precio(
                    valor
                )

                if precio is not None:
                    precios_float.append(
                        precio
                    )

            # Si no encontramos el precio asociado
            # al IVA, buscamos precios generales.

            if not precios_float:

                print(
                    "⚠️ No se encontró precio asociado "
                    "directamente a 'IVA incl'."
                )

                precios = re.findall(
                    r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})"
                    r"\s*€",
                    texto_producto
                )

                for valor in precios:

                    precio = convertir_precio(
                        valor
                    )

                    if precio is not None:

                        if 0 < precio < 10000:

                            precios_float.append(
                                precio
                            )

            if not precios_float:

                raise ValueError(
                    "❌ No se ha encontrado "
                    "ningún precio válido."
                )

            print(
                "💰 Precios encontrados:",
                precios_float
            )

            # El primer precio asociado a IVA incluido
            # es el precio del producto.

            precio = precios_float[0]

            print(
                f"💰 Precio seleccionado: "
                f"{precio:.2f} €"
            )

            # ==================================================
            # VENDEDOR
            # ==================================================

            vendedor = "Decántalo"

            print()
            print(
                "🏪 Vendedor:",
                vendedor
            )

            # ==================================================
            # RESULTADO
            # ==================================================

            resultado = ProductoPrecio(
                tienda="Decántalo",
                vendedor=vendedor,
                ean=ean_esperado,
                producto=nombre_producto,
                marca=producto_config.marca,
                formato=producto_config.formato,
                precio=precio,
                stock=stock,
                estado=estado,
                fuente="Decántalo web",
                url=url_decantalo
            )

            print()
            print("=" * 80)
            print("✅ DECÁNTALO COMPLETADO")
            print("=" * 80)

            print(resultado)

            return resultado

        except Exception as e:

            print()
            print("=" * 80)
            print("❌ ERROR EN DECÁNTALO")
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
        "Canasta Cream"
    )

    resultado = obtener_decantalo(
        producto
    )

    print()
    print("=" * 80)
    print("🍷 RESULTADO FINAL")
    print("=" * 80)

    print(resultado)
