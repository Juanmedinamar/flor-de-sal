import requests

url = "https://servicio-distribucion-hosteleria.makro.es/shop/search"

params = {
    "q": "Tío Pepe"
}

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
}

print("=" * 80)
print("🔎 PRUEBA ENDPOINT MAKRO")
print("=" * 80)

print()
print("URL:")
print(url)

response = requests.get(
    url,
    params=params,
    headers=headers,
    timeout=30
)

print()
print("STATUS:", response.status_code)
print("URL FINAL:", response.url)

print()
print("CONTENT-TYPE:")
print(response.headers.get("content-type"))

print()
print("TAMAÑO:")
print(len(response.text))

print()
print("=" * 80)
print("📄 RESPUESTA")
print("=" * 80)

print(response.text[:10000])

with open(
    "makro_endpoint_tio_pepe.html",
    "w",
    encoding="utf-8"
) as archivo:

    archivo.write(response.text)

print()
print("💾 Guardado:")
print("makro_endpoint_tio_pepe.html")