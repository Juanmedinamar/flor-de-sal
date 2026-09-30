import sys
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

# ============================================================
# RUTA DEL PROYECTO
# ============================================================

ROOT_DIR = Path.cwd()

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ============================================================
# CONFIGURACIÓN
# ============================================================

PRODUCTO_PRUEBA = "Canasta Cream"
CODIGO_POSTAL = "11407"

URL_INICIO = "https://www.mercadona.es/"
URL_TIENDA = "https://tienda.mercadona.es/"

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def limpiar_precio(texto):
    """
    Convierte precios españoles como:
        7,90 €
        7,90€ por Unidad
        10,53€ por Litro

    en float.
    """

    if not texto:
        return None

    match = re.search(r"(\d+[,.]\d{2})\s*€", texto)

    if not match:
        return None

    valor = match.group(1).replace(",", ".")

    try:
        return float(valor)
    except ValueError:
        return None


def normalizar(texto):
    """
    Normaliza texto para búsquedas.
    """

    if not texto:
        return ""

    return (
        texto.lower()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ü", "u")
    )


# ============================================================
# SCRAPER
# ============================================================

def obtener_mercadona(producto_config=None):

    # ========================================================
    # PRODUCTO DINÁMICO
    # ========================================================

    if producto_config is not None:

        nombre_producto = getattr(
            producto_config,
            "nombre",
            None
        )

        if not nombre_producto:
            nombre_producto = getattr(
                producto_config,
                "producto",
                None
            )

        if not nombre_producto:
            nombre_producto = PRODUCTO_PRUEBA

        ean = getattr(
            producto_config,
            "ean",
            "PENDIENTE"
        )

        marca = getattr(
            producto_config,
            "marca",
            ""
        )

        formato = getattr(
            producto_config,
            "formato",
            "75 cl"
        )

    else:

        nombre_producto = PRODUCTO_PRUEBA
        ean = "PENDIENTE"
        marca = ""
        formato = "75 cl"

    print("=" * 80)
    print("🛒 MERCADONA")
    print(f"📦 Producto: {nombre_producto}")
    print(f"🔢 EAN: {ean}")
    print(f"🏷️ Marca: {marca}")
    print(f"📦 Formato: {formato}")
    print(f"📍 Código postal: {CODIGO_POSTAL}")
    print("=" * 80)

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=False
        )

        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="es-ES"
        )

        page = context.new_page()

        # ====================================================
        # 1. ABRIR MERCADONA
        # ====================================================

        print("\n🌐 Abriendo Mercadona...")

        page.goto(
            URL_INICIO,
            wait_until="domcontentloaded",
            timeout=60000
        )

        page.wait_for_timeout(3000)

        print(f"URL inicial: {page.url}")
        print(f"Título: {page.title()}")

        page.screenshot(
            path="mercadona_inicio.png",
            full_page=True
        )

        # ====================================================
        # 2. INTRODUCIR CÓDIGO POSTAL
        # ====================================================

        print("\n📍 Configurando código postal...")

        selectores_cp = [
            'input[placeholder*="postal" i]',
            'input[aria-label*="postal" i]',
            'input[type="text"]'
        ]

        campo_cp = None

        for selector in selectores_cp:

            try:

                locator = page.locator(selector)

                count = locator.count()

                for i in range(count):

                    elemento = locator.nth(i)

                    if elemento.is_visible():

                        campo_cp = elemento

                        print(
                            f"✅ Campo CP encontrado: {selector}"
                        )

                        break

                if campo_cp:
                    break

            except Exception:
                pass

        if not campo_cp:

            print(
                "❌ No se encontró el campo de código postal."
            )

            browser.close()

            return None

        campo_cp.fill(CODIGO_POSTAL)

        page.wait_for_timeout(1000)

        # ====================================================
        # 3. PULSAR BOTÓN CP
        # ====================================================

        print("🔘 Buscando botón para confirmar CP...")

        pulsado = False

        try:

            submits = page.locator(
                'input[type="submit"]'
            )

            for i in range(submits.count()):

                boton = submits.nth(i)

                if boton.is_visible():

                    print(
                        "🖱️ Pulsando botón submit"
                    )

                    boton.click()

                    pulsado = True

                    break

        except Exception:
            pass

        if not pulsado:

            nombres = [
                "Entrar",
                "Continuar",
                "Aceptar",
                "Confirmar"
            ]

            for nombre in nombres:

                try:

                    boton = page.get_by_role(
                        "button",
                        name=re.compile(
                            nombre,
                            re.IGNORECASE
                        )
                    )

                    if boton.count() > 0:

                        for i in range(boton.count()):

                            b = boton.nth(i)

                            if b.is_visible():

                                print(
                                    f"🖱️ Pulsando botón: {nombre}"
                                )

                                b.click()

                                pulsado = True

                                break

                    if pulsado:
                        break

                except Exception:
                    pass

        if not pulsado:

            print(
                "⚠️ No se pudo identificar el botón de CP."
            )

            try:

                campo_cp.press("Enter")

                print("⌨️ Se ha pulsado Enter")

            except Exception:
                pass

        # ====================================================
        # 4. ESPERAR REDIRECCIÓN
        # ====================================================

        page.wait_for_timeout(5000)

        print("\n🌐 URL después del CP:")
        print(page.url)

        print("\n📄 Título:")
        print(page.title())

        page.screenshot(
            path="mercadona_cp.png",
            full_page=True
        )

        # ====================================================
        # 5. LOCALIZAR BUSCADOR
        # ====================================================

        print("\n" + "=" * 80)
        print("🔎 BUSCANDO PRODUCTO")
        print("=" * 80)

        selectores_busqueda = [
            'input[name="search"]',
            'input[placeholder*="buscar" i]',
            'input[aria-label*="buscar" i]',
            '[role="searchbox"]'
        ]

        buscador = None

        for selector in selectores_busqueda:

            try:

                locator = page.locator(selector)

                count = locator.count()

                for i in range(count):

                    elemento = locator.nth(i)

                    if elemento.is_visible():

                        buscador = elemento

                        print(
                            f"✅ Buscador encontrado: {selector}"
                        )

                        break

                if buscador:
                    break

            except Exception:
                pass

        if not buscador:

            print(
                "❌ No se encontró el buscador."
            )

            page.screenshot(
                path="mercadona_error_buscador.png",
                full_page=True
            )

            page.wait_for_timeout(5000)

            browser.close()

            return None

        # ====================================================
        # 6. BUSCAR PRODUCTO DINÁMICO
        # ====================================================

        print(
            f"\n⌨️ Buscando: {nombre_producto}"
        )

        buscador.fill(nombre_producto)

        page.wait_for_timeout(500)

        try:

            buscador.press("Enter")

            print("↵ Enter enviado")

        except Exception:
            pass

        page.wait_for_timeout(4000)

        print("\n🌐 URL después de buscar:")
        print(page.url)

        # ====================================================
        # 7. ANALIZAR RESULTADOS
        # ====================================================

        print("\n" + "=" * 80)
        print("🍷 ANALIZANDO RESULTADOS")
        print("=" * 80)

        html = page.content()

        Path(
            "mercadona_resultado.html"
        ).write_text(
            html,
            encoding="utf-8"
        )

        texto = page.locator(
            "body"
        ).inner_text()

        Path(
            "mercadona_resultado.txt"
        ).write_text(
            texto,
            encoding="utf-8"
        )

        page.screenshot(
            path="mercadona_resultado.png",
            full_page=True
        )

        # ====================================================
        # 8. BUSCAR BOTONES DE PRODUCTOS
        # ====================================================

        print(
            "\n🔘 Analizando botones de productos..."
        )

        botones = page.locator("button")

        encontrados = []

        producto_busqueda = normalizar(
            nombre_producto
        )

        for i in range(botones.count()):

            try:

                boton = botones.nth(i)

                if not boton.is_visible():
                    continue

                aria = boton.get_attribute(
                    "aria-label"
                )

                texto_boton = boton.inner_text()

                contenido = (
                    aria or texto_boton or ""
                ).strip()

                if not contenido:
                    continue

                normalizado = normalizar(
                    contenido
                )

                if producto_busqueda in normalizado:

                    print(
                        "\n🎯 PRODUCTO ENCONTRADO"
                    )

                    print("-" * 80)

                    print(
                        f"Texto:\n{contenido}"
                    )

                    encontrados.append(
                        (boton, contenido)
                    )

            except Exception:
                pass

        print(
            f"\n🎯 Coincidencias: {len(encontrados)}"
        )

        # ====================================================
        # 9. PRODUCTO NO ENCONTRADO
        # ====================================================

        if not encontrados:

            print(
                "\n❌ Producto NO encontrado."
            )

            print(
                "\nℹ️ Vamos a mostrar parte del texto "
                "de la página para investigar."
            )

            print(
                "\n" + texto[:5000]
            )

            page.wait_for_timeout(5000)

            browser.close()

            return None

        boton, contenido = encontrados[0]

        # ====================================================
        # 10. PRECIO
        # ====================================================

        precio = limpiar_precio(
            contenido
        )

        print(
            f"\n💰 Precio detectado: {precio}"
        )

        # ====================================================
        # 11. STOCK
        # ====================================================

        normalizado = normalizar(
            contenido
        )

        stock = True

        if (
            "no disponible" in normalizado
            or "agotado" in normalizado
            or "sin stock" in normalizado
        ):

            stock = False

        print(
            f"📦 Stock: "
            f"{'Disponible' if stock else 'NO disponible'}"
        )

        # ====================================================
        # 12. URL PRODUCTO
        # ====================================================

        url_producto = page.url

        try:

            enlace = boton.locator(
                "xpath=ancestor::a[1]"
            )

            if enlace.count() > 0:

                href = enlace.first.get_attribute(
                    "href"
                )

                if href:

                    if href.startswith("/"):

                        url_producto = (
                            "https://tienda.mercadona.es"
                            + href
                        )

                    else:

                        url_producto = href

        except Exception:
            pass

        print(
            f"🔗 URL: {url_producto}"
        )

        # ====================================================
        # 13. RESULTADO FINAL
        # ====================================================

        print("\n" + "=" * 80)
        print("✅ RESULTADO MERCADONA")
        print("=" * 80)

        print(
            "🏪 Tienda: Mercadona"
        )

        print(
            f"🍷 Producto: {nombre_producto}"
        )

        print(
            f"🔢 EAN: {ean}"
        )

        print(
            f"🏷️ Marca: {marca}"
        )

        print(
            f"📦 Formato: {formato}"
        )

        print(
            f"💰 Precio: {precio} €"
        )

        print(
            f"📦 Stock: "
            f"{'Sí' if stock else 'No'}"
        )

        print(
            f"🔗 URL: {url_producto}"
        )

        print("=" * 80)

        # ====================================================
        # 14. VALIDAR PRECIO
        # ====================================================

        if precio is None:

            print(
                "⚠️ No se pudo extraer el precio."
            )

            browser.close()

            return None

        # ====================================================
        # 15. CREAR ProductoPrecio
        # ====================================================

        try:

            from scrapers.common import ProductoPrecio

            resultado = ProductoPrecio(
                tienda="Mercadona",
                vendedor="Mercadona",
                ean=ean,
                producto=nombre_producto,
                marca=marca,
                formato=formato,
                precio=precio,
                stock=stock,
                estado="OK",
                fuente="Mercadona web",
                url=url_producto
            )

        except Exception as e:

            print(
                f"⚠️ Error creando ProductoPrecio: {e}"
            )

            resultado = None

        # ====================================================
        # 16. ESPERA FINAL
        # ====================================================

        print(
            "\n⏸️ Navegador abierto 10 segundos..."
        )

        page.wait_for_timeout(10000)

        browser.close()

        return resultado


# ============================================================
# PRUEBA DIRECTA
# ============================================================

if __name__ == "__main__":

    try:

        from productos import obtener_producto

        producto_config = obtener_producto(
            PRODUCTO_PRUEBA
        )

    except Exception as e:

        print(
            f"⚠️ No se pudo cargar productos.py: {e}"
        )

        producto_config = None

    resultado = obtener_mercadona(
        producto_config
    )

    print("\n" + "=" * 80)

    if resultado:

        print(
            "🎉 MERCADONA FUNCIONA"
        )

        print(
            f"Producto: {resultado.producto}"
        )

        print(
            f"Precio: {resultado.precio} €"
        )

        print(
            f"Stock: {resultado.stock}"
        )

        print(
            f"URL: {resultado.url}"
        )

    else:

        print(
            "❌ MERCADONA NO DEVOLVIÓ RESULTADO"
        )

    print("=" * 80)