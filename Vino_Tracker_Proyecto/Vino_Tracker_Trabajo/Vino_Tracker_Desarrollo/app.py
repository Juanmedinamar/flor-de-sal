
import streamlit as st
import pandas as pd
import subprocess
import sys
from pathlib import Path

from database import (
    obtener_ultimos_precios,
    obtener_precios
)

from productos import (
    obtener_producto,
    obtener_productos,
    obtener_nombres_productos
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="Vino Tracker",
    page_icon="🍷",
    layout="wide"
)


BASE_DIR = Path(__file__).resolve().parent


# ============================================================
# CATÁLOGO
# ============================================================

productos_catalogo = obtener_productos()

nombres_productos = (
    obtener_nombres_productos()
)


# ============================================================
# TIENDAS DISPONIBLES
# ============================================================

tiendas_disponibles = [

    "Carrefour",

    "Alcampo",

    "Bodeboca",

    "Hermanos Martin",

    "El Corte Inglés",

    "Hipercor",

    "Makro",

    "Mercadona",

    "Decántalo",

    "Grau Online",

    "Vinoselección",

]


# ============================================================
# CABECERA
# ============================================================

st.title("🍷 Vino Tracker")

st.subheader(
    "Seguimiento de precios de vinos"
)


# ============================================================
# SELECCIÓN
# ============================================================

col_productos, col_tiendas = st.columns(2)


# ============================================================
# PRODUCTOS
# ============================================================

with col_productos:

    st.markdown(
        "### 📦 Productos"
    )

    productos_seleccionados = st.multiselect(

        "Selecciona uno o varios productos",

        options=nombres_productos,

        default=(
            ["Canasta Cream"]
            if "Canasta Cream" in nombres_productos
            else []
        )
    )


# ============================================================
# TIENDAS
# ============================================================

with col_tiendas:

    st.markdown(
        "### 🏪 Tiendas"
    )

    tiendas_seleccionadas = st.multiselect(

        "Selecciona una o varias tiendas",

        options=tiendas_disponibles,

        default=tiendas_disponibles
    )


# ============================================================
# INFORMACIÓN DE PRODUCTOS
# ============================================================

if productos_seleccionados:

    st.markdown(
        "### 🍷 Productos seleccionados"
    )

    informacion = []

    for nombre in productos_seleccionados:

        producto = obtener_producto(
            nombre
        )

        if producto is None:
            continue

        informacion.append({

            "Producto":
                producto.nombre,

            "Marca":
                producto.marca,

            "Formato":
                producto.formato,

            "EAN":
                producto.ean
        })

    if informacion:

        st.dataframe(

            pd.DataFrame(
                informacion
            ),

            width="stretch",

            hide_index=True
        )


# ============================================================
# BOTÓN ACTUALIZAR
# ============================================================

st.markdown("---")


actualizar = st.button(

    "🔄 Actualizar precios seleccionados",

    type="primary",

    width="stretch"
)


# ============================================================
# VALIDACIÓN
# ============================================================

if actualizar:

    if not productos_seleccionados:

        st.error(
            "❌ Selecciona al menos un producto."
        )

        st.stop()

    if not tiendas_seleccionadas:

        st.error(
            "❌ Selecciona al menos una tienda."
        )

        st.stop()

    # --------------------------------------------------------
    # CONSTRUIR ARGUMENTOS
    # --------------------------------------------------------

    productos_arg = "|".join(
        productos_seleccionados
    )

    tiendas_arg = "|".join(
        tiendas_seleccionadas
    )

    # --------------------------------------------------------
    # EJECUTAR ACTUALIZACIÓN
    # --------------------------------------------------------

    with st.spinner(
        "🔄 Actualizando precios..."
    ):

        try:

            resultado = subprocess.run(

                [

                    sys.executable,

                    "actualizar_todo.py",

                    "--productos",
                    productos_arg,

                    "--tiendas",
                    tiendas_arg
                ],

                cwd=BASE_DIR,

                capture_output=True,

                text=True,

                encoding="utf-8",

                errors="replace",

                timeout=600
            )

            st.session_state[
                "ultima_actualizacion"
            ] = resultado.stdout

            st.session_state[
                "actualizacion_error"
            ] = resultado.stderr

            st.session_state[
                "codigo_actualizacion"
            ] = resultado.returncode

        except subprocess.TimeoutExpired:

            st.session_state[
                "ultima_actualizacion"
            ] = (
                "⚠️ La actualización ha superado "
                "el tiempo máximo de 10 minutos."
            )

            st.session_state[
                "actualizacion_error"
            ] = ""

            st.session_state[
                "codigo_actualizacion"
            ] = -1

        except Exception as e:

            st.session_state[
                "ultima_actualizacion"
            ] = ""

            st.session_state[
                "actualizacion_error"
            ] = str(e)

            st.session_state[
                "codigo_actualizacion"
            ] = -1

    st.rerun()


# ============================================================
# RESULTADO ACTUALIZACIÓN
# ============================================================

if "codigo_actualizacion" in st.session_state:

    codigo = (
        st.session_state[
            "codigo_actualizacion"
        ]
    )

    if codigo == 0:

        st.success(
            "✅ Actualización terminada"
        )

    else:

        st.warning(
            "⚠️ La actualización terminó "
            "con incidencias."
        )

    with st.expander(
        "📋 Ver resultado de la actualización"
    ):

        salida = (
            st.session_state.get(
                "ultima_actualizacion",
                ""
            )
        )

        error = (
            st.session_state.get(
                "actualizacion_error",
                ""
            )
        )

        if salida:

            st.code(
                salida,
                language="text"
            )

        if error:

            st.error(
                error
            )


# ============================================================
# RESULTADOS ACTUALES
# ============================================================

if not productos_seleccionados:

    st.info(
        "Selecciona uno o varios productos "
        "para consultar sus precios."
    )

    st.stop()


# ============================================================
# MOSTRAR CADA PRODUCTO
# ============================================================

for PRODUCTO in productos_seleccionados:

    producto_config = obtener_producto(
        PRODUCTO
    )

    if producto_config is None:
        continue

    st.markdown("---")

    st.markdown(
        f"## 🍷 {producto_config.nombre}"
    )

    st.caption(

        f"Marca: {producto_config.marca} · "

        f"EAN: {producto_config.ean} · "

        f"Formato: {producto_config.formato}"
    )

    # --------------------------------------------------------
    # DATOS
    # --------------------------------------------------------

    datos = obtener_ultimos_precios(
        PRODUCTO
    )

    if not datos:

        st.info(
            "No hay precios registrados "
            "para este producto."
        )

        continue

    filas = []

    for dato in datos:

        (
            fecha,
            tienda,
            vendedor,
            producto_db,
            marca,
            formato,
            precio,
            precio_litro,
            stock,
            estado,
            fuente,
            url
        ) = dato

        if precio is None:
            continue

        # Solo tiendas seleccionadas

        if (
            tiendas_seleccionadas
            and tienda not in tiendas_seleccionadas
        ):
            continue

        filas.append({

            "Tienda":
                tienda,

            "Vendedor":
                vendedor or "No indicado",

            "Precio (€)":
                precio,

            "€/Litro":
                precio_litro,

            "IVA":
                "Sin IVA"
                if tienda == "Makro"
                else "IVA incluido",

            "Stock":
                (
                    "Disponible"
                    if stock
                    else "Sin stock"
                ),

            "Estado":
                (
                    "Correcto"
                    if estado == "OK"
                    else "Error"
                ),

            "Actualizado":
                fecha,

            "URL":
                url
        })

    df = pd.DataFrame(
        filas
    )

    if df.empty:

        st.warning(
            "No hay precios disponibles "
            "para las tiendas seleccionadas."
        )

        continue

    # --------------------------------------------------------
    # ÚLTIMA ACTUALIZACIÓN
    # --------------------------------------------------------

    try:

        fechas = pd.to_datetime(
            df["Actualizado"]
        )

        ultima_fecha = fechas.max()

        st.caption(

            "🕐 Último dato registrado: "

            f"{ultima_fecha.strftime('%d/%m/%Y %H:%M:%S')}"
        )

    except Exception:

        pass

    # --------------------------------------------------------
    # MÉTRICAS
    # --------------------------------------------------------

    precio_minimo = (
        df["Precio (€)"].min()
    )

    precio_medio = (
        df["Precio (€)"].mean()
    )

    precio_maximo = (
        df["Precio (€)"].max()
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "💰 Precio mínimo",
            f"{precio_minimo:.2f} €"
        )

    with col2:

        st.metric(
            "📊 Precio medio",
            f"{precio_medio:.2f} €"
        )

    with col3:

        st.metric(
            "📈 Precio máximo",
            f"{precio_maximo:.2f} €"
        )

    # --------------------------------------------------------
    # TABLA
    # --------------------------------------------------------

    st.markdown(
        "### 🛒 Precios encontrados"
    )

    st.caption(
    "ℹ️ Los precios de Makro se muestran sin IVA. "
    )

    df_tabla = df[
        [
            "Tienda",
            "Vendedor",
            "Precio (€)",
            "€/Litro",
            "IVA",
            "Stock",
            "Estado",
            "Actualizado"
        ]
    ].copy()

    df_tabla = df_tabla.sort_values(
        "Precio (€)"
    )

    st.dataframe(

        df_tabla,

        width="stretch",

        hide_index=True,

        column_config={

            "Precio (€)":
                st.column_config.NumberColumn(
                    "Precio (€)",
                    format="%.2f €"
                ),

            "IVA":
                st.column_config.TextColumn(
                    "IVA"
                ),

            "€/Litro":
                st.column_config.NumberColumn(
                    "€/Litro",
                    format="%.2f €/L"
                )
        }
    )

    # --------------------------------------------------------
    # MEJOR PRECIO
    # --------------------------------------------------------


    
    # Normalizamos todos los precios a IVA incluido para determinar
    # cuál es realmente el mejor precio.

    IVA = 0.21

    df_comparable = df.copy()

    df_comparable["Precio comparable (€)"] = df_comparable.apply(
        lambda fila: (
            fila["Precio (€)"] * (1 + IVA)
            if fila["Tienda"] == "Makro"
            else fila["Precio (€)"]
        ),
        axis=1
    )

    # El mejor precio es el menor precio después de normalizar el IVA
    mejor = df_comparable.loc[
        df_comparable["Precio comparable (€)"].idxmin()
    ]

    precio_mejor = mejor["Precio comparable (€)"]

    # Precio por litro comparable
    if mejor["Tienda"] == "Makro":
        precio_litro_mejor = mejor["€/Litro"] * (1 + IVA)
    else:
        precio_litro_mejor = mejor["€/Litro"]

    st.markdown("### 🏆 Mejor precio")

    st.success(
        f"**{mejor['Tienda']}** — "
        f"{precio_mejor:.2f} € IVA incluido "
        f"({precio_litro_mejor:.2f} €/L)"
    )

    if mejor["Tienda"] == "Makro":
        st.caption(
            "ℹ️ El precio original de Makro se muestra sin IVA. "
            "Para esta comparación se ha añadido el 21% de IVA."
        )


    # --------------------------------------------------------
    # AHORRO
    # --------------------------------------------------------


    st.markdown("### 💶 Ahorro frente al mejor precio")

    # NORMALIZAR PRECIOS A IVA INCLUIDO
    # Makro muestra el precio sin IVA.
    # El resto de tiendas se consideran con IVA incluido.
    IVA = 0.21

    df_ahorro_base = df.copy()

    df_ahorro_base["Precio comparable (€)"] = df_ahorro_base.apply(
        lambda fila: (
            fila["Precio (€)"] * (1 + IVA)
            if fila["Tienda"] == "Makro"
            else fila["Precio (€)"]
        ),
        axis=1
    )

    # Buscar el mejor precio REAL después de normalizar el IVA
    indice_mejor_ahorro = df_ahorro_base["Precio comparable (€)"].idxmin()
    mejor_ahorro = df_ahorro_base.loc[indice_mejor_ahorro]

    precio_mejor_comparable = mejor_ahorro["Precio comparable (€)"]

    # Construir tabla de ahorro
    ahorros = []

    for _, fila in df_ahorro_base.iterrows():

        precio_comparable = fila["Precio comparable (€)"]

        ahorro = precio_comparable - precio_mejor_comparable

        if precio_comparable > 0:
            porcentaje = ahorro / precio_comparable * 100
        else:
            porcentaje = 0

        ahorros.append({
            "Tienda": fila["Tienda"],
            "Precio original (€)": fila["Precio (€)"],
            "IVA": fila["IVA"],
            "Precio comparable (€)": precio_comparable,
            "Más caro (€)": ahorro,
            "Diferencia (%)": porcentaje
        })

    df_ahorro = pd.DataFrame(ahorros)

    # Ordenar desde el precio comparable más barato
    df_ahorro = df_ahorro.sort_values("Precio comparable (€)")

    # Mostrar mejor precio
    st.success(
        f"🏆 Mejor precio comparable: **{mejor_ahorro['Tienda']}** — "
        f"{precio_mejor_comparable:.2f} € IVA incluido"
    )

    # Aviso si aparece Makro
    if "Makro" in df_ahorro["Tienda"].values:
        st.caption(
            "ℹ️ Para comparar correctamente, el precio de Makro "
            "se ha convertido de sin IVA a IVA incluido (21%)."
        )

    # Tabla
    st.dataframe(
        df_ahorro,
        width="stretch",
        hide_index=True,
        column_config={
            "Precio original (€)": st.column_config.NumberColumn(
                "Precio original (€)",
                format="%.2f €"
            ),
            "Precio comparable (€)": st.column_config.NumberColumn(
                "Precio comparable (€)",
                format="%.2f €"
            ),
            "Más caro (€)": st.column_config.NumberColumn(
                "Más caro (€)",
                format="%.2f €"
            ),
            "Diferencia (%)": st.column_config.NumberColumn(
                "Diferencia (%)",
                format="%.1f %%"
            )
        }
    )


    # --------------------------------------------------------
    # HISTÓRICO
    # --------------------------------------------------------

    st.markdown(
        "### 📈 Histórico de precios"
    )

    historico = obtener_precios()

    registros = []

    for dato in historico:

        (
            fecha,
            tienda,
            vendedor,
            producto_db,
            marca,
            formato,
            precio,
            precio_litro,
            stock,
            estado,
            fuente,
            url
        ) = dato

        if (
            producto_db != PRODUCTO
            or precio is None
            or tienda not in tiendas_seleccionadas
        ):
            continue

        registros.append({

            "Fecha":
                pd.to_datetime(fecha),

            "Tienda":
                tienda,

            "Precio":
                precio
        })

    if registros:

        df_historico = pd.DataFrame(
            registros
        )

        df_evolucion = (

            df_historico

            .pivot_table(

                index="Fecha",

                columns="Tienda",

                values="Precio",

                aggfunc="last"
            )

            .sort_index()
        )

        st.line_chart(

            df_evolucion,

            y_label="Precio (€)",

            x_label="Fecha"
        )

    else:

        st.info(
            "Todavía no hay histórico "
            "para las tiendas seleccionadas."
        )

    # --------------------------------------------------------
    # ENLACES
    # --------------------------------------------------------

    st.markdown(
        "### 🔗 Tiendas"
    )

    for _, fila in df.iterrows():

        if fila["URL"]:

            st.markdown(

                f"- **{fila['Tienda']}** — "
                f"[Ver producto]({fila['URL']})"
            )