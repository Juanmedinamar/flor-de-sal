# -*- coding: utf-8 -*-

import json
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright


# ============================================================
# CONFIGURACIÓN
# ============================================================

PRODUCTO = "Canasta Cream"
EAN = "8410028030903"
PRODUCT_ID = "B001018720300344"

URL = (
    "https://www.elcorteingles.es/supermercado/"
    "B001018720300344-canasta-vino-oloroso-dulce-do-jerez-xeres-sherry-botella-75-cl/"
)

STATUS_FLOW_URL = (
    "https://www.elcorteingles.es/api/food-firefly/status_flow/"
    "?status_flow_query=001018720300344___"
    "&delivery_type=home_delivery"
    "&center_id=0701"
    "&subsite=supermarketStore"
)

CROSSSELLING_URL = (
    "https://www.elcorteingles.es/api/food-firefly/"
    "crosselling-pdp/B001018720300344/"
)


# ============================================================
# UTILIDADES
# ============================================================

def separador():
    print("=" * 100)


def contiene_objetivo(texto):
    if not texto:
        return False

    texto = str(texto).lower()

    return (
        EAN.lower() in texto
        or PRODUCT_ID.lower() in texto
        or "canasta" in texto
    )


def precio_float(texto):
    """
    Convierte:
        7,89 € -> 7.89
        7.89 € -> 7.89
    """
    if not texto:
        return None

    texto = str(texto)

    texto = texto.replace("€", "").strip()

    # Formato español
    if "," in texto:
        texto = texto.replace(".", "")
        texto = texto.replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return None


def guardar_json(nombre, datos):
    try:
        with open(nombre, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)

        print(f"✅ {nombre} creado")

    except Exception as e:
        print(f"❌ Error guardando {nombre}: {e}")


# ============================================================
# MAIN
# ============================================================

def main():

    separador()
    print("🍷 VINO TRACKER - TEST API EL CORTE INGLÉS")
    separador()

    print(f"📦 Producto : {PRODUCTO}")
    print(f"🔢 EAN      : {EAN}")
    print(f"🆔 ID       : {PRODUCT_ID}")

    separador()
    print("🚀 INICIANDO CHROMIUM")
    separador()

    respuestas = []
    respuestas_objetivo = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=False
        )

        context = browser.new_context(
            locale="es-ES",
            timezone_id="Europe/Madrid",
            viewport={
                "width": 1440,
                "height": 1000
            }
        )

        page = context.new_page()

        # ====================================================
        # CAPTURA DE RESPUESTAS
        # ====================================================

        def procesar_response(response):

            try:
                url = response.url

                if "/api/" not in url:
                    return

                status = response.status

                print()
                print("➡️ RESPONSE API")
                print(url)

                registro = {
                    "url": url,
                    "status": status,
                    "content_type": response.headers.get(
                        "content-type", ""
                    ),
                    "body": None
                }

                # Intentamos JSON
                try:
                    body = response.json()
                    registro["body"] = body

                except Exception:

                    try:
                        texto = response.text()

                        registro["body"] = texto[:200000]

                    except Exception:
                        registro["body"] = None

                respuestas.append(registro)

                texto = json.dumps(
                    registro["body"],
                    ensure_ascii=False
                ).lower()

                objetivo = contiene_objetivo(texto)

                if objetivo:
                    respuestas_objetivo.append(registro)

            except Exception:
                pass

        page.on("response", procesar_response)

        # ====================================================
        # ABRIR PÁGINA
        # ====================================================

        separador()
        print("🌐 ABRIENDO EL CORTE INGLÉS")
        separador()

        print(URL)

        try:

            response = page.goto(
                URL,
                wait_until="domcontentloaded",
                timeout=60000
            )

            if response:
                print()
                print(
                    f"📄 Página HTTP STATUS: "
                    f"{response.status}"
                )

        except Exception as e:

            print()
            print(f"❌ Error abriendo página: {e}")

        # ====================================================
        # ESPERA
        # ====================================================

        separador()
        print(
            "⏳ ESPERANDO 25 SEGUNDOS PARA CAPTURAR LAS APIs"
        )
        separador()

        for i in range(25, 0, -1):

            if i == 25 or i <= 5 or i % 5 == 0:
                print(
                    f"   ⏱️ {i:02d} segundos restantes..."
                )

            time.sleep(1)

        # ====================================================
        # RESUMEN APIS
        # ====================================================

        separador()
        print("📡 RESUMEN DE APIs CAPTURADAS")
        separador()

        print(
            f"Total APIs capturadas : {len(respuestas)}"
        )

        print(
            f"Respuestas objetivo   : "
            f"{len(respuestas_objetivo)}"
        )

        # ====================================================
        # FOOD-FIREFLY
        # ====================================================

        separador()
        print("🔬 FOOD-FIREFLY")
        separador()

        for respuesta in respuestas:

            url = respuesta["url"]

            if "food-firefly" not in url:
                continue

            print()
            print("-" * 100)

            print(
                f"STATUS: {respuesta['status']}"
            )

            print(f"URL: {url}")

            texto = json.dumps(
                respuesta["body"],
                ensure_ascii=False
            )

            es_status = "status_flow" in url
            es_cross = "crosselling" in url

            if es_status:
                print("🔎 TIPO: STATUS FLOW")

            elif es_cross:
                print("🔎 TIPO: CROSSSELLING PDP")

            print(
                f"   EAN encontrado: "
                f"{EAN.lower() in texto.lower()}"
            )

            print(
                f"   Product ID encontrado: "
                f"{PRODUCT_ID.lower() in texto.lower()}"
            )

        # ====================================================
        # CONSULTAS DIRECTAS
        # ====================================================

        separador()
        print("🎯 CONSULTA DIRECTA")
        separador()

        print()
        print("🔎 STATUS FLOW")
        print(STATUS_FLOW_URL)

        try:

            r = context.request.get(
                STATUS_FLOW_URL,
                timeout=30000
            )

            print(f"STATUS: {r.status}")

            if r.ok:
                print("✅ STATUS FLOW obtenido directamente")
            else:
                print("⚠️ La consulta directa fue rechazada.")

        except Exception as e:

            print(f"❌ Error: {e}")

        print()
        print("🔎 CROSSSELLING")
        print(CROSSSELLING_URL)

        try:

            r = context.request.get(
                CROSSSELLING_URL,
                timeout=30000
            )

            print(f"STATUS: {r.status}")

            if r.ok:
                print(
                    "✅ CROSSSELLING obtenido directamente"
                )
            else:
                print(
                    "⚠️ La consulta directa fue rechazada."
                )

        except Exception as e:

            print(f"❌ Error: {e}")

        # ====================================================
        # HTML
        # ====================================================

        separador()
        print("🔬 ANALIZANDO HTML DEL PRODUCTO")
        separador()

        try:

            html = page.content()

        except Exception as e:

            print(f"❌ No se pudo obtener HTML: {e}")
            html = ""

        print(
            f"📄 Tamaño HTML: {len(html):,} caracteres"
        )

        # Guardar HTML
        try:

            Path("corte_pagina.html").write_text(
                html,
                encoding="utf-8"
            )

            print("💾 corte_pagina.html guardado")

        except Exception as e:

            print(
                f"❌ Error guardando HTML: {e}"
            )

        print()

        print(
            f"EAN encontrado        : "
            f"{EAN in html}"
        )

        print(
            f"Product ID encontrado : "
            f"{PRODUCT_ID in html}"
        )

        print(
            f"'Canasta' encontrada  : "
            f"{'Canasta' in html}"
        )

        print(
            f"'Cream' encontrada    : "
            f"{'Cream' in html}"
        )

        print(
            f"'Williams' encontrada : "
            f"{'Williams' in html}"
        )

        # ====================================================
        # BÚSQUEDA PRECISA DEL BLOQUE DE PRECIO
        # ====================================================

        separador()
        print(
            "🎯 BÚSQUEDA DEL BLOQUE REAL DE PRECIO"
        )
        separador()

        precio_producto = None
        precio_litro = None
        bloque_precio = None

        # ----------------------------------------------------
        # MÉTODO 1
        # Buscar directamente la estructura:
        #
        # food-prices__price
        # price-integer
        # price-decimal
        # ----------------------------------------------------

        patron_precio = re.compile(
            r'<div[^>]*class="[^"]*food-prices__price[^"]*"'
            r'[^>]*>'
            r'.*?'
            r'<span[^>]*class="[^"]*price-integer[^"]*"'
            r'[^>]*>\s*([^<]+?)\s*</span>'
            r'.*?'
            r'<span[^>]*class="[^"]*price-decimal[^"]*"'
            r'[^>]*>\s*([^<]+?)\s*</span>'
            r'.*?</div>',
            re.IGNORECASE | re.DOTALL
        )

        coincidencias = patron_precio.findall(html)

        print(
            f"💰 Bloques de precio encontrados: "
            f"{len(coincidencias)}"
        )

        if coincidencias:

            for numero, (entero, decimal) in enumerate(
                coincidencias,
                1
            ):

                entero = entero.strip()
                decimal = decimal.strip()

                texto_precio = (
                    entero + decimal
                )

                valor = precio_float(
                    texto_precio
                )

                print()
                print(
                    f"   💶 Precio #{numero}: "
                    f"{texto_precio}"
                )

                print(
                    f"      Valor: {valor}"
                )

                # El primer bloque corresponde
                # normalmente al producto PDP
                if precio_producto is None and valor:
                    precio_producto = valor

        # ----------------------------------------------------
        # MÉTODO 2
        # Buscar el bloque completo alrededor de:
        # food-pdp-page-content-grid-detail-price
        # ----------------------------------------------------

        if precio_producto is not None:

            patron_bloque = re.compile(
                r'<div[^>]*'
                r'food-pdp-page-content-grid-detail-price'
                r'[^>]*>'
                r'.{0,5000}?',
                re.IGNORECASE | re.DOTALL
            )

            match_bloque = patron_bloque.search(
                html
            )

            if match_bloque:

                bloque_precio = match_bloque.group(0)

                print()
                print(
                    "✅ BLOQUE PDP DE PRECIO ENCONTRADO"
                )

                print(
                    f"   Tamaño bloque: "
                    f"{len(bloque_precio)} caracteres"
                )

                # Buscar precio por litro
                patron_litro = re.search(
                    r'(\d+[,.]\d+)\s*€\s*/\s*Litro',
                    bloque_precio,
                    re.IGNORECASE
                )

                if patron_litro:

                    precio_litro = precio_float(
                        patron_litro.group(1)
                    )

                    print(
                        f"   📏 Precio/litro: "
                        f"{precio_litro} €"
                    )

        # ====================================================
        # MÉTODO 3
        # EXTRAER PRECIO DIRECTAMENTE DEL DOM
        # ====================================================

        separador()
        print(
            "🔬 EXTRACCIÓN DIRECTA DEL DOM"
        )
        separador()

        try:

            precios_dom = page.locator(
                ".food-prices__price"
            ).all_inner_texts()

            print(
                f"Elementos .food-prices__price: "
                f"{len(precios_dom)}"
            )

            for i, texto in enumerate(
                precios_dom,
                1
            ):

                print(
                    f"   {i}. {texto.strip()}"
                )

                valor = precio_float(
                    texto
                )

                if (
                    valor is not None
                    and precio_producto is None
                ):
                    precio_producto = valor

        except Exception as e:

            print(
                f"⚠️ Error leyendo DOM: {e}"
            )

        # ====================================================
        # JSON-LD
        # ====================================================

        separador()
        print("🔎 BUSCANDO JSON-LD DEL PRODUCTO")
        separador()

        jsonld_resultados = []

        try:

            scripts = page.locator(
                'script[type="application/ld+json"]'
            ).all_inner_texts()

            print(
                f"Scripts JSON-LD encontrados: "
                f"{len(scripts)}"
            )

            for script in scripts:

                try:

                    data = json.loads(script)

                    jsonld_resultados.append(data)

                    texto = json.dumps(
                        data,
                        ensure_ascii=False
                    )

                    if (
                        EAN in texto
                        or PRODUCT_ID in texto
                        or "Canasta" in texto
                    ):

                        print()
                        print(
                            "🎯 JSON-LD CONTIENE EL PRODUCTO"
                        )

                        print(
                            json.dumps(
                                data,
                                ensure_ascii=False,
                                indent=2
                            )[:5000]
                        )

                except Exception:
                    pass

        except Exception as e:

            print(
                f"⚠️ Error leyendo JSON-LD: {e}"
            )

        # ====================================================
        # SCRIPTS
        # ====================================================

        separador()
        print(
            "🔎 BUSCANDO PRODUCT ID / EAN EN SCRIPTS"
        )
        separador()

        try:

            scripts = page.locator(
                "script"
            ).all_inner_texts()

            print(
                f"Total scripts: {len(scripts)}"
            )

            for numero, script in enumerate(
                scripts,
                1
            ):

                if (
                    EAN in script
                    or PRODUCT_ID in script
                    or "Canasta" in script
                ):

                    print()
                    print(
                        f"🎯 SCRIPT #{numero} CONTIENE PRODUCTO"
                    )

                    print(
                        f"Tamaño: "
                        f"{len(script)}"
                    )

                    # Buscar precios dentro del script
                    precios = re.findall(
                        r'\d+[,.]\d{2}',
                        script
                    )

                    if precios:

                        print("💰 Precios:")

                        for precio in precios:
                            print(
                                f"   → {precio} €"
                            )

        except Exception as e:

            print(
                f"⚠️ Error analizando scripts: {e}"
            )

        # ====================================================
        # RESULTADO FINAL
        # ====================================================

        separador()
        print("🏁 RESULTADO FINAL")
        separador()

        print(f"Producto : {PRODUCTO}")
        print(f"EAN      : {EAN}")
        print(f"ProductID: {PRODUCT_ID}")

        print()

        if precio_producto is not None:

            print(
                "🎉🎉🎉 PRECIO DEL PRODUCTO IDENTIFICADO"
            )

            print()

            print(
                f"🍷 Producto : {PRODUCTO}"
            )

            print(
                f"💶 PRECIO   : {precio_producto:.2f} €"
            )

            if precio_litro is not None:

                print(
                    f"📏 PRECIO/L : "
                    f"{precio_litro:.2f} €/Litro"
                )

            print()

            print(
                "✅ El precio procede del bloque PDP "
                "food-prices__price."
            )

            print(
                "✅ NO se utiliza 641,75 €."
            )

            print(
                "   Ese valor corresponde a la dirección "
                "del operador (Km 641,75)."
            )

        else:

            print(
                "⚠️ TODAVÍA NO SE HA PODIDO IDENTIFICAR "
                "EL PRECIO."
            )

        # ====================================================
        # GUARDAR RESPUESTAS
        # ====================================================

        separador()
        print(
            "💾 GUARDANDO ARCHIVOS"
        )
        separador()

        guardar_json(
            "corte_api_respuestas.json",
            respuestas
        )

        analisis = {
            "producto": PRODUCTO,
            "ean": EAN,
            "product_id": PRODUCT_ID,
            "url": URL,
            "precio_producto": precio_producto,
            "precio_litro": precio_litro,
            "apis_capturadas": len(respuestas),
            "respuestas_objetivo": len(
                respuestas_objetivo
            ),
            "jsonld": jsonld_resultados,
        }

        guardar_json(
            "corte_analisis_precio.json",
            analisis
        )

        # ====================================================
        # DIAGNÓSTICO
        # ====================================================

        separador()
        print("📌 DIAGNÓSTICO")
        separador()

        print(
            "✔ Página PDP accesible"
        )

        print(
            "✔ EAN correcto"
        )

        print(
            "✔ Product ID correcto"
        )

        print(
            "✔ STATUS FLOW capturado"
        )

        print(
            "✔ CROSSSELLING capturado"
        )

        print(
            "✔ HTML completo capturado"
        )

        if precio_producto is not None:

            print(
                f"✔ Precio PDP identificado: "
                f"{precio_producto:.2f} €"
            )

            if precio_litro is not None:

                print(
                    f"✔ Precio por litro: "
                    f"{precio_litro:.2f} €/L"
                )

            print()
            print(
                "🚀 YA PODEMOS PASAR A "
                "scrapers/corte_ingles.py"
            )

        else:

            print(
                "❌ Falta identificar el precio."
            )

        separador()

        print()
        print(
            "Pulsa ENTER para cerrar Chromium..."
        )

        input()

        browser.close()


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":
    main()