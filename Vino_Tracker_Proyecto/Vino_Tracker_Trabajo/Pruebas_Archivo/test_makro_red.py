from playwright.sync_api import sync_playwright

URL = "https://www.makro.es/"
BUSQUEDA = "Tío Pepe"

print("=" * 80)
print("🔎 MAKRO - CAPTURA DE RED")
print("=" * 80)

with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=False
    )

    context = browser.new_context(
        locale="es-ES",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/151.0.0.0 Safari/537.36"
        )
    )

    page = context.new_page()

    # ============================================================
    # CAPTURA DE REQUESTS
    # ============================================================

    def request_handler(request):
        print()
        print("🚀 REQUEST")
        print("-" * 80)
        print(request.method)
        print(request.url)

        if request.post_data:
            print()
            print("POST DATA:")
            print(request.post_data[:3000])

    # ============================================================
    # CAPTURA DE RESPONSES
    # ============================================================

    def response_handler(response):

        url = response.url

        print()
        print("📥 RESPONSE")
        print("-" * 80)
        print(response.status)
        print(url)

        try:

            texto = response.text()

            texto_lower = texto.lower()

            palabras_detectar = [
                "tío pepe",
                "tio pepe",
                "8410023000031",
                "5,79",
                "5.79"
            ]

            if any(palabra in texto_lower for palabra in palabras_detectar):

                print()
                print("🎯🎯🎯 PRODUCTO DETECTADO EN RESPONSE 🎯🎯🎯")
                print()

                print(texto[:20000])

                with open(
                    "makro_producto_response.txt",
                    "w",
                    encoding="utf-8"
                ) as f:
                    f.write(texto)

        except Exception:
            pass

    page.on("request", request_handler)
    page.on("response", response_handler)

    # ============================================================
    # ABRIR MAKRO
    # ============================================================

    print()
    print("🌐 Abriendo Makro...")

    page.goto(
        URL,
        wait_until="domcontentloaded",
        timeout=60000
    )

    print()
    print("URL inicial:")
    print(page.url)

    print()
    print("⏳ Esperando 10 segundos...")

    page.wait_for_timeout(10000)

    # ============================================================
    # COOKIES
    # ============================================================

    print()
    print("=" * 80)
    print("🍪 COMPROBANDO COOKIES")
    print("=" * 80)

    # Buscamos botones habituales de consentimiento
    selectores_cookies = [
        "button:has-text('Aceptar')",
        "button:has-text('Aceptar todas')",
        "button:has-text('Aceptar todo')",
        "button:has-text('Rechazar')",
        "button:has-text('Rechazar todas')",
        "button:has-text('Continuar')",
        "[class*='consent'] button",
        "[class*='cookie'] button"
    ]

    cookie_resuelto = False

    for selector in selectores_cookies:

        try:

            loc = page.locator(selector)

            cantidad = loc.count()

            if cantidad > 0:

                print()
                print("Botón encontrado:", selector)
                print("Cantidad:", cantidad)

                # Intentamos el primero visible
                for i in range(min(cantidad, 5)):

                    boton = loc.nth(i)

                    try:

                        if boton.is_visible():

                            print("👆 Botón visible encontrado")

                            print("Texto:")
                            print(boton.inner_text())

                            boton.click(
                                force=True,
                                timeout=5000
                            )

                            print("✅ Consentimiento resuelto")

                            cookie_resuelto = True

                            page.wait_for_timeout(2000)

                            break

                    except Exception as e:
                        print("⚠️ No se pudo pulsar:", e)

                if cookie_resuelto:
                    break

        except Exception:
            pass

    if not cookie_resuelto:

        print()
        print("ℹ️ No se ha encontrado botón de cookies.")
        print("Intentaremos continuar.")

    # ============================================================
    # COMPROBAR BUSCADOR
    # ============================================================

    print()
    print("=" * 80)
    print("🔎 BUSCANDO EL INPUT")
    print("=" * 80)

    buscadores = [
        "#site-header-input",
        "input[name='textBoxSearch']",
        "input[placeholder*='Buscar']",
        "input[type='search']"
    ]

    buscador = None

    for selector in buscadores:

        try:

            loc = page.locator(selector).first

            if loc.count() > 0:

                print()
                print("Encontrado:", selector)

                buscador = loc

                break

        except Exception:
            pass

    if buscador is None:

        print()
        print("❌ No se encontró el buscador.")

        print()
        print("URL:")
        print(page.url)

        page.screenshot(
            path="makro_sin_buscador.png",
            full_page=True
        )

        input("\nPulsa ENTER para cerrar...")

        browser.close()

        raise SystemExit

    # ============================================================
    # COMPROBAR VISIBILIDAD
    # ============================================================

    print()
    print("👁️ Comprobando buscador...")

    try:

        print("Visible:", buscador.is_visible())
        print("Habilitado:", buscador.is_enabled())

    except Exception as e:

        print("⚠️ Error:", e)

    # ============================================================
    # ESCRIBIR
    # ============================================================

    print()
    print("=" * 80)
    print("✍️ ESCRIBIENDO PRODUCTO")
    print("=" * 80)

    print()
    print("Producto:")
    print(BUSQUEDA)

    try:

        # No necesitamos hacer click.
        # fill() puede escribir directamente en el input.

        buscador.fill(
            BUSQUEDA,
            timeout=10000
        )

        print()
        print("✅ Texto escrito correctamente")

    except Exception as e:

        print()
        print("❌ Error escribiendo en el buscador:")
        print(e)

        page.screenshot(
            path="makro_error_buscador.png",
            full_page=True
        )

        input("\nPulsa ENTER para cerrar...")

        browser.close()

        raise SystemExit

    # ============================================================
    # ESPERAR
    # ============================================================

    print()
    print("⏳ Esperando 5 segundos sin lanzar búsqueda...")

    page.wait_for_timeout(5000)

    print()
    print("URL actual:")
    print(page.url)

    print()
    print("📸 Capturando pantalla...")

    page.screenshot(
        path="makro_tio_pepe_antes_enter.png",
        full_page=True
    )

    # ============================================================
    # LANZAR BÚSQUEDA
    # ============================================================

    print()
    print("=" * 80)
    print("🚀 LANZANDO BÚSQUEDA CON ENTER")
    print("=" * 80)

    try:

        buscador.press(
            "Enter",
            timeout=10000
        )

        print()
        print("✅ ENTER enviado")

    except Exception as e:

        print()
        print("❌ Error al pulsar ENTER:")
        print(e)

    # ============================================================
    # ESPERAR RESULTADOS
    # ============================================================

    print()
    print("⏳ Esperando 12 segundos...")

    page.wait_for_timeout(12000)

    # ============================================================
    # RESULTADO
    # ============================================================

    print()
    print("=" * 80)
    print("📄 RESULTADO")
    print("=" * 80)

    print()
    print("URL FINAL:")
    print(page.url)

    print()
    print("TÍTULO:")
    print(page.title())

    try:

        texto = page.locator("body").inner_text()

        print()
        print("TEXTO VISIBLE:")
        print("-" * 80)

        print(texto[:15000])

        with open(
            "makro_resultado.txt",
            "w",
            encoding="utf-8"
        ) as f:

            f.write(texto)

    except Exception as e:

        print()
        print("⚠️ No se pudo leer el body:")
        print(e)

    # ============================================================
    # CAPTURA FINAL
    # ============================================================

    page.screenshot(
        path="makro_tio_pepe_despues_enter.png",
        full_page=True
    )

    print()
    print("📸 Capturas guardadas.")

    print()
    print("=" * 80)
    print("🏁 PRUEBA TERMINADA")
    print("=" * 80)

    input("\nPulsa ENTER para cerrar Chromium...")

    browser.close()