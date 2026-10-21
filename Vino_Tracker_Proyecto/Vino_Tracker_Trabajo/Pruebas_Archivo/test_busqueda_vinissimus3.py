import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

BUSQUEDA = "Cream sherry"

URL = (
    "https://www.vinissimus.com/es/search-result/"
    "?type=%2Fvi"
    "&search=" + quote(BUSQUEDA)
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
print("========== TEXTO DE LA PÁGINA ==========")

texto = soup.get_text(" ", strip=True)

print("CREAM:", "cream" in texto.lower())
print("CANASTA:", "canasta" in texto.lower())
print("SHERRY:", "sherry" in texto.lower())

print()
print("========== PRODUCTOS ==========")

encontrados = []

for elemento in soup.select("a[href]"):

    texto_elemento = elemento.get_text(" ", strip=True)

    if "canasta" in texto_elemento.lower() or "cream" in texto_elemento.lower():

        encontrados.append(
            (
                texto_elemento,
                elemento.get("href")
            )
        )

for texto_elemento, href in encontrados:

    print()
    print("🎯 RESULTADO")
    print("TEXTO:", repr(texto_elemento))
    print("HREF:", href)

print()
print("TOTAL:", len(encontrados))

print()
print("========== H2 ==========")

for h2 in soup.find_all("h2"):

    texto_h2 = h2.get_text(" ", strip=True)

    if texto_h2:
        print("-", repr(texto_h2))

print()
print("=" * 80)
print("FIN")
print("=" * 80)