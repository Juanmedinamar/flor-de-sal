# Vino Tracker

Aplicación para consultar y comparar precios de vinos y bebidas en supermercados y tiendas online.

## Características

- 🍷 **Catálogo de productos** con EAN, marca y formato
- 🏪 **12 tiendas** soportadas: Carrefour, Alcampo, Bodeboca, Hermanos Martin, El Corte Inglés, Hipercor, Makro, Mercadona, Decántalo, Grau Online, Vinoselección
- 📊 **Comparación de precios** con normalización de IVA
- 📈 **Histórico de precios** con gráficos de evolución
- 💾 **Base de datos local** SQLite
- 🔄 **Actualización automática** mediante scrapers

## Requisitos

- Python 3.11 o superior
- Windows 10/11
- Conexión a Internet

## Instalación

### Opción 1: Instalador automático (recomendado)

1. Descomprime el archivo `Vino_Tracker.zip` en una carpeta
2. Haz doble clic en `instalar.bat`
3. Espera a que termine la instalación

### Opción 2: Instalación manual

```bash
# Crear entorno virtual
python -m venv .venv

# Activar entorno virtual
# Windows:
.venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Instalar Chromium para Playwright
playwright install chromium
```

## Uso

### Iniciar la aplicación

Doble clic en `iniciar.bat` o:

```bash
.venv\Scripts\python.exe -m streamlit run app.py
```

### Actualizar precios desde terminal

```bash
# Actualizar todos los productos y tiendas
python actualizar_todo.py

# Actualizar productos específicos
python actualizar_todo.py --productos "Canasta Cream|Tío Pepe"

# Actualizar tiendas específicas
python actualizar_todo.py --tiendas "Carrefour|Mercadona"

# Combinación
python actualizar_todo.py --productos "Canasta Cream" --tiendas "Carrefour|Alcampo"
```

## Estructura del proyecto

```
Vino_Tracker/
├── app.py                 # Aplicación Streamlit
├── database.py            # Gestión de base de datos SQLite
├── productos.py           # Catálogo de productos
├── actualizar_todo.py     # Script de actualización
├── requirements.txt       # Dependencias
├── instalar.bat           # Instalador automático
├── iniciar.bat            # Launcher de la aplicación
├── scrapers/              # Scrapers de cada tienda
│   ├── carrefour.py
│   ├── alcampo.py
│   ├── bodeboca.py
│   ├── hermanos_martin.py
│   ├── corte_ingles.py
│   ├── hipercor.py
│   ├── makro.py
│   ├── mercadona.py
│   ├── decantalo.py
│   ├── grauonline.py
│   ├── vinoseleccion.py
│   └── common.py
├── data/                  # Base de datos local
│   └── precios.db
└── assets/                # Iconos y recursos
```

## Añadir un nuevo producto

Edita `productos.py` y añade una nueva entrada al diccionario `PRODUCTOS`:

```python
"Nombre del Producto": Producto(
    nombre="Nombre del Producto",
    ean="1234567890123",
    marca="Marca del Producto",
    formato="75 cl",
    urls={
        "Carrefour": "https://...",
        "Alcampo": "https://...",
        # ... resto de tiendas
    },
),
```

## Añadir una nueva tienda

1. Crea un archivo `scrapers/mitienda.py` con una función `obtener_mitienda(producto_config)`
2. Registra la tienda en `actualizar_todo.py` dentro del diccionario `TIENDAS`
3. Añade la tienda en la lista `tiendas_disponibles` de `app.py`

## Solución de problemas

### Python no está instalado
Instala Python 3.11+ desde [python.org](https://python.org)

### Error al instalar dependencias
Ejecuta `instalar.bat` como administrador

### Una tienda muestra error
Puede deberse a que la web bloquea temporalmente las consultas o el producto no está disponible

## Licencia

Este proyecto es de uso personal.
