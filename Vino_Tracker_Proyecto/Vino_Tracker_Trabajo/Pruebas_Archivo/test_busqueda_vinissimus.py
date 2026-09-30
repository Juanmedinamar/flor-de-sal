import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

BUSQUEDA = "Canasta Cream"

URL = (
    "https://www.vinissimus.com/es/buscar/"
    "?q=" + quote(BUSQUEDA)
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

print("=" * 80)
print("🍷 BÚSQUEDA VINISSIMUS")
print("=" * 80)

print("BUSCANDO:", BUSQUEDA)
print("URL:", URL)

respuesta = requests.get(
    URL,
    headers=HEADERS,
    timeout=30,
)

print()
print("HTTP:", respuesta.status_code)
print("URL FINAL:", respuesta.url)
print("HTML:", len(respuesta.text), "caracteres")

soup = BeautifulSoup(respuesta.text, "html.parser")

print()
print("========== RESULTADOS ==========")

encontrados = []

for elemento in soup.select("a[href]"):

    texto = elemento.get_text(" ", strip=True)

    if "canasta" in texto.lower():

        href = elemento.get("href")

        encontrados.append(
            (
                texto,
                href,
            )
        )

for texto, href in encontrados:

    print()
    print("🎯 PRODUCTO:")
    print("TEXTO:", repr(texto))
    print("HREF:", href)

print()
print("TOTAL ENCONTRADOS:", len(encontrados))

print()
print("========== H2 ==========")

for h2 in soup.find_all("h2"):

    texto = h2.get_text(" ", strip=True)

    print("-", repr(texto))

print()
print("=" * 80)
print("FIN")
print("=" * 80)