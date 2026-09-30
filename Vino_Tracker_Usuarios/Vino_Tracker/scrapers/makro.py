# ============================================================
# 🍷 VINO TRACKER - SCRAPER MAKRO
# ============================================================

import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright


# ============================================================
# IMPORTAR ProductoPrecio
# ============================================================

ROOT_DIR = Path.cwd()

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scrapers.common import ProductoPrecio


# ============================================================
# URL MAKRO
# ============================================================

URL_MAKRO = "https://www.makro.es/"


# ============================================================
# NORMALIZAR TEXTO
# ============================================================

def normalizar(texto):

    if not texto:
        return ""

    texto = str(texto).lower().strip()

    texto = unicodedata.normalize(
        "NFD",
        texto
    )

    texto = "".join(
        c
        for c in texto
        if unicodedata.category(c) != "Mn"
    )

    return texto


# ============================================================
# PALABRAS GENÉRICAS
# ============================================================

PALABRAS_IGNORAR = {
    "vino",
    "vinos",
    "botella",
    "botellas",
    "frasco",
    "frascos",
    "unidad",
    "unidades",
    "producto",
    "productos",
    "cl",
    "ml",
    "litro",
    "litros",
    "l",
    "de",
    "del",
    "la",
    "el",
    "los",
    "las",
    "con",
    "sin",
    "do",
    "jerez",
    "sherry",
}


# ============================================================
# VARIANTES CONOCIDAS
# ============================================================

VARIANTES_PALABRAS = {

    "cream": {
        "cream",
        "crema",
    },

    "crema": {
        "cream",
        "crema",
    },

    "tio": {
        "tio",
        "tío",
    },

    "px": {
        "px",
        "pedro",
        "ximenez",
        "ximénez",
    },

    "pedro": {
        "pedro",
    },

    "ximenez": {
        "ximenez",
        "ximénez",
    },

    "don": {
        "don",
    },

    "zoilo": {
        "zoilo",
    },

    "pepe": {
        "pepe",
    },
}

# ============================================================
# CONSULTAS ALTERNATIVAS MAKRO
# ============================================================

ALIAS_BUSQUEDA_MAKRO = {

    "canasta cream": [
        "Canasta Cream",
        "Canasta crema",
    ],

    "tio pepe": [
        "Tío Pepe",
        "Tio Pepe",
    ],

    "don zoilo pedro ximenez": [
        "Don Zoilo",
        "Don Zoilo PX",
        "Don Zoilo Pedro Ximenez",
        "Don Zoilo Pedro Ximénez",
    ],
}


def obtener_consultas_makro(nombre_producto):

    clave = normalizar(nombre_producto)

    if clave in ALIAS_BUSQUEDA_MAKRO:
        return ALIAS_BUSQUEDA_MAKRO[clave]

    return [
        nombre_producto
    ]

# ============================================================
# PALABRAS IMPORTANTES DEL PRODUCTO
# ============================================================

def palabras_producto(nombre):

    texto = normalizar(nombre)

    palabras = re.findall(
        r"\w+",
        texto,
        flags=re.UNICODE
    )

    resultado = []

    for palabra in palabras:

        if len(palabra) <= 2:
            continue

        if palabra in PALABRAS_IGNORAR:
            continue

        if palabra not in resultado:
            resultado.append(palabra)

    return resultado


# ============================================================
# VARIANTES DE UNA PALABRA
# ============================================================

def variantes_palabra(palabra):

    palabra_normalizada = normalizar(
        palabra
    )

    if palabra_normalizada in VARIANTES_PALABRAS:

        return {
            normalizar(x)
            for x in VARIANTES_PALABRAS[
                palabra_normalizada
            ]
        }

    return {
        palabra_normalizada
    }


# ============================================================
# COMPROBAR PALABRA
# ============================================================

def palabra_aparece(
    texto_normalizado,
    palabra
):

    variantes = variantes_palabra(
        palabra
    )

    for variante in variantes:

        # Coincidencia como palabra
        patron = (
            r"\b"
            + re.escape(variante)
            + r"\b"
        )

        if re.search(
            patron,
            texto_normalizado
        ):

            return True

    return False


# ============================================================
# COMPROBAR PRODUCTO
# ============================================================

def producto_coincide(
    texto,
    nombre_producto
):

    texto_normalizado = normalizar(
        texto
    )

    palabras = palabras_producto(
        nombre_producto
    )

    if not palabras:
        return False

    for palabra in palabras:

        if not palabra_aparece(
            texto_normalizado,
            palabra
        ):

            return False

    return True


# ============================================================
# EXTRAER PRECIOS
# ============================================================

def extraer_precios(texto):

    if not texto:
        return []

    encontrados = re.findall(
        r'(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})\s*€',
        texto
    )

    precios = []

    for valor_texto in encontrados:

        try:

            valor = (
                valor_texto
                .replace(".", "")
                .replace(",", ".")
            )

            valor = float(valor)

            if (
                valor > 0
                and valor not in precios
            ):

                precios.append(valor)

        except ValueError:

            continue

    return precios


# ============================================================
# COMPROBAR PRECIO
# ============================================================

def contiene_precio(texto):

    return bool(
        extraer_precios(texto)
    )


# ============================================================
# BUSCAR BLOQUE PRODUCTO
# ============================================================

def buscar_bloque_producto(
    page,
    nombre_producto
):

    print()
    print("=" * 80)
    print("🔎 BUSCANDO BLOQUE DEL PRODUCTO")
    print("=" * 80)

    elementos = page.locator(
        "body *"
    )

    try:

        cantidad = elementos.count()

        print(
            f"🔢 Elementos DOM encontrados: {cantidad}"
        )

    except Exception as e:

        print(
            "⚠️ No se pudo contar el DOM:",
            e
        )

        return None, ""

    candidatos = []

    limite = min(
        cantidad,
        5000
    )

    for i in range(limite):

        try:

            elemento = elementos.nth(i)

            if not elemento.is_visible():
                continue

            texto = (
                elemento
                .inner_text()
                .strip()
            )

            if not texto:
                continue

            if len(texto) > 600:
                continue

            if not producto_coincide(
                texto,
                nombre_producto
            ):
                continue

            precios = extraer_precios(
                texto
            )

            if not precios:
                continue

            candidatos.append(
                (
                    len(texto),
                    elemento,
                    texto,
                    precios
                )
            )

        except Exception:
            continue

    candidatos.sort(
        key=lambda x: x[0]
    )

    if not candidatos:

        print()
        print(
            "❌ No se encontró ningún bloque "
            "producto + precio."
        )

        return None, ""

    print()
    print(
        f"🎯 Candidatos encontrados: "
        f"{len(candidatos)}"
    )

    for posicion, candidato in enumerate(
        candidatos[:10],
        start=1
    ):

        longitud, _, txt, precios = candidato

        print()
        print(
            f"--- Candidato {posicion} ---"
        )

        print(
            f"Longitud: {longitud}"
        )

        print(
            f"Precios: {precios}"
        )

        print(
            txt[:500]
        )

    _, mejor_elemento, mejor_texto, _ = (
        candidatos[0]
    )

    print()
    print(
        "✅ Mejor bloque localizado"
    )

    return (
        mejor_elemento,
        mejor_texto
    )


# ============================================================
# RESOLVER COOKIES
# ============================================================

def resolver_cookies(page):

    print()
    print("=" * 80)
    print("🍪 COMPROBANDO COOKIES")
    print("=" * 80)

    selectores = [
        "button:has-text('Aceptar todas')",
        "button:has-text('Aceptar todo')",
        "button:has-text('Aceptar')",
        "button:has-text('Rechazar todas')",
        "button:has-text('Rechazar')",
        "[class*='consent'] button",
        "[class*='cookie'] button",
    ]

    for selector in selectores:

        try:

            botones = page.locator(
                selector
            )

            cantidad = botones.count()

            if cantidad == 0:
                continue

            for i in range(
                min(cantidad, 5)
            ):

                boton = botones.nth(i)

                try:

                    if not boton.is_visible():
                        continue

                    print()
                    print(
                        "🍪 Botón encontrado:",
                        selector
                    )

                    try:
                        print(
                            "Texto:",
                            boton.inner_text()
                        )
                    except Exception:
                        pass

                    boton.click(
                        force=True,
                        timeout=5000
                    )

                    print(
                        "✅ Cookies gestionadas"
                    )

                    page.wait_for_timeout(
                        1500
                    )

                    return True

                except Exception:
                    continue

        except Exception:
            continue

    print()
    print(
        "ℹ️ No fue necesario gestionar cookies."
    )

    return False


# ============================================================
# LOCALIZAR BUSCADOR
# ============================================================

def localizar_buscador(page):

    selectores = [
        "#site-header-input",
        'input[name="textBoxSearch"]',
        'input[placeholder*="Buscar"]',
        'input[type="search"]',
    ]

    for selector in selectores:

        try:

            buscador = page.locator(
                selector
            ).first

            if buscador.count() == 0:
                continue

            buscador.wait_for(
                state="visible",
                timeout=5000
            )

            print()
            print(
                "✅ Buscador localizado:",
                selector
            )

            return buscador

        except Exception:
            continue

    return None


# ============================================================
# DETECTAR ERROR "ARE YOU LOST?"
# ============================================================

def pagina_are_you_lost(texto):

    if not texto:
        return False

    texto_normalizado = normalizar(
        texto
    )

    return (
        "are you lost" in texto_normalizado
        or
        "only our team of experts has access here"
        in texto_normalizado
    )


# ============================================================
# CREAR RESULTADO VACÍO
# ============================================================

def resultado_vacio(
    producto_config,
    estado="NO ENCONTRADO"
):

    ean = getattr(
        producto_config,
        "ean",
        None
    )

    nombre = getattr(
        producto_config,
        "nombre",
        ""
    )

    marca = getattr(
        producto_config,
        "marca",
        ""
    )

    formato = getattr(
        producto_config,
        "formato",
        ""
    )

    return ProductoPrecio(
        tienda="Makro",
        vendedor="Makro",
        ean=ean,
        producto=nombre,
        marca=marca,
        formato=formato,
        precio=None,
        stock=False,
        estado=estado,
        fuente="Makro web (precio sin IVA)",
        url=URL_MAKRO
    )


# ============================================================
# EXTRAER URL REAL DEL PRODUCTO
# ============================================================

def extraer_url_producto(
    elemento,
    page
):

    try:

        enlaces = elemento.locator(
            "a"
        )

        cantidad = enlaces.count()

        for i in range(cantidad):

            try:

                enlace = enlaces.nth(i)

                href = enlace.get_attribute(
                    "href"
                )

                if not href:
                    continue

                url = urljoin(
                    page.url,
                    href
                )

                if (
                    "makro" in url.lower()
                    and
                    "/shop/" in url.lower()
                ):

                    return url

            except Exception:
                continue

    except Exception:
        pass

    return page.url


# ============================================================
# EXTRAER NOMBRE REAL
# ============================================================

def extraer_nombre_real(
    texto_producto,
    nombre_config
):

    try:

        lineas = [
            linea.strip()
            for linea
            in texto_producto.splitlines()
            if linea.strip()
        ]

        for linea in lineas:

            linea_normalizada = normalizar(
                linea
            )

            if len(linea) < 5:
                continue

            if "€" in linea:
                continue

            if linea_normalizada.startswith(
                "disponible"
            ):
                continue

            if linea_normalizada in {
                "1 botella",
                "1 botellas",
                "unidad",
                "unidades",
            }:
                continue

            return linea

    except Exception:
        pass

    return nombre_config


# ============================================================
# CLASE SCRAPER MAKRO
# ============================================================

class MakroScraper:

    def __init__(
        self,
        headless=False
    ):

        self.headless = headless

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.buscador = None

        self.iniciado = False


    # ========================================================
    # ABRIR MAKRO
    # ========================================================

    def abrir(self):

        if self.iniciado:
            return True

        print()
        print("=" * 80)
        print("🌐 ABRIENDO MAKRO")
        print("=" * 80)

        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(
            headless=self.headless
        )

        self.context = self.browser.new_context(
            viewport={
                "width": 1440,
                "height": 900
            },
            locale="es-ES",
            user_agent=(
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/151.0.0.0 "
                "Safari/537.36"
            )
        )

        self.page = self.context.new_page()

        response = self.page.goto(
            URL_MAKRO,
            wait_until="domcontentloaded",
            timeout=60000
        )

        if response:

            print(
                "STATUS:",
                response.status
            )

        print(
            "URL:",
            self.page.url
        )

        self.page.wait_for_timeout(
            8000
        )

        resolver_cookies(
            self.page
        )

        self.buscador = localizar_buscador(
            self.page
        )

        if self.buscador is None:

            print()
            print(
                "❌ No se encontró el buscador de Makro."
            )

            return False

        self.iniciado = True

        print()
        print(
            "✅ MAKRO PREPARADO"
        )

        return True

    # ========================================================
    # RECUPERAR SESIÓN MAKRO
    # ========================================================

    def recuperar(self):

        print()
        print("=" * 80)
        print("🔄 RECUPERANDO SESIÓN MAKRO")
        print("=" * 80)

        try:

            self.page.goto(
                URL_MAKRO,
                wait_until="domcontentloaded",
                timeout=60000
            )

            print(
                "🔗 URL recuperación:",
                self.page.url
            )

            self.page.wait_for_timeout(
                5000
            )

            resolver_cookies(
                self.page
            )

            self.buscador = localizar_buscador(
                self.page
            )

            if self.buscador is None:

                print(
                    "❌ No se pudo recuperar el buscador."
                )

                return False

            print(
                "✅ Sesión Makro recuperada."
            )

            return True

        except Exception as e:

            print(
                "❌ Error recuperando Makro:",
                type(e).__name__,
                e
            )

            return False



    # ========================================================
    # BUSCAR PRODUCTO
    # ========================================================

    def buscar_producto(
        self,
        producto_config
    ):

        nombre_config = getattr(
            producto_config,
            "nombre",
            None
        )

        if not nombre_config:

            return resultado_vacio(
                producto_config,
                "ERROR"
            )

        if not self.iniciado:

            if not self.abrir():

                return resultado_vacio(
                    producto_config,
                    "ERROR"
                )

        ean = getattr(
            producto_config,
            "ean",
            None
        )

        marca = getattr(
            producto_config,
            "marca",
            ""
        )

        formato = getattr(
            producto_config,
            "formato",
            ""
        )

        consultas = obtener_consultas_makro(
            nombre_config
        )

        print()
        print("=" * 80)
        print(
            f"🍷 MAKRO → {nombre_config}"
        )
        print("=" * 80)

        print(
            "🏷️ EAN:",
            ean
        )

        print(
            "🏭 Marca:",
            marca
        )

        print(
            "📦 Formato:",
            formato
        )

        print(
            "🔤 Palabras:",
            palabras_producto(
                nombre_config
            )
        )

        print()
        print(
            "🔎 Consultas alternativas:"
        )

        for consulta in consultas:

            print(
                "   •",
                consulta
            )

        # ====================================================
        # PROBAR TODAS LAS CONSULTAS
        # ====================================================

        for numero_consulta, consulta in enumerate(
            consultas,
            start=1
        ):

            print()
            print("#" * 80)

            print(
                f"🔎 CONSULTA "
                f"{numero_consulta}/{len(consultas)}"
            )

            print(
                f"🍷 {consulta}"
            )

            print("#" * 80)

            try:

                # --------------------------------------------
                # ASEGURAR BUSCADOR
                # --------------------------------------------

                self.buscador = localizar_buscador(
                    self.page
                )

                if self.buscador is None:

                    print(
                        "⚠️ Buscador no disponible."
                    )

                    if not self.recuperar():

                        continue

                    self.buscador = localizar_buscador(
                        self.page
                    )

                    if self.buscador is None:

                        continue

                # --------------------------------------------
                # ESCRIBIR CONSULTA
                # --------------------------------------------

                print()
                print(
                    "✍️ Consulta:",
                    consulta
                )

                try:

                    self.buscador.fill(
                        consulta,
                        timeout=10000
                    )

                except Exception:

                    self.buscador.fill(
                        consulta,
                        force=True,
                        timeout=10000
                    )

                # --------------------------------------------
                # LANZAR BÚSQUEDA
                # --------------------------------------------

                self.buscador.press(
                    "Enter",
                    timeout=10000
                )

                print(
                    "🚀 Búsqueda lanzada"
                )

                # --------------------------------------------
                # ESPERAR RESULTADOS
                # --------------------------------------------

                self.page.wait_for_timeout(
                    7000
                )

                print()
                print(
                    "🔗 URL resultados:",
                    self.page.url
                )

                # --------------------------------------------
                # TEXTO VISIBLE
                # --------------------------------------------

                try:

                    texto = self.page.locator(
                        "body"
                    ).inner_text()

                except Exception:

                    texto = ""

                print()
                print(
                    "📄 Texto visible:"
                )

                print(
                    texto[:8000]
                )

                # --------------------------------------------
                # DETECTAR ARE YOU LOST
                # --------------------------------------------

                if pagina_are_you_lost(
                    texto
                ):

                    print()
                    print(
                        "⚠️ MAKRO DEVOLVIÓ:"
                    )

                    print(
                        "   ARE YOU LOST?"
                    )

                    print()
                    print(
                        "⚠️ Esto NO significa "
                        "producto no disponible."
                    )

                    self.guardar_evidencia(
                        nombre_config,
                        f"are_you_lost_{numero_consulta}"
                    )

                    # ----------------------------------------
                    # RECUPERAR SESIÓN
                    # ----------------------------------------

                    if numero_consulta < len(
                        consultas
                    ):

                        self.recuperar()

                        continue

                    return resultado_vacio(
                        producto_config,
                        "ERROR MAKRO"
                    )

                # --------------------------------------------
                # BUSCAR BLOQUE PRODUCTO
                # --------------------------------------------

                producto_locator, texto_producto = (
                    buscar_bloque_producto(
                        self.page,
                        consulta
                    )
                )

                if producto_locator is None:

                    print()
                    print(
                        "❌ No se encontró producto "
                        "con esta consulta:"
                    )

                    print(
                        "   ",
                        consulta
                    )

                    self.guardar_evidencia(
                        nombre_config,
                        f"no_encontrado_{numero_consulta}"
                    )

                    # ----------------------------------------
                    # SI HAY MÁS CONSULTAS, RECUPERAR
                    # ----------------------------------------

                    if numero_consulta < len(
                        consultas
                    ):

                        self.recuperar()

                        continue

                    return resultado_vacio(
                        producto_config,
                        "NO ENCONTRADO"
                    )

                # --------------------------------------------
                # MOSTRAR BLOQUE
                # --------------------------------------------

                print()
                print("=" * 80)
                print("📦 BLOQUE PRODUCTO")
                print("=" * 80)

                print(
                    texto_producto
                )

                # --------------------------------------------
                # PRECIO
                # --------------------------------------------

                precios = extraer_precios(
                    texto_producto
                )

                print()
                print(
                    "💰 Precios:",
                    precios
                )

                if not precios:

                    print(
                        "❌ Producto localizado "
                        "pero sin precio."
                    )

                    self.guardar_evidencia(
                        nombre_config,
                        "sin_precio"
                    )

                    return resultado_vacio(
                        producto_config,
                        "SIN PRECIO"
                    )

                # Makro muestra primero el precio sin IVA

                precio = precios[0]

                print()
                print(
                    "✅ PRECIO SIN IVA:",
                    f"{precio:.2f} €"
                )

                if len(precios) >= 2:

                    print(
                        "ℹ️ Precio siguiente:",
                        f"{precios[1]:.2f} €"
                    )

                # --------------------------------------------
                # STOCK
                # --------------------------------------------

                texto_normalizado = normalizar(
                    texto_producto
                )

                indicadores_stock = [

                    "disponible en makro",

                    "en stock",

                    "disponible",

                    "anadir a la cesta",

                    "añadir a la cesta",

                    "comprar",

                ]

                stock = any(

                    normalizar(indicador)
                    in texto_normalizado

                    for indicador
                    in indicadores_stock

                )

                print()

                if stock:

                    print(
                        "📦 STOCK: Disponible"
                    )

                else:

                    print(
                        "📦 STOCK: No confirmado"
                    )

                # --------------------------------------------
                # NOMBRE REAL
                # --------------------------------------------

                nombre_real = extraer_nombre_real(
                    texto_producto,
                    nombre_config
                )

                print()
                print(
                    "🍷 PRODUCTO DETECTADO:",
                    nombre_real
                )

                # --------------------------------------------
                # URL REAL
                # --------------------------------------------

                url_producto = extraer_url_producto(
                    producto_locator,
                    self.page
                )

                print()
                print(
                    "🔗 URL PRODUCTO:",
                    url_producto
                )

                # --------------------------------------------
                # CREAR RESULTADO
                # --------------------------------------------

                resultado = ProductoPrecio(

                    tienda="Makro",

                    vendedor="Makro",

                    ean=ean,

                    producto=nombre_config,

                    marca=marca,

                    formato=formato,

                    precio=precio,

                    stock=stock,

                    estado="OK",

                    fuente=(
                        "Makro web "
                        "(precio sin IVA)"
                    ),

                    url=url_producto

                )

                # --------------------------------------------
                # MOSTRAR RESULTADO
                # --------------------------------------------

                print()
                print("=" * 80)
                print("📊 RESULTADO MAKRO")
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

                # --------------------------------------------
                # ÉXITO
                # --------------------------------------------

                return resultado

            except Exception as e:

                print()
                print("=" * 80)
                print("❌ ERROR EN CONSULTA MAKRO")
                print("=" * 80)

                print(
                    "Consulta:",
                    consulta
                )

                print(
                    type(e).__name__,
                    e
                )

                self.guardar_evidencia(
                    nombre_config,
                    f"error_{numero_consulta}"
                )

                # --------------------------------------------
                # INTENTAR RECUPERAR
                # --------------------------------------------

                if numero_consulta < len(
                    consultas
                ):

                    self.recuperar()

                    continue

                return resultado_vacio(
                    producto_config,
                    "ERROR MAKRO"
                )

        # ====================================================
        # NINGUNA CONSULTA FUNCIONÓ
        # ====================================================

        return resultado_vacio(
            producto_config,
            "NO ENCONTRADO"
        )

    # ========================================================
    # GUARDAR EVIDENCIA
    # ========================================================

    def guardar_evidencia(
        self,
        nombre_producto,
        sufijo
    ):

        if self.page is None:
            return

        try:

            nombre = normalizar(
                nombre_producto
            )

            nombre = re.sub(
                r"[^a-z0-9]+",
                "_",
                nombre
            ).strip("_")

            if not nombre:
                nombre = "producto"

            base = (
                f"makro_{nombre}_{sufijo}"
            )

            self.page.screenshot(
                path=f"{base}.png",
                full_page=True
            )

            with open(
                f"{base}.html",
                "w",
                encoding="utf-8"
            ) as archivo:

                archivo.write(
                    self.page.content()
                )

            print()
            print(
                "💾 Evidencia guardada:",
                base
            )

        except Exception as e:

            print(
                "⚠️ No se pudo guardar evidencia:",
                e
            )


    # ========================================================
    # CERRAR
    # ========================================================

    def cerrar(self):

        print()
        print("=" * 80)
        print("🛑 CERRANDO MAKRO")
        print("=" * 80)

        try:

            if self.context:
                self.context.close()

        except Exception:
            pass

        try:

            if self.browser:
                self.browser.close()

        except Exception:
            pass

        try:

            if self.playwright:
                self.playwright.stop()

        except Exception:
            pass

        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
        self.buscador = None
        self.iniciado = False

        print(
            "✅ Makro cerrado correctamente."
        )


# ============================================================
# FUNCIÓN COMPATIBLE CON EL RESTO DEL PROYECTO
# ============================================================

def obtener_makro(
    producto_config
):

    scraper = MakroScraper(
        headless=False
    )

    try:

        return scraper.buscar_producto(
            producto_config
        )

    finally:

        scraper.cerrar()


# ============================================================
# PRUEBA DIRECTA - VARIOS PRODUCTOS
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 80)
    print("🧪 PRUEBA MAKRO - VARIOS PRODUCTOS")
    print("=" * 80)

    class ProductoCanasta:

        nombre = "Canasta Cream"
        ean = "8410028030903"
        marca = "Williams & Humbert"
        formato = "75 cl"

    class ProductoDonZoilo:

        nombre = "Don Zoilo Pedro Ximénez"
        ean = "8410028005307"
        marca = "Williams & Humbert"
        formato = "75 cl"


    class ProductoTioPepe:

        nombre = "Tío Pepe"
        ean = "8410023000031"
        marca = "González Byass"
        formato = "75 cl"


    productos_prueba = [

        ProductoCanasta(),

        ProductoDonZoilo(),

        ProductoTioPepe(),

    ]


    scraper = MakroScraper(
        headless=False
    )


    try:

        # ====================================================
        # ABRIR MAKRO UNA SOLA VEZ
        # ====================================================

        if not scraper.abrir():

            print()
            print(
                "❌ No se pudo abrir Makro."
            )

            sys.exit(1)


        resultados = []


        # ====================================================
        # BUSCAR TODOS LOS PRODUCTOS
        # ====================================================

        for numero, producto in enumerate(
            productos_prueba,
            start=1
        ):

            print()
            print()
            print("#" * 80)
            print(
                f"🍷 PRODUCTO {numero}/"
                f"{len(productos_prueba)}"
            )
            print("#" * 80)

            resultado = scraper.buscar_producto(
                producto
            )

            resultados.append(
                resultado
            )


        # ====================================================
        # RESUMEN
        # ====================================================

        print()
        print()
        print("=" * 80)
        print("📊 RESUMEN FINAL MAKRO")
        print("=" * 80)

        for resultado in resultados:

            print()

            print(
                f"🍷 {resultado.producto}"
            )

            print(
                f"   EAN:     {resultado.ean}"
            )

            print(
                f"   Precio:  {resultado.precio}"
            )

            print(
                f"   Stock:   {resultado.stock}"
            )

            print(
                f"   Estado:  {resultado.estado}"
            )

            print(
                f"   URL:     {resultado.url}"
            )


    finally:

        scraper.cerrar()


    print()
    print("=" * 80)
    print("🏁 PRUEBA DE VARIOS PRODUCTOS TERMINADA")
    print("=" * 80)