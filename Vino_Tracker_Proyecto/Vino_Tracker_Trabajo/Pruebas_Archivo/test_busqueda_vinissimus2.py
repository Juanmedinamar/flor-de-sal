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

print("=" * 80)
print("🍷 INVESTIGANDO BÚSQUEDA VINISSIMUS")
print("=" * 80)

respuesta = requests.get(
    URL,
    headers=HEADERS,
    timeout=30,
)

print("HTTP:", respuesta.status_code)
print("URL:", respuesta.url)
print("HTML:", len(respuesta.text), "caracteres")

soup = BeautifulSoup(respuesta.text, "html.parser")

print()
print("========== FORMULARIOS ==========")

for formulario in soup.find_all("form"):

    print()
    print("FORMULARIO:")

    print("ACTION:", formulario.get("action"))
    print("METHOD:", formulario.get("method"))

    for elemento in formulario.find_all(["input", "button"]):

        print(
            " ",
            elemento.name,
            "name=", elemento.get("name"),
            "type=", elemento.get("type"),
            "value=", elemento.get("value"),
            "placeholder=", elemento.get("placeholder"),
        )

print()
print("========== ENLACES CON SEARCH ==========")

for a in soup.find_all("a", href=True):

    href = a.get("href")
    texto = a.get_text(" ", strip=True)

    if "search" in href.lower() or "buscar" in href.lower():

        print(
            "TEXTO:", repr(texto),
            "| HREF:", href
        )

print()
print("========== JAVASCRIPT RELACIONADO CON SEARCH ==========")

for script in soup.find_all("script"):

    texto = script.get_text()

    if "search" in texto.lower():

        print()
        print(texto[:3000])

print()
print("=" * 80)
print("FIN")
print("=" * 80)