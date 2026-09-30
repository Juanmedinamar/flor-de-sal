import requests
from bs4 import BeautifulSoup

URL = "https://www.vinissimus.com/es/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

respuesta = requests.get(
    URL,
    headers=HEADERS,
    timeout=30,
)

soup = BeautifulSoup(respuesta.text, "html.parser")

print("=" * 80)
print("🍷 INVESTIGACIÓN DEL BUSCADOR VINISSIMUS")
print("=" * 80)

# ---------------------------------------------------------
# FORMULARIO
# ---------------------------------------------------------

print()
print("========== FORMULARIO DE BÚSQUEDA ==========")

for formulario in soup.find_all("form"):

    print("FORM:", formulario)

# ---------------------------------------------------------
# INPUT
# ---------------------------------------------------------

print()
print("========== INPUTS ==========")

for inp in soup.find_all("input"):

    print(
        "name =", repr(inp.get("name")),
        "| type =", repr(inp.get("type")),
        "| value =", repr(inp.get("value")),
        "| placeholder =", repr(inp.get("placeholder")),
        "| id =", repr(inp.get("id")),
        "| class =", repr(inp.get("class")),
    )

# ---------------------------------------------------------
# ELEMENTOS CON SEARCH
# ---------------------------------------------------------

print()
print("========== ELEMENTOS CON 'SEARCH' ==========")

for elemento in soup.find_all(
    lambda tag: any(
        "search" in str(valor).lower()
        for valor in tag.attrs.values()
    )
):

    print()
    print("TAG:", elemento.name)
    print("ATTRS:", elemento.attrs)
    print("TEXTO:", repr(elemento.get_text(" ", strip=True)[:300]))

# ---------------------------------------------------------
# SCRIPTS
# ---------------------------------------------------------

print()
print("========== SCRIPTS CON 'search-result' ==========")

contador = 0

for script in soup.find_all("script"):

    texto = script.get_text()

    if "search-result" in texto.lower():

        contador += 1

        print()
        print("----- SCRIPT", contador, "-----")

        posicion = texto.lower().find("search-result")

        print(
            texto[
                max(0, posicion - 2000):
                posicion + 5000
            ]
        )

print()
print("TOTAL SCRIPTS:", contador)

# ---------------------------------------------------------
# SCRIPTS CON 'Buscar vino'
# ---------------------------------------------------------

print()
print("========== SCRIPTS CON 'Buscar vino' ==========")

contador = 0

for script in soup.find_all("script"):

    texto = script.get_text()

    if "Buscar vino" in texto:

        contador += 1

        print()
        print("----- SCRIPT", contador, "-----")
        print(texto[:8000])

print()
print("=" * 80)
print("FIN")
print("=" * 80)