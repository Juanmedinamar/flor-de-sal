from dataclasses import dataclass
from typing import Optional


@dataclass
class ProductoPrecio:

    tienda: str
    vendedor: str
    ean: str
    producto: str
    marca: str
    formato: str

    # Precio mostrado por la tienda.
    # En Makro será el precio SIN IVA.
    precio: Optional[float]

    stock: bool
    estado: str
    fuente: str
    url: str

    # ========================================================
    # INFORMACIÓN SOBRE IVA
    # ========================================================

    # Indica si el precio incluye IVA.
    #
    # True  = precio con IVA
    # False = precio sin IVA
    # None  = no especificado
    incluye_iva: Optional[bool] = None

    # Tipo de IVA aplicado, si se conoce.
    # Ejemplo: 21.0
    tipo_iva: Optional[float] = None

    # Precio calculado con IVA.
    #
    # Si precio=7.05 y tipo_iva=21:
    # precio_con_iva = 8.53
    #
    # Si la tienda ya muestra el precio con IVA,
    # este campo puede coincidir con precio.
    precio_con_iva: Optional[float] = None

    # Precio calculado sin IVA.
    #
    # Si la tienda muestra precio con IVA, podemos
    # calcular aquí el precio base.
    precio_sin_iva: Optional[float] = None
