from playwright.sync_api import sync_playwright

URL = (
    "https://www.carrefour.es/"
    "canasta-cream-sherry-75cl-vino-generoso-"
    "espana-jerez-xeres-sherry-75-cl-195/"
    "8410028030903/p"
)

with sync_playwright() as p:

    print("🌐 Abriendo Carrefour con navegador visible...")

    browser = p.chromium.launch(
        headless=False
    )

    page = browser.new_page(
        viewport={
            "width": 1366,
            "height": 900
        }
    )

    page.goto(
        URL,
        wait_until="domcontentloaded",
        timeout=60000
    )

    print()
    print("Título inicial:", page.title())
    print("URL:", page.url)

    print()
    print("⏳ Tienes 30 segundos para comprobar el navegador...")

    page.wait_for_timeout(30000)

    print()
    print("Título final:", page.title())

    texto = page.locator("body").inner_text()

    print("Tamaño texto:", len(texto))
    print("Canasta Cream:", "Canasta Cream" in texto)
    print("EAN:", "8410028030903" in texto)

    browser.close()