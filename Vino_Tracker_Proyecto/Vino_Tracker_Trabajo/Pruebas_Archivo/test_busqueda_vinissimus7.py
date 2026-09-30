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
print("🍷 BUSQUEDA VINISSIMUS - CANASTA")
print("=" * 80)

params = {
    "name": "Canasta",
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
print("CANASTA EN HTML:", "canasta" in respuesta.text.lower())
print("CANASTA EN TEXTO:", "canasta" in texto.lower())

print()
print("=" * 80)
print("H2 ENCONTRADOS")
print("=" * 80)

h2s = soup.find_all("h2")

print("TOTAL H2:", len(h2s))

for h2 in h2s:
    print("-", repr(h2.get_text(" ", strip=True)))


print()
print("=" * 80)
print("PRODUCT-LIST-ITEM")
print("=" * 80)

bloques = soup.select("div.product-list-item")

print("TOTAL BLOQUES:", len(bloques))

for bloque in bloques:

    contenido = bloque.get_text(" ", strip=True)

    print()
    print("PRODUCTO:", contenido[:500])

    if "canasta" in contenido.lower():

        print()
        print("🎯🎯🎯 CANASTA ENCONTRADA 🎯🎯🎯")
        print(contenido)

        enlace = bloque.find("a", href=True)

        if enlace:
            print("HREF:", enlace.get("href"))

        print()
        print("========== HTML DEL PRODUCTO ==========")
        print(str(bloque)[:12000])


print()
print("=" * 80)
print("TEXTOS RELACIONADOS CON CANASTA")
print("=" * 80)

palabras = [
    "canasta",
    "no disponible",
    "no encontramos",
    "resultados",
    "resultado",
]

for palabra in palabras:

    print()
    print("BUSCANDO:", palabra)

    posicion = texto.lower().find(palabra)

    if posicion >= 0:

        inicio = max(0, posicion - 500)
        fin = min(len(texto), posicion + 1500)

        print(texto[inicio:fin])

    else:
        print("NO ENCONTRADO")


print()
print("=" * 80)
print("FIN")
print("=" * 80)