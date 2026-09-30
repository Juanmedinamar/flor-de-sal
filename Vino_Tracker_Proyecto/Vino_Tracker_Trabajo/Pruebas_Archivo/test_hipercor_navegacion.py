import asyncio
from playwright.async_api import async_playwright

URL = "https://www.hipercor.es/supermercado/marcas/canasta/supermercado/bebidas/vinos/vinos-generosos/olorosos/canasta-cream-vino-oloroso-dulce-con-d-o-jerez-xeres-sherry/botella-75-cl/8410028030903/p"


async def main():

    print("=" * 90)
    print("🍷 HIPERCOR - PRUEBA DE NAVEGACIÓN")
    print("=" * 90)

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--start-maximized",
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="es-ES",
            timezone_id="Europe/Madrid",
        )

        page = await context.new_page()

        print("\n🌐 Abriendo página...")
        print(URL)

        try:

            response = await page.goto(
                URL,
                wait_until="domcontentloaded",
                timeout=60000
            )

            print("\nSTATUS:", response.status if response else "SIN RESPUESTA")
            print("URL ACTUAL:", page.url)
            print("TÍTULO:", await page.title())

        except Exception as e:

            print("\n❌ ERROR AL ABRIR:")
            print(type(e).__name__)
            print(e)

        print("\n⏳ Esperando 10 segundos...")
        await page.wait_for_timeout(10000)

        print("\nURL DESPUÉS DE 10 SEGUNDOS:")
        print(page.url)

        print("\nTÍTULO:")
        print(await page.title())

        # --------------------------------------------------
        # Buscar textos importantes en la página
        # --------------------------------------------------

        texto = await page.locator("body").inner_text()

        print("\n" + "=" * 90)
        print("🔎 COMPROBACIONES")
        print("=" * 90)

        palabras = [
            "Canasta",
            "Cream",
            "8410028030903",
            "€",
            "precio",
            "añadir",
            "carrito",
            "producto",
            "captcha",
            "verifica",
            "robot",
        ]

        for palabra in palabras:

            if palabra.lower() in texto.lower():
                print(f"✅ {palabra}")
            else:
                print(f"❌ {palabra}")

        print("\n" + "=" * 90)
        print("📄 PRIMEROS 3000 CARACTERES")
        print("=" * 90)

        print(texto[:3000])

        # --------------------------------------------------
        # Guardamos screenshot
        # --------------------------------------------------

        await page.screenshot(
            path="hipercor_prueba.png",
            full_page=True
        )

        print("\n📸 Screenshot guardado:")
        print("hipercor_prueba.png")

        # --------------------------------------------------
        # Dejamos el navegador abierto
        # --------------------------------------------------

        print("\n" + "=" * 90)
        print("🛑 NAVEGADOR ABIERTO")
        print("=" * 90)

        input("\nPulsa ENTER aquí para cerrar...")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())