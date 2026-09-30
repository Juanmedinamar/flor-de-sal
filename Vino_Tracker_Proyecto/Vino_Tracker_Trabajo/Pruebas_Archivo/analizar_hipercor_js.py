import requests
import re
from pathlib import Path

print("=" * 100)
print("🍷 HIPERCOR - ANÁLISIS DEL JAVASCRIPT")
print("=" * 100)

BASE = "https://cdn.grupoelcorteingles.es/statics/front-msh3-food-hipercor/assets/javascripts/chunks/"

ARCHIVOS = [
    "index.CNr97dLu.js",
    "default_layout.DHIgY0w_.js",
    "promotional.action.composable.B_ZDlDH2.js",
    "global-cart-watcher.composable.DdMljqWd.js",
    "MyLists.store.CQXrb4VK.js",
    "base_layout.C0ZVG9Bk.js",
]

CARPETA = Path("hipercor_js")
CARPETA.mkdir(exist_ok=True)

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    )
}

for archivo in ARCHIVOS:

    print("\n" + "=" * 100)
    print("📥 DESCARGANDO:", archivo)
    print("=" * 100)

    url = BASE + archivo

    try:
        r = requests.get(
            url,
            headers=headers,
            timeout=30
        )

        print("STATUS:", r.status_code)
        print("TAMAÑO:", len(r.text))

        if r.status_code != 200:
            print("❌ No descargado")
            continue

        ruta = CARPETA / archivo
        ruta.write_text(r.text, encoding="utf-8")

        print("💾 Guardado:", ruta)

        texto = r.text

        patrones = [
            r'https?://[^"\'\s]+',
            r'["\']([^"\']*/api/[^"\']*)["\']',
            r'["\']([^"\']*product[^"\']*)["\']',
            r'["\']([^"\']*products[^"\']*)["\']',
            r'["\']([^"\']*search[^"\']*)["\']',
            r'["\']([^"\']*catalog[^"\']*)["\']',
            r'["\']([^"\']*graphql[^"\']*)["\']',
            r'["\']([^"\']*ean[^"\']*)["\']',
            r'["\']([^"\']*price[^"\']*)["\']',
        ]

        encontrados = set()

        for patron in patrones:
            try:
                resultados = re.findall(
                    patron,
                    texto,
                    flags=re.IGNORECASE
                )

                for resultado in resultados:

                    if isinstance(resultado, tuple):
                        resultado = resultado[0]

                    if len(resultado) > 300:
                        continue

                    encontrados.add(resultado)

            except Exception:
                pass

        print("\n🔎 POSIBLES PISTAS:")

        for x in sorted(encontrados):
            print("   ", x)

    except Exception as e:
        print("❌ ERROR:", e)


print("\n")
print("=" * 100)
print("🏁 ANÁLISIS TERMINADO")
print("=" * 100)

print("\n📁 Archivos descargados en:")
print(CARPETA.resolve())