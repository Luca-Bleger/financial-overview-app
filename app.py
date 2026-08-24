import pandas as pd
import streamlit as st

from data import (
    MESES_ES, REGLAS_CATEGORIAS, calcular_variacion, construir_movimientos,
    gastos_categoria_por_mes, gastos_por_categoria, leer_archivo_robusto,
    periodo_anterior_de, resumen_por_periodo, sugerencias_de_mapeo,
)
from charts import (
    grafico_categorias_tiempo, grafico_donut, grafico_evolucion,
    grafico_tasa_ahorro, grafico_top_gastos,
)
from insights import generar_insights

st.set_page_config(
    page_title="Financial Overview",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    .block-container { padding-top: 2rem; max-width: 1200px; }
    div[data-testid="stMetric"] {
        background-color: #152033;
        border: 1px solid #263752;
        border-radius: 10px;
        padding: 14px 16px;
    }
    div[data-testid="stMetricLabel"] { color: #8FA1BC; }
</style>
""", unsafe_allow_html=True)


# =========================================================
# PORTADA / CARGA DE ARCHIVO
# =========================================================

if "df_movimientos" not in st.session_state:
    st.session_state.df_movimientos = None

st.markdown("## 💰 Financial Overview")
st.caption("Tu panel personal de análisis financiero")

archivo = st.file_uploader(
    "Subí tu resumen o extracto (CSV o Excel)",
    type=["csv", "xlsx", "xls"],
    help="Funciona con resúmenes de distintos bancos, en CSV o Excel: en el siguiente paso "
         "vas a poder indicar qué columna es cuál. Si tu celular guardó el archivo como "
         ".xlsx, también anda.",
)

if archivo is None:
    st.session_state.df_movimientos = None
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### 📊 Varios análisis")
        st.caption("Evolución financiera, gastos por categoría, tasa de ahorro y tus mayores gastos del mes.")
    with col2:
        st.markdown("#### 🧠 Consejos automáticos")
        st.caption("Detecta aumentos, categorías nuevas y meses de ahorro flojo, sin IA externa ni costos.")
    with col3:
        st.markdown("#### 🏷️ Clasificación de gastos")
        st.caption("Categoriza automáticamente por palabras clave, y corregís lo que haga falta a mano.")
    st.info("Subí un archivo CSV para empezar. No hace falta que tenga un formato específico — "
            "vos le indicás a la app qué columna es la fecha, la descripción y el importe.")
    st.stop()


# =========================================================
# MAPEO DE COLUMNAS (los CSV de distintos bancos no vienen todos igual)
# =========================================================

try:
    df_raw = leer_archivo_robusto(archivo)
except Exception as e:
    st.error(f"No pude leer el archivo: {e}")
    st.stop()

with st.expander("Vista previa del archivo subido", expanded=False):
    st.dataframe(df_raw.head(10), width="stretch")

columnas = list(df_raw.columns)
sugerencias = sugerencias_de_mapeo(columnas)

st.markdown("#### Configurá las columnas de tu archivo")
st.caption("Cada banco exporta distinto — indicá acá qué columna corresponde a cada dato.")

col_a, col_b = st.columns(2)

with col_a:
    col_fecha = st.selectbox("Columna de fecha", columnas, index=sugerencias["fecha"] or 0)
    col_descripcion = st.selectbox("Columna de descripción", columnas, index=sugerencias["descripcion"] or 0)

    tiene_categoria = st.checkbox("Mi archivo ya trae una columna de categoría", value=sugerencias["categoria"] is not None)
    col_categoria = None
    if tiene_categoria:
        col_categoria = st.selectbox("Columna de categoría", columnas, index=sugerencias["categoria"] or 0)

with col_b:
    modo_importe_label = st.radio(
        "¿Cómo viene el importe en tu archivo?",
        ["Una sola columna con signo (+ ingreso / - gasto)", "Columnas separadas de Débito y Crédito"],
    )
    modo_importe = "unica" if modo_importe_label.startswith("Una sola") else "separado"

    if modo_importe == "unica":
        col_importe = st.selectbox("Columna de importe", columnas, index=sugerencias["importe"] or 0)
        col_debito = col_credito = None
    else:
        col_importe = None
        col_debito = st.selectbox("Columna de Débito (gastos)", columnas, index=sugerencias["debito"] or 0)
        col_credito = st.selectbox("Columna de Crédito (ingresos)", columnas, index=sugerencias["credito"] or 0)

    formato_numero_label = st.radio("Formato de los números", ["1234.56 (punto decimal)", "1.234,56 (coma decimal)"])
    formato_numero = "punto" if formato_numero_label.startswith("1234.56") else "coma"

    formato_fecha_label = st.selectbox("Formato de fecha", ["Detectar automáticamente (día primero)", "Mes primero (MM/DD/AAAA)"])
    formato_fecha = "mes_primero" if "Mes primero" in formato_fecha_label else "auto"

mapeo = {
    "fecha": col_fecha,
    "descripcion": col_descripcion,
    "categoria": col_categoria,
    "importe": col_importe,
    "debito": col_debito,
    "credito": col_credito,
}

try:
    df_movimientos, filas_invalidas = construir_movimientos(
        df_raw, mapeo, modo_importe, formato_numero, formato_fecha
    )
except Exception as e:
    st.error(f"No pude procesar el archivo con este mapeo: {e}")
    st.stop()

if df_movimientos.empty:
    st.error("No quedó ningún movimiento válido con este mapeo de columnas. Revisá la configuración de arriba.")
    st.stop()

if filas_invalidas > 0:
    st.warning(f"Se descartaron {filas_invalidas} fila(s) porque no se pudo interpretar la fecha o el importe.")

st.session_state.df_movimientos = df_movimientos
st.markdown("---")


# =========================================================
# SELECTOR DE PERÍODO
# =========================================================

df_solo_gastos = df_movimientos[df_movimientos["tipo"] == "Gasto"].copy()
df_solo_gastos["importe"] = df_solo_gastos["importe"].abs()

resumen = resumen_por_periodo(df_movimientos)
periodos_disponibles = sorted(df_movimientos["periodo"].unique())
opciones_periodo = {f"{MESES_ES[p.month]} {p.year}": p for p in periodos_disponibles}

nombre_seleccionado = st.selectbox(
    "📅 Período a analizar",
    options=list(opciones_periodo.keys()),
    index=len(opciones_periodo) - 1,
)
periodo_seleccionado = opciones_periodo[nombre_seleccionado]
periodo_anterior = periodo_anterior_de(periodos_disponibles, periodo_seleccionado)

ingresos_actual = resumen.loc[periodo_seleccionado, "Ingreso"]
gastos_actual = resumen.loc[periodo_seleccionado, "Gasto"]
saldo_actual = resumen.loc[periodo_seleccionado, "Saldo"]
tasa_ahorro = (saldo_actual / ingresos_actual) * 100 if ingresos_actual else 0

if periodo_anterior is not None:
    variacion_ingresos = calcular_variacion(ingresos_actual, resumen.loc[periodo_anterior, "Ingreso"])
    variacion_gastos = calcular_variacion(gastos_actual, resumen.loc[periodo_anterior, "Gasto"])
    variacion_saldo = calcular_variacion(saldo_actual, resumen.loc[periodo_anterior, "Saldo"])
else:
    variacion_ingresos = variacion_gastos = variacion_saldo = None


# =========================================================
# KPIs (responsive: se apilan solos en celular)
# =========================================================

k1, k2, k3, k4 = st.columns(4)
k1.metric("Ingresos", f"${ingresos_actual:,.0f}",
          f"{variacion_ingresos:+.1f}%" if variacion_ingresos is not None else None)
k2.metric("Gastos", f"${gastos_actual:,.0f}",
          f"{variacion_gastos:+.1f}%" if variacion_gastos is not None else None,
          delta_color="inverse")
k3.metric("Saldo", f"${saldo_actual:,.0f}",
          f"{variacion_saldo:+.1f}%" if variacion_saldo is not None else None)
k4.metric("Tasa de ahorro", f"{tasa_ahorro:.1f}%")


# =========================================================
# SECCIONES (apartados)
# =========================================================

tab_resumen, tab_categorias, tab_consejos, tab_movimientos = st.tabs(
    ["📈 Resumen", "🏷️ Categorías", "🧠 Consejos", "📋 Movimientos"]
)

with tab_resumen:
    col_izq, col_der = st.columns(2)
    with col_izq:
        st.markdown("##### Evolución financiera")
        st.plotly_chart(grafico_evolucion(resumen), width="stretch")
    with col_der:
        st.markdown("##### Gastos por categoría")
        gastos_cat_actual = gastos_por_categoria(df_solo_gastos, periodo_seleccionado)
        st.plotly_chart(grafico_donut(gastos_cat_actual), width="stretch")

    st.markdown("##### Mayores gastos individuales del mes")
    st.plotly_chart(grafico_top_gastos(df_solo_gastos, periodo_seleccionado), width="stretch")

with tab_categorias:
    cat_mes = gastos_categoria_por_mes(df_solo_gastos)
    st.markdown("##### Evolución de gastos por categoría")
    st.plotly_chart(grafico_categorias_tiempo(cat_mes), width="stretch")
    st.markdown("##### Tasa de ahorro por mes")
    st.plotly_chart(grafico_tasa_ahorro(resumen), width="stretch")

with tab_consejos:
    st.caption("Generados automáticamente a partir de tus datos — sin IA externa, sin costo.")
    insights = generar_insights(df_movimientos, df_solo_gastos, resumen, periodo_seleccionado)
    for item in insights:
        if item["tipo"] == "positivo":
            st.success(item["mensaje"])
        elif item["tipo"] == "alerta":
            st.warning(item["mensaje"])
        else:
            st.info(item["mensaje"])

with tab_movimientos:
    st.caption("Movimientos del período seleccionado. Podés corregir la categoría de cualquiera.")
    df_periodo = df_movimientos[df_movimientos["periodo"] == periodo_seleccionado].copy()
    categorias_existentes = sorted(set(df_movimientos["categoria"]) | set(REGLAS_CATEGORIAS.keys()) | {"Ingresos", "Sin clasificar"})

    editado = st.data_editor(
        df_periodo[["fecha", "descripcion", "importe", "categoria"]],
        column_config={
            "categoria": st.column_config.SelectboxColumn("categoria", options=categorias_existentes),
            "importe": st.column_config.NumberColumn("importe", format="$%.0f"),
        },
        disabled=["fecha", "descripcion", "importe"],
        width="stretch",
        hide_index=True,
        key=f"editor_{periodo_seleccionado}",
    )

    if not editado["categoria"].equals(df_periodo["categoria"].reset_index(drop=True)):
        df_movimientos.loc[df_periodo.index, "categoria"] = editado["categoria"].values
        st.session_state.df_movimientos = df_movimientos
        st.success("Categorías actualizadas. Descargá el CSV corregido abajo para no perder el cambio.")

    csv_actualizado = df_movimientos.drop(columns=["mes", "año", "periodo", "tipo"]).to_csv(index=False)
    st.download_button(
        "⬇️ Descargar CSV con las categorías corregidas",
        data=csv_actualizado,
        file_name="movimientos_corregidos.csv",
        mime="text/csv",
    )
