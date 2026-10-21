from playwright.sync_api import sync_playwright


URL = "https://www.carrefour.es/supermercado/brandy-de-jerez-gran-duque-d-alba-solera-gran-reserva-70-cl/R-520663025/p"


with sync_playwright() as p:

    print("=" * 80)
    print("🌐 PRUEBA DIRECTA CARREFOUR")
    print("=" * 80)

    browser = p.chromium.launch(
        headless=False
    )

    page = browser.new_page(
        viewport={"width": 1400, "height": 900}
    )

    print()
    print("🌐 Abriendo página directa...")
    print(URL)

    page.goto(
        URL,
        wait_until="domcontentloaded",
        timeout=60000
    )

    page.wait_for_timeout(5000)

    print()
    print("📄 TÍTULO:")
    print(page.title())

    print()
    print("🔗 URL FINAL:")
    print(page.url)

    print()
    print("=" * 80)
    print("🔎 BUSCANDO PRODUCTO")
    print("=" * 80)

    texto = page.locator("body").inner_text()

    print()
    print("¿Aparece 'Gran Duque'?:",
          "gran duque" in texto.lower())

    print("¿Aparece '28,80'?:",
          "28,80" in texto)

    print("¿Aparece '28.80'?:",
          "28.80" in texto)

    print("¿Aparece '70 cl'?:",
          "70 cl" in texto.lower())

    print()
    print("📄 TEXTO DE LA PÁGINA")
    print("-" * 80)

    print(texto[:12000])

    print("-" * 80)

    input("\nPulsa ENTER para cerrar el navegador...")

    browser.close()