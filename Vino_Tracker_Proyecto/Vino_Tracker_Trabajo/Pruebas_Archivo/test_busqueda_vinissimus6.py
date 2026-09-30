import requests
from bs4 import BeautifulSoup

URL = "https://www.vinissimus.com/es/search-result/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

print("=" * 80)
print("🍷 BUSQUEDA REAL VINISSIMUS")
print("=" * 80)

params = {
    "name": "Canasta Cream",
    "notavailable": "true",
}

respuesta = requests.get(
    URL,
    params=params,
    headers=HEADERS,
    timeout=30,
)

print("HTTP:", respuesta.status_code)
print("URL FINAL:", respuesta.url)
print("HTML:", len(respuesta.text), "caracteres")

soup = BeautifulSoup(respuesta.text, "html.parser")

texto = soup.get_text(" ", strip=True)

print()
print("CANASTA EN HTML:", "Canasta" in respuesta.text)
print("CANASTA EN TEXTO:", "canasta" in texto.lower())
print("CREAM EN TEXTO:", "cream" in texto.lower())

print()
print("========== H2 ==========")

h2s = soup.find_all("h2")

print("TOTAL H2:", len(h2s))

for h2 in h2s:

    nombre = h2.get_text(" ", strip=True)

    print("-", repr(nombre))

print()
print("========== PRODUCT-LIST-ITEM ==========")

bloques = soup.select("div.product-list-item")

print("TOTAL BLOQUES:", len(bloques))

for bloque in bloques:

    contenido = bloque.get_text(" ", strip=True)

    if "canasta" in contenido.lower():

        print()
        print("🎯 PRODUCTO ENCONTRADO")
        print(contenido)

        print()
        print("========== HTML ==========")
        print(str(bloque)[:10000])

print()
print("=" * 80)
print("FIN")
print("=" * 80)