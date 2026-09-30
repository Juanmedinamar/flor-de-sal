import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright


URL = (
    "https://www.hipercor.es/supermercado/"
    "marcas/canasta/supermercado/bebidas/vinos/"
    "vinos-generosos/olorosos/"
    "canasta-cream-vino-oloroso-dulce-con-d-o-jerez-xeres-sherry/"
    "botella-75-cl/8410028030903/p"
)


async def main():

    print("=" * 100)
    print("🍷 HIPERCOR - DETECTOR DE API DE PRODUCTO")
    print("=" * 100)

    respuestas = []

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=False
        )

        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="es-ES"
        )

        page = await context.new_page()

        async def capturar_response(response):

            request = response.request
            url = response.url
            method = request.method

            # Nos interesan especialmente XHR/FETCH
            if request.resource_type not in ["xhr", "fetch"]:
                return

            try:
                headers = await response.all_headers()
            except:
                headers = {}

            content_type = headers.get("content-type", "").lower()

            # Intentamos leer la respuesta
            try:
                body = await response.body()
                texto = body.decode("utf-8", errors="ignore")
            except Exception as e:
                texto = ""

            registro = {
                "method": method,
                "status": response.status,
                "resource_type": request.resource_type,
                "url": url,
                "content_type": content_type,
                "request_headers": await request.all_headers(),
                "request_post_data": request.post_data,
                "response_body": texto
            }

            respuestas.append(registro)

            # ============================================================
            # DETECTOR
            # ============================================================

            texto_busqueda = (
                url
                + " "
                + content_type
                + " "
                + texto[:50000]
            ).lower()

            pistas = [
                "8410028030903",
                "canasta",
                "price",
                "precio",
                "product",
                "sku",
                "ean",
                "barcode",
                "pvp",
                "amount",
                "offer",
                "availability",
                "stock",
                "catalog",
                "graphql"
            ]

            encontradas = [
                p for p in pistas
                if p in texto_busqueda
            ]

            # También nos interesan respuestas JSON
            es_json = (
                "json" in content_type
                or texto.strip().startswith("{")
                or texto.strip().startswith("[")
            )

            if encontradas or es_json:

                print()
                print("=" * 100)
                print("🔥 POSIBLE API DE PRODUCTO")
                print("=" * 100)

                print("METHOD :", method)
                print("STATUS :", response.status)
                print("TYPE   :", request.resource_type)
                print("URL    :", url)
                print("TYPE   :", content_type)

                if encontradas:
                    print("PISTAS :", ", ".join(encontradas))

                if request.post_data:
                    print()
                    print("📤 POST DATA:")
                    print(request.post_data[:3000])

                print()
                print("📥 RESPUESTA:")
                print(texto[:5000])

        page.on("response", capturar_response)

        print()
        print("🌐 Abriendo:")
        print(URL)
        print()

        await page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        print()
        print("⏳ Esperando 15 segundos...")
        await page.wait_for_timeout(15000)

        # ============================================================
        # SEGUNDO PASO:
        # hacer scroll para provocar carga diferida
        # ============================================================

        print()
        print("📜 Haciendo scroll...")

        await page.evaluate("""
            async () => {
                for (let y = 0; y < document.body.scrollHeight; y += 500) {
                    window.scrollTo(0, y);
                    await new Promise(r => setTimeout(r, 500));
                }
            }
        """)

        await page.wait_for_timeout(5000)

        # ============================================================
        # GUARDAR TODO
        # ============================================================

        Path("hipercor_api_completo.json").write_text(
            json.dumps(
                respuestas,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

        print()
        print("=" * 100)
        print("📊 RESULTADO")
        print("=" * 100)

        print("Total XHR/FETCH:", len(respuestas))

        print()
        print("💾 Guardado:")
        print("hipercor_api_completo.json")

        print()
        print("🛑 Navegador abierto.")
        print("Pulsa ENTER para cerrar.")

        input()

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())