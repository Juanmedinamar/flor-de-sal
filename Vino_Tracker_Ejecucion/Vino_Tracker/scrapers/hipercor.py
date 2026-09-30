# ============================================================
# 🍷 VINO TRACKER - SCRAPER HIPERCOR
# ============================================================

import re
import sys
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright


# ============================================================
# IMPORTAR ProductoPrecio
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scrapers.common import ProductoPrecio


# ============================================================
# URL DE BÚSQUEDA
# ============================================================

URL_BUSQUEDA = (
    "https://www.hipercor.es/supermercado/"
    "buscar?question={}"
    "&catalog=supermercado"
    "&stype=text_box"
)


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def normalizar_texto(texto):
    """
    Normaliza texto para facilitar las comparaciones.
    """

    if not texto:
        return ""

    texto = texto.lower()

    reemplazos = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "ñ": "n",
    }

    for origen, destino in reemplazos.items():
        texto = texto.replace(origen, destino)

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


def producto_coincide(nombre_producto, texto):
    """
    Comprueba si el producto solicitado aparece
    realmente en el texto encontrado.

    En búsquedas de Hipercor, el nombre mostrado
    puede ser diferente al nombre configurado.
    Por ejemplo:

        Configurado: "Canasta Cream"
        Hipercor:    "Vino oloroso dulce ... CANASTA"

    En esos casos utilizamos la primera palabra
    significativa del nombre como identificador base.
    Para nombres como "Gran Duque de Alba" exigimos
    todas las palabras significativas.
    """

    producto = normalizar_texto(nombre_producto)
    contenido = normalizar_texto(texto)

    palabras = producto.split()

    palabras_significativas = [
        palabra
        for palabra in palabras
        if len(palabra) >= 3
    ]

    if not palabras_significativas:
        return False

    # Para productos de dos palabras o más:
    # si la primera palabra es suficientemente distintiva,
    # permitimos que Hipercor utilice una denominación
    # comercial ligeramente diferente.
    if len(palabras_significativas) == 2:
        primera = palabras_significativas[0]

        if primera in contenido:
            return True

    # Para nombres de tres o más palabras exigimos
    # todas las palabras significativas.
    return all(
        palabra in contenido
        for palabra in palabras_significativas
    )


def extraer_precios(texto):
    """
    Extrae precios del texto visible.
    """

    patrones = [

        r'(\d{1,3}[,.]\d{2})\s*€',

        r'€\s*(\d{1,3}[,.]\d{2})'
    ]

    precios = []

    for patron in patrones:

        encontrados = re.findall(
            patron,
            texto,
            flags=re.IGNORECASE
        )

        for valor_texto in encontrados:

            try:

                valor = float(
                    valor_texto
                    .replace(".", "")
                    .replace(",", ".")
                )

                if valor > 0 and valor not in precios:

                    precios.append(valor)

            except ValueError:

                continue

    return precios


# ============================================================
# SCRAPER
# ============================================================

def obtener_hipercor(producto_config):

    print()
    print("=" * 80)
    print("🍷 HIPERCOR - SCRAPER")
    print("=" * 80)

    # ========================================================
    # DATOS DEL PRODUCTO
    # ========================================================

    ean = getattr(
        producto_config,
        "ean",
        None
    )

    nombre_config = getattr(
        producto_config,
        "nombre",
        None
    )

    marca = getattr(
        producto_config,
        "marca",
        None
    )

    formato = getattr(
        producto_config,
        "formato",
        None
    )

    urls = getattr(
        producto_config,
        "urls",
        {}
    )

    url_configurada = urls.get(
        "Hipercor"
    )

    print()
    print("📦 PRODUCTO SOLICITADO")
    print(
        f"   Nombre : {nombre_config}"
    )
    print(
        f"   EAN    : {ean}"
    )
    print(
        f"   Marca  : {marca}"
    )
    print(
        f"   Formato: {formato}"
    )

    # ========================================================
    # COMPROBAR URL
    # ========================================================

    if not url_configurada:

        print()
        print(
            "⚠️ No existe URL de Hipercor "
            "configurada para este producto."
        )

        return None

    # ========================================================
    # RESULTADO POR DEFECTO
    # ========================================================

    resultado = ProductoPrecio(

        tienda="Hipercor",

        vendedor="Hipercor",

        ean=ean,

        producto=nombre_config,

        marca=marca,

        formato=formato,

        precio=None,

        stock=False,

        estado="NO ENCONTRADO",

        fuente="Hipercor búsqueda",

        url=url_configurada
    )

    # ========================================================
    # PLAYWRIGHT
    # ========================================================

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=False
        )

        context = browser.new_context(

            viewport={
                "width": 1440,
                "height": 900
            },

            locale="es-ES",

            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36"
            )
        )

        page = context.new_page()

        try:

            # ==================================================
            # ABRIR FICHA CONFIGURADA
            # ==================================================

            print()
            print(
                "🌐 Abriendo ficha de Hipercor..."
            )

            print(
                url_configurada
            )

            response = page.goto(
                url_configurada,
                wait_until="domcontentloaded",
                timeout=60000
            )

            if response:

                print()
                print(
                    f"STATUS: {response.status}"
                )

            print(
                "URL:",
                page.url
            )

            # ==================================================
            # SI LA FICHA DEVUELVE 403
            # ==================================================

            if response and response.status in (
                403,
                404,
                410
            ):

                print()
                print(
                    "⚠️ La ficha individual devuelve "
                    f"HTTP {response.status}."
                )

                print(
                    "🔎 Intentaremos mediante búsqueda."
                )

                # ------------------------------------------------
                # BÚSQUEDA DEL PRODUCTO
                # ------------------------------------------------

                url_busqueda = URL_BUSQUEDA.format(
                    quote(nombre_config)
                )

                print()
                print(
                    "🌐 Abriendo búsqueda..."
                )

                print(
                    url_busqueda
                )

                response = page.goto(
                    url_busqueda,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                if response:

                    print()
                    print(
                        f"STATUS BÚSQUEDA: "
                        f"{response.status}"
                    )

                print(
                    "URL:",
                    page.url
                )

            # ==================================================
            # ESPERAR CARGA
            # ==================================================

            print()
            print(
                "⏳ Esperando carga del producto..."
            )

            page.wait_for_timeout(
                5000
            )

            # ==================================================
            # TEXTO VISIBLE
            # ==================================================

            texto = page.locator(
                "body"
            ).inner_text()

            print()
            print("=" * 80)
            print("📄 TEXTO VISIBLE")
            print("=" * 80)

            print(texto)

            # ==================================================
            # COMPROBAR PRODUCTO
            # ==================================================

            coincide = producto_coincide(
                nombre_config,
                texto
            )

            if not coincide:

                print()
                print(
                    "❌ EL PRODUCTO NO COINCIDE"
                )

                print(
                    f"   Buscado : {nombre_config}"
                )

                print(
                    "   No se guardará ningún precio."
                )

                return resultado

            print()
            print(
                "✅ PRODUCTO COINCIDENTE"
            )

            print(
                f"   {nombre_config}"
            )

            # ==================================================
            # BUSCAR PRECIO
            # ==================================================

            print()
            print("=" * 80)
            print("💰 BUSCANDO PRECIO")
            print("=" * 80)

            precios = extraer_precios(
                texto
            )

            print(
                "Precios encontrados:",
                precios
            )

            if not precios:

                print()
                print(
                    "❌ No se encontró precio "
                    "para el producto."
                )

                return resultado

            # ==================================================
            # SELECCIONAR PRECIO
            # ==================================================

            precio = precios[0]

            print()
            print(
                f"✅ PRECIO PRODUCTO: "
                f"{precio:.2f} €"
            )

            # ==================================================
            # PRODUCTO ENCONTRADO
            # ==================================================

            resultado = ProductoPrecio(

                tienda="Hipercor",

                vendedor="Hipercor",

                ean=ean,

                producto=nombre_config,

                marca=marca,

                formato=formato,

                precio=precio,

                stock=True,

                estado="OK",

                fuente="Hipercor web",

                url=url_configurada
            )

            # ==================================================
            # RESULTADO
            # ==================================================

            print()
            print("=" * 80)
            print("📊 RESULTADO HIPERCOR")
            print("=" * 80)

            print(
                f"tienda    : {resultado.tienda}"
            )

            print(
                f"vendedor  : {resultado.vendedor}"
            )

            print(
                f"ean       : {resultado.ean}"
            )

            print(
                f"producto  : {resultado.producto}"
            )

            print(
                f"marca     : {resultado.marca}"
            )

            print(
                f"formato   : {resultado.formato}"
            )

            print(
                f"precio    : {resultado.precio}"
            )

            print(
                f"stock     : {resultado.stock}"
            )

            print(
                f"estado    : {resultado.estado}"
            )

            print(
                f"fuente    : {resultado.fuente}"
            )

            print(
                f"url       : {resultado.url}"
            )

            # ==================================================
            # GUARDAR HTML
            # ==================================================

            try:

                page.screenshot(
                    path="hipercor_scraper_final.png",
                    full_page=True
                )

                with open(
                    "hipercor_scraper_final.html",
                    "w",
                    encoding="utf-8"
                ) as archivo:

                    archivo.write(
                        page.content()
                    )

                print()
                print(
                    "💾 HTML: "
                    "hipercor_scraper_final.html"
                )

                print(
                    "📸 Screenshot: "
                    "hipercor_scraper_final.png"
                )

            except Exception as e:

                print()
                print(
                    "⚠️ No se pudieron guardar "
                    "HTML/screenshot:",
                    e
                )

            return resultado

        except Exception as e:

            print()
            print(
                "❌ ERROR EN HIPERCOR:"
            )

            print(
                f"   {type(e).__name__}: {e}"
            )

            raise

        finally:

            print()
            print(
                "🛑 Cerrando navegador Hipercor..."
            )

            try:

                context.close()

            except Exception:

                pass

            try:

                browser.close()

            except Exception:

                pass


# ============================================================
# PRUEBA DIRECTA
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 80)
    print(
        "🧪 PRUEBA DIRECTA DEL SCRAPER HIPERCOR"
    )
    print("=" * 80)

    class ProductoPrueba:

        nombre = "Canasta Cream"

        ean = "8410028030903"

        marca = "Williams & Humbert"

        formato = "75 cl"

        urls = {

            "Hipercor":
                "https://www.hipercor.es/"
                "supermercado/"
                "B001018720300344-canasta-"
                "vino-oloroso-dulce-do-jerez-"
                "xeres-sherry-botella-75-cl/"
        }

    resultado = obtener_hipercor(
        ProductoPrueba()
    )

    print()
    print("=" * 80)
    print("🏁 PRUEBA TERMINADA")
    print("=" * 80)

    print(
        "Precio:",
        resultado.precio
    )

    print(
        "EAN:",
        resultado.ean
    )

    print(
        "Stock:",
        resultado.stock
    )

    print(
        "Estado:",
        resultado.estado
    )
