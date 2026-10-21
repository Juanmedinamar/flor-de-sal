import asyncio
import re
from playwright.async_api import async_playwright


URL_BUSQUEDA = (
    "https://www.hipercor.es/supermercado/"
    "buscar?question=canasta&catalog=supermercado&stype=text_box"
)


async def main():

    print("=" * 90)
    print("🍷 HIPERCOR - EXTRACCIÓN DESDE RESULTADOS DE BÚSQUEDA")
    print("=" * 90)

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=False
        )

        context = await browser.new_context(
            locale="es-ES",
            viewport={"width": 1440, "height": 900},
        )

        page = await context.new_page()

        print("\n🌐 Abriendo búsqueda...")
        print(URL_BUSQUEDA)

        response = await page.goto(
            URL_BUSQUEDA,
            wait_until="domcontentloaded",
            timeout=60000
        )

        print("\nSTATUS:", response.status if response else "N/A")
        print("URL:", page.url)

        print("\n⏳ Esperando producto...")

        try:
            await page.get_by_text(
                "Vino oloroso dulce DO Jerez-Xérès-Sherry CANASTA",
                exact=False
            ).wait_for(timeout=30000)

            print("✅ Producto localizado")

        except Exception:
            print("⚠️ No apareció el texto exacto")
            print("Continuamos con el análisis del DOM...")

        await page.wait_for_timeout(5000)

        # ---------------------------------------------------------
        # TEXTO VISIBLE
        # ---------------------------------------------------------

        texto = await page.locator("body").inner_text()

        print("\n" + "=" * 90)
        print("📄 TEXTO VISIBLE")
        print("=" * 90)

        print(texto[:5000])

        # ---------------------------------------------------------
        # PRECIO
        # ---------------------------------------------------------

        print("\n" + "=" * 90)
        print("💰 BUSCANDO PRECIO")
        print("=" * 90)

        precios = re.findall(
            r'(\d{1,3}[,.]\d{2})\s*€',
            texto
        )

        if precios:
            print("Precios encontrados:")

            for precio in precios:
                print("  💶", precio, "€")

        else:
            print("❌ No se encontraron precios")

        # ---------------------------------------------------------
        # PRECIO POR LITRO
        # ---------------------------------------------------------

        litros = re.findall(
            r'(\d{1,3}[,.]\d{2})\s*€\s*/\s*Litro',
            texto,
            re.IGNORECASE
        )

        print("\nPrecio por litro:")

        if litros:
            for precio in litros:
                print("  📏", precio, "€/Litro")
        else:
            print("❌ No encontrado")

        # ---------------------------------------------------------
        # BUSCAR PRODUCTO
        # ---------------------------------------------------------

        print("\n" + "=" * 90)
        print("🍷 BUSCANDO PRODUCTO")
        print("=" * 90)

        elementos = page.locator("text=/CANASTA/i")

        count = await elementos.count()

        print("Elementos encontrados:", count)

        for i in range(min(count, 10)):

            try:
                elemento = elementos.nth(i)

                txt = await elemento.inner_text()

                if txt.strip():
                    print(f"\n--- ELEMENTO {i} ---")
                    print(txt[:1000])

            except Exception:
                pass

        # ---------------------------------------------------------
        # ENLACES
        # ---------------------------------------------------------

        print("\n" + "=" * 90)
        print("🔗 ENLACES DE CANASTA")
        print("=" * 90)

        enlaces = page.locator("a")

        encontrados = 0

        for i in range(await enlaces.count()):

            try:

                a = enlaces.nth(i)

                href = await a.get_attribute("href")

                if not href:
                    continue

                texto_a = await a.inner_text()

                if "canasta" in (
                    texto_a + " " + href
                ).lower():

                    print("\nTEXTO:", repr(texto_a))
                    print("URL  :", href)

                    encontrados += 1

            except Exception:
                pass

        print("\nTotal enlaces:", encontrados)

        # ---------------------------------------------------------
        # GUARDAR HTML
        # ---------------------------------------------------------

        html = await page.content()

        with open(
            "hipercor_busqueda_scraper.html",
            "w",
            encoding="utf-8"
        ) as f:

            f.write(html)

        print("\n💾 HTML guardado:")
        print("hipercor_busqueda_scraper.html")

        # ---------------------------------------------------------
        # SCREENSHOT
        # ---------------------------------------------------------

        await page.screenshot(
            path="hipercor_busqueda_scraper.png",
            full_page=True
        )

        print("📸 Screenshot:")
        print("hipercor_busqueda_scraper.png")

        print("\n" + "=" * 90)
        print("🏁 FIN")
        print("=" * 90)

        print("\n🛑 Navegador abierto.")
        input("Pulsa ENTER para cerrar...")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())