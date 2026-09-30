from dataclasses import dataclass


# ============================================================
# MODELO DE PRODUCTO
# ============================================================

@dataclass(frozen=True)
class Producto:

    nombre: str
    ean: str
    marca: str
    formato: str
    urls: dict


# ============================================================
# CATÁLOGO DE PRODUCTOS
# ============================================================

PRODUCTOS = {

    # ========================================================
    # CANASTA CREAM
    # ========================================================

    "Canasta Cream": Producto(

        nombre="Canasta Cream",

        ean="8410028030903",

        marca="Williams & Humbert",

        formato="75 cl",

        urls={

            "Carrefour": (
                "https://www.carrefour.es/"
                "canasta-cream-sherry-75cl-vino-generoso-"
                "espana-jerez-xeres-sherry-75-cl-195/"
                "8410028030903/p"
            ),

            "Alcampo": (
                "https://www.compraonline.alcampo.es/products/"
                "canasta-cream-vino-oloroso-dulce-con-d-o-jerez-"
                "xeres-sherry-botella-75-cl/36731"
            ),

            "Bodeboca": (
                "https://www.bodeboca.com/"
                "vino/canasta-cream-williams-humbert"
            ),

            "Hermanos Martin": (
                "https://www.supermercadosmas.com/"
                "vinos-dulces-generosos/"
                "vino-oloroso-canasta-cream-75cl/"
            ),

            "El Corte Inglés": (
                "https://www.elcorteingles.es/"
                "supermercado/B001018720300344-canasta-vino-"
                "oloroso-dulce-do-jerez-xeres-sherry-botella-75-cl/"
            ),

            "Hipercor": (
                "https://www.hipercor.es/"
                "supermercado/buscar?"
                "question=canasta&catalog=supermercado&stype=text_box"
            ),

            # Makro trabaja mediante búsqueda
            "Makro": (
                "https://www.makro.es/"
            ),

            # Mercadona trabaja mediante búsqueda
            "Mercadona": (
                "https://www.mercadona.es/"
            ),

            "Decántalo": (
                "https://www.decantalo.com/es/es/canasta-cream.html"
            ),

            "Grau Online": (
                "https://www.grauonline.es/vinos-generosos/canasta-cream-dulce.html"
            ),

            "Vinissimus": (
                "https://www.vinissimus.com/es/vino/williams-humbert-canasta-cream/"
            ),    
        },
    ),

    # ========================================================
    # GRAN DUQUE DE ALBA
    # ========================================================

    "Gran Duque de Alba": Producto(

        nombre="Gran Duque de Alba",

        ean="8410028530700",

        marca="Williams & Humbert",

        formato="70 cl",

        urls={

            # ------------------------------------------------
            # Estas tiendas las comprobaremos una a una.
            # ------------------------------------------------

            "Carrefour": "https://www.carrefour.es/supermercado/brandy-de-jerez-gran-duque-d-alba-solera-gran-reserva-70-cl/R-520663025/p",

            "Alcampo": None,

            "Bodeboca": None,

            "Hermanos Martin": None,

            "El Corte Inglés": "https://www.elcorteingles.es/supermercado/B001018725300190-gran-duque-de-alba-brandy-solera-gran-reserva-de-jerez-botella-70-cl/",

            "Hipercor": "https://www.hipercor.es/supermercado/B001018725300190-gran-duque-de-alba-brandy-solera-gran-reserva-de-jerez-botella-70-cl/",

            # ------------------------------------------------
            # Makro busca directamente el producto
            # ------------------------------------------------

            "Makro": (
                "https://www.makro.es/"
            ),

            # ------------------------------------------------
            # Mercadona busca mediante su buscador
            # ------------------------------------------------

            "Mercadona": (
                "https://www.mercadona.es/"
            ),
        },
    ),

    # ========================================================
    # DON ZOILO PEDRO XIMÉNEZ
    # ========================================================

    "Don Zoilo Pedro Ximénez": Producto(

        nombre="Don Zoilo Pedro Ximénez",

        ean="8410028005307",

        marca="Williams & Humbert",

        formato="75 cl",

        urls={

            "Carrefour": (
                "https://www.carrefour.es/"
                "williams-humbert-vino-generoso-don-zoilo-"
                "jerez-xeres-sherry-12-anos-75-cl-18-vol/"
                "8410028005307/p"
            ),

            "Alcampo": None,

            "Bodeboca": (
                "https://www.bodeboca.com/"
                "vino/don-zoilo-pedro-ximenez-rama-15-anos"
            ),

            "Hermanos Martin": None,

            "El Corte Inglés": None,

            "Hipercor": None,

            "Makro": "https://www.makro.es/",

            "Mercadona": "https://www.mercadona.es/",
        },
    ),


    # ========================================================
    # TÍO PEPE
    # ========================================================

    "Tío Pepe": Producto(

        nombre="Tío Pepe",

        ean="8410023000031",

        marca="González Byass",

        formato="75 cl",

        urls={

            # ------------------------------------------------
            # Estas tiendas todavía las vamos a integrar.
            # Dejamos None hasta comprobar sus fichas.
            # ------------------------------------------------

            "Carrefour": "https://www.carrefour.es/tio-pepe-vino-generoso-espana-jerez-xeres-sherry-75-cl-150/8410023000031/p",

            "Alcampo": None,

            "Bodeboca": None,

            "Hermanos Martin": None,

            "El Corte Inglés": None,

            "Hipercor": None,

            # ------------------------------------------------
            # Makro busca directamente el producto
            # ------------------------------------------------

            "Makro": (
                "https://www.makro.es/"
            ),

            # ------------------------------------------------
            # Mercadona busca directamente el producto
            # ------------------------------------------------

            "Mercadona": (
                "https://www.mercadona.es/"
            ),

            "Vinoselección": (
                "https://www.vinoseleccion.com/fino-tio-pepe-agr-51141"
            ),
        },
    ),
}


# ============================================================
# OBTENER PRODUCTO
# ============================================================

def obtener_producto(nombre):

    return PRODUCTOS.get(nombre)


# ============================================================
# OBTENER PRODUCTOS
# ============================================================

def obtener_productos():

    return PRODUCTOS


# ============================================================
# OBTENER NOMBRES
# ============================================================

def obtener_nombres_productos():

    return list(PRODUCTOS.keys())


# ============================================================
# PRUEBA
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("🍷 CATÁLOGO VINO TRACKER")
    print("=" * 70)

    print()
    print(f"Productos registrados: {len(PRODUCTOS)}")

    for producto in PRODUCTOS.values():

        print()
        print("-" * 70)

        print(f"🍷 {producto.nombre}")
        print(f"   Marca:   {producto.marca}")
        print(f"   Formato: {producto.formato}")
        print(f"   EAN:     {producto.ean}")

        print("   Tiendas:")

        for tienda, url in producto.urls.items():

            if url:

                print(f"      • {tienda}: {url}")

            else:

                print(f"      • {tienda}: URL PENDIENTE")

    print()
    print("=" * 70)
