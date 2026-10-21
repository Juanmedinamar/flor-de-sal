from playwright.sync_api import sync_playwright
import time

URL = "https://www.hipercor.es/supermercado/marcas/canasta/supermercado/bebidas/vinos/vinos-generosos/olorosos/canasta-cream-vino-oloroso-dulce-con-d-o-jerez-xeres-sherry-botella-75-cl/8410028030903/p"

with sync_playwright() as p:

    print("🌐 Abriendo Hipercor...")

    browser = p.chromium.launch(
        headless=False
    )

    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        locale="es-ES"
    )

    page = context.new_page()

    # ---------------------------------------------------------
    # CONSOLA
    # ---------------------------------------------------------

    def consola(msg):
        try:
            texto = msg.text
            if texto:
                print(f"[CONSOLE] {msg.type}: {texto[:500]}")
        except:
            pass

    page.on("console", consola)

    # ---------------------------------------------------------
    # ERRORES JAVASCRIPT
    # ---------------------------------------------------------

    def error_js(error):
        try:
            print("[JS ERROR]", error)
        except:
            pass

    page.on("pageerror", error_js)

    # ---------------------------------------------------------
    # PETICIONES
    # ---------------------------------------------------------

    contador = 0

    def request(req):
        

        url = req.url.lower()

        interesantes = [
            "api",
            "product",
            "producto",
            "price",
            "precio",
            "offer",
            "oferta",
            "stock",
            "availability",
            "catalog",
            "search",
            "pdp",
            "commerce",
            "graphql",
            "8410028030903"
        ]

        if any(x in url for x in interesantes):
            print("\n>>> REQUEST")
            print(req.method, req.resource_type)
            print(req.url[:1000])

    page.on("request", request)

    # ---------------------------------------------------------
    # RESPUESTAS
    # ---------------------------------------------------------

    def response(resp):

        url = resp.url.lower()

        interesantes = [
            "api",
            "product",
            "producto",
            "price",
            "precio",
            "offer",
            "oferta",
            "stock",
            "availability",
            "catalog",
            "search",
            "pdp",
            "commerce",
            "graphql",
            "8410028030903"
        ]

        if any(x in url for x in interesantes):

            print("\n<<< RESPONSE")
            print(resp.status, resp.request.method, resp.request.resource_type)
            print(resp.url[:1000])

            # Si parece JSON, intentamos leerlo
            try:
                ct = resp.headers.get("content-type", "")

                if "json" in ct.lower():
                    texto = resp.text()

                    print("CONTENT-TYPE:", ct)
                    print("JSON LENGTH:", len(texto))
                    print(texto[:3000])

            except Exception as e:
                print("No se pudo leer respuesta:", e)

    page.on("response", response)

    # ---------------------------------------------------------
    # ABRIR
    # ---------------------------------------------------------

    try:

        page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

    except Exception as e:
        print("ERROR GOTO:", e)

    print("\n⏳ Esperando 20 segundos...")
    page.wait_for_timeout(20000)

    print("\n========================================")
    print("RESULTADO")
    print("========================================")

    print("URL:", page.url)
    print("TITLE:", page.title())

    try:
        texto = page.locator("body").inner_text()

        print("\n--- TEXTO VISIBLE ---")
        print(texto[:5000])

    except Exception as e:
        print("Error leyendo body:", e)

    # ---------------------------------------------------------
    # GUARDAR HTML
    # ---------------------------------------------------------

    try:

        html = page.content()

        with open(
            "hipercor_paso2.html",
            "w",
            encoding="utf-8"
        ) as f:
            f.write(html)

        print("\nHTML guardado:")
        print("hipercor_paso2.html")
        print("Tamaño:", len(html))

    except Exception as e:
        print("Error guardando HTML:", e)

    # ---------------------------------------------------------
    # SCREENSHOT
    # ---------------------------------------------------------

    try:
        page.screenshot(
            path="hipercor_paso2.png",
            full_page=True
        )

        print("Screenshot guardado: hipercor_paso2.png")

    except Exception as e:
        print("Error screenshot:", e)

    print("\n========================================")
    print("NO CIERRES EL NAVEGADOR TODAVÍA")
    print("Pulsa ENTER aquí cuando hayas visto la página")
    print("========================================")

    input()

    browser.close()