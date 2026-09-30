from playwright.sync_api import sync_playwright
import json
import re

URL = (
    "https://www.elcorteingles.es/supermercado/"
    "B001018720300344-canasta-vino-oloroso-dulce-do-jerez-"
    "xeres-sherry-botella-75-cl/"
)

PRODUCT_ID = "B001018720300344"
EAN = "8410028030903"

print("🚀 Iniciando Chromium...")

with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=False
    )

    page = browser.new_page(
        locale="es-ES"
    )

    respuestas = []

    def capturar(response):

        url = response.url

        # Nos interesan las APIs de El Corte Inglés
        if "elcorteingles.es/api/" not in url:
            return

        try:
            texto = response.text()
        except Exception:
            texto = ""

        datos = {
            "url": url,
            "status": response.status,
            "content_type": response.headers.get(
                "content-type", ""
            ),
            "texto": texto
        }

        respuestas.append(datos)

        print("\n" + "=" * 120)
        print("API DETECTADA")
        print("STATUS:", response.status)
        print("URL:", url)

        # Detectamos especialmente respuestas
        # relacionadas con Canasta
        if (
            PRODUCT_ID in texto
            or EAN in texto
            or "priceSpecification" in texto
            or '"price"' in texto
            or '"salePrice"' in texto
        ):

            print("🔥🔥🔥 POSIBLEMENTE IMPORTANTE 🔥🔥🔥")

            print(
                texto[:10000]
            )

    page.on("response", capturar)

    print("🌐 Abriendo El Corte Inglés...")

    page.goto(
        URL,
        wait_until="domcontentloaded",
        timeout=60000
    )

    print(
        "\n⏳ Esperando 20 segundos..."
    )

    page.wait_for_timeout(20000)

    # ---------------------------------------------------------
    # Guardamos todas las APIs encontradas
    # ---------------------------------------------------------

    print("\n")
    print("=" * 120)
    print("📊 RESUMEN DE APIs")
    print("=" * 120)

    for i, r in enumerate(respuestas, 1):

        print(
            f"{i:03d} | "
            f"{r['status']} | "
            f"{r['url']}"
        )

    # ---------------------------------------------------------
    # Guardar resultados en archivo
    # ---------------------------------------------------------

    with open(
        "apis_corte_ingles.txt",
        "w",
        encoding="utf-8"
    ) as f:

        for i, r in enumerate(respuestas, 1):

            f.write("\n")
            f.write("=" * 120)
            f.write("\n")

            f.write(
                f"API #{i}\n"
            )

            f.write(
                f"STATUS: {r['status']}\n"
            )

            f.write(
                f"CONTENT-TYPE: {r['content_type']}\n"
            )

            f.write(
                f"URL: {r['url']}\n"
            )

            f.write("\nRESPUESTA:\n")

            f.write(
                r["texto"]
            )

            f.write("\n")

    print("\n")
    print("=" * 120)
    print("💾 APIs guardadas en:")
    print("apis_corte_ingles.txt")
    print("=" * 120)

    input(
        "\nPulsa ENTER para cerrar Chromium..."
    )

    browser.close()

