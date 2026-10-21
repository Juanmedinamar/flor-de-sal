import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

URL = "https://www.vinissimus.com/es/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

print("=" * 80)
print("🍷 INVESTIGANDO JAVASCRIPT DEL BUSCADOR VINISSIMUS")
print("=" * 80)

respuesta = requests.get(
    URL,
    headers=HEADERS,
    timeout=30,
)

print("HTTP:", respuesta.status_code)
print("HTML:", len(respuesta.text), "caracteres")

soup = BeautifulSoup(respuesta.text, "html.parser")

print()
print("========== ARCHIVOS JAVASCRIPT ==========")

scripts = []

for script in soup.find_all("script", src=True):

    src = script.get("src")

    if src:
        src_completo = urljoin(URL, src)
        scripts.append(src_completo)

        print()
        print(src_completo)

print()
print("TOTAL SCRIPTS:", len(scripts))

print()
print("========== BUSCANDO 'SEARCH' EN JAVASCRIPT ==========")

encontrados = 0

for i, script_url in enumerate(scripts, 1):

    try:

        r = requests.get(
            script_url,
            headers=HEADERS,
            timeout=30,
        )

        texto = r.text

        texto_lower = texto.lower()

        palabras = [
            "search-result",
            "search-form",
            "input-text search",
            "buscar vino",
            "search?",
        ]

        coincidencias = [
            palabra
            for palabra in palabras
            if palabra in texto_lower
        ]

        if coincidencias:

            encontrados += 1

            print()
            print("--------------------------------------------------")
            print("SCRIPT:", i)
            print("URL:", script_url)
            print("TAMAÑO:", len(texto))
            print("COINCIDENCIAS:", coincidencias)
            print("--------------------------------------------------")

            for palabra in coincidencias:

                posicion = texto_lower.find(palabra)

                print()
                print(">>>", palabra)

                print(
                    texto[
                        max(0, posicion - 1500):
                        posicion + 4000
                    ]
                )

    except Exception as e:

        print()
        print("ERROR SCRIPT:", script_url)
        print(type(e).__name__, ":", e)

print()
print("=" * 80)
print("SCRIPTS CON COINCIDENCIAS:", encontrados)
print("=" * 80)