import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

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
print("🍷 INVESTIGACIÓN VINISSIMUS - ENLACES CANASTA")
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


# -------------------------------------------------------------------
# 1. BUSCAR TODOS LOS ENLACES QUE CONTENGAN "CANASTA"
# -------------------------------------------------------------------

print()
print("=" * 80)
print("🔎 ENLACES QUE CONTIENEN 'CANASTA'")
print("=" * 80)

enlaces = soup.find_all("a", href=True)

contador = 0

for enlace in enlaces:

    texto = enlace.get_text(" ", strip=True)
    href = enlace.get("href", "")

    combinado = (texto + " " + href).lower()

    if "canasta" in combinado:

        contador += 1

        print()
        print(f"--- ENLACE {contador} ---")
        print("TEXTO:", repr(texto))
        print("HREF:", href)
        print("URL:", urljoin(URL, href))


print()
print("TOTAL ENLACES CON CANASTA:", contador)


# -------------------------------------------------------------------
# 2. BUSCAR "CANASTA" DIRECTAMENTE EN EL HTML
# -------------------------------------------------------------------

print()
print("=" * 80)
print("🔎 CONTEXTO RAW HTML DE 'CANASTA'")
print("=" * 80)

html_lower = respuesta.text.lower()

posiciones = []
inicio_busqueda = 0

while True:

    posicion = html_lower.find("canasta", inicio_busqueda)

    if posicion == -1:
        break

    posiciones.append(posicion)
    inicio_busqueda = posicion + 7


print("TOTAL APARICIONES EN HTML:", len(posiciones))

for numero, posicion in enumerate(posiciones[:20], start=1):

    inicio = max(0, posicion - 300)
    fin = min(len(respuesta.text), posicion + 700)

    print()
    print(f"--- APARICIÓN {numero} ---")
    print(respuesta.text[inicio:fin])


# -------------------------------------------------------------------
# 3. BUSCAR PRODUCTOS CUYO HREF TENGA CANASTA
# -------------------------------------------------------------------

print()
print("=" * 80)
print("🍷 PRODUCTOS CON HREF 'CANASTA'")
print("=" * 80)

productos = soup.select("div.product-list-item")

encontrados = 0

for producto in productos:

    enlaces_producto = producto.find_all("a", href=True)

    for enlace in enlaces_producto:

        href = enlace.get("href", "")

        if "canasta" in href.lower():

            encontrados += 1

            print()
            print("🎯 PRODUCTO ENCONTRADO")
            print("TEXTO:", producto.get_text(" ", strip=True))
            print("HREF:", href)
            print("URL:", urljoin(URL, href))
            print()
            print("HTML:")
            print(str(producto)[:12000])


print()
print("TOTAL PRODUCTOS:", encontrados)


print()
print("=" * 80)
print("FIN")
print("=" * 80)