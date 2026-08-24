from pathlib import Path

import pandas as pd
import streamlit as st

from data import (
    FREQ_POR_GRANULARIDAD, MESES_ES, REGLAS_CATEGORIAS, calcular_variacion,
    construir_movimientos, gastos_categoria_por_mes, gastos_por_categoria,
    leer_archivo_robusto, mapeo_fijo_pdf_mercadopago, periodo_anterior_de,
    proyectar_ahorro, resumen_por_granularidad, resumen_por_periodo,
    sugerencias_de_mapeo,
)
from charts import (
    grafico_categorias_tiempo, grafico_donut, grafico_evolucion,
    grafico_tasa_ahorro, grafico_top_gastos,
)
from insights import generar_insights
from preguntas import PREGUNTAS_SUGERIDAS, responder as responder_pregunta

st.set_page_config(
    page_title="Financial Overview",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    .block-container { padding-top: 2rem; max-width: 1200px; animation: fadeSlideUp 0.5s ease-out; }

    @keyframes fadeSlideUp {
        from { opacity: 0; transform: translateY(14px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }

    div[data-testid="stMetric"] {
        background-color: #152033;
        border: 1px solid #263752;
        border-radius: 10px;
        padding: 14px 16px;
        transition: border-color 0.2s ease, transform 0.2s ease;
    }
    div[data-testid="stMetric"]:hover {
        border-color: #67D2D0;
        transform: translateY(-2px);
    }
    div[data-testid="stMetricLabel"] { color: #8FA1BC; }

    /* Tarjetas (st.container(border=True)): mismo lenguaje visual que los
       gráficos de Plotly (mismo fondo/borde), con un realce sutil al pasar
       el mouse para que se sientan interactivas. */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #152033;
        border-color: #263752 !important;
        border-radius: 14px !important;
        transition: border-color 0.25s ease, box-shadow 0.25s ease, transform 0.25s ease;
        animation: fadeIn 0.6s ease-out both;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(button):hover {
        border-color: #67D2D0 !important;
        box-shadow: 0 10px 28px rgba(103, 210, 208, 0.14);
        transform: translateY(-3px);
    }

    /* Tarjetas de la pantalla inicial: aparecen escalonadas (cada columna un
       poco después que la anterior) y con un borde superior de color según
       la posición, para que la fila no se vea toda igual/vacía. */
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(1) div[data-testid="stVerticalBlockBorderWrapper"] {
        animation-delay: 0.05s;
        border-top: 3px solid #8B95F6 !important;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(2) div[data-testid="stVerticalBlockBorderWrapper"] {
        animation-delay: 0.15s;
        border-top: 3px solid #67D2D0 !important;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(3) div[data-testid="stVerticalBlockBorderWrapper"] {
        animation-delay: 0.25s;
        border-top: 3px solid #FF8194 !important;
    }

    /* Botones: efecto de elevación suave al pasar el mouse/tocar */
    div[data-testid="stButton"] button {
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    div[data-testid="stButton"] button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
    }

    /* Fondo decorativo de la pantalla inicial: dos manchas de gradiente
       difuminadas que flotan suavemente, para que el hero no se vea vacío
       (estilo landing de app de finanzas, sin depender de imágenes externas). */
    .hero-wrap {
        position: relative;
        padding-top: 6px;
    }
    .hero-fondo {
        position: absolute;
        top: -60px;
        left: -40px;
        right: -40px;
        height: 260px;
        overflow: visible;
        z-index: -1;
        pointer-events: none;
    }
    .hero-fondo::before, .hero-fondo::after {
        content: "";
        position: absolute;
        border-radius: 50%;
        filter: blur(60px);
        opacity: 0.30;
        animation: flotar 7s ease-in-out infinite alternate;
    }
    .hero-fondo::before {
        width: 260px; height: 260px;
        background: #8B95F6;
        top: -40px; left: 0;
    }
    .hero-fondo::after {
        width: 240px; height: 240px;
        background: #67D2D0;
        top: 10px; right: 10px;
        animation-delay: 1.2s;
    }
    @keyframes flotar {
        from { transform: translateY(0) scale(1); }
        to { transform: translateY(18px) scale(1.1); }
    }

    .hero-titulo {
        font-size: 2.6rem;
        font-weight: 800;
        margin-bottom: 0;
        background: linear-gradient(90deg, #F8FAFC 0%, #8FA1BC 100%);
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .hero-accent {
        height: 4px;
        width: 64px;
        border-radius: 4px;
        margin: 10px 0 16px 0;
        background: linear-gradient(90deg, #8B95F6, #67D2D0);
        background-size: 200% 100%;
        animation: brillo 3s ease-in-out infinite;
    }
    @keyframes brillo {
        0%, 100% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
    }
    .hero-subtitulo {
        color: #CBD5E1;
        font-size: 1.05rem;
        margin-bottom: 18px;
    }

    .badge-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 30px;
    }
    .badge-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(103, 210, 208, 0.08);
        border: 1px solid rgba(103, 210, 208, 0.28);
        color: #9FB4CE;
        padding: 5px 13px;
        border-radius: 999px;
        font-size: 12.5px;
        font-weight: 500;
    }

    /* Portada: pantalla de bienvenida previa a la pantalla de opciones,
       con manchas de gradiente e íconos de finanzas flotando de fondo. */
    .portada-wrap {
        min-height: 60vh;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        position: relative;
        overflow: hidden;
        padding: 20px 12px;
    }
    .portada-fondo {
        position: absolute;
        inset: -60px;
        z-index: -1;
        pointer-events: none;
    }
    .portada-fondo::before, .portada-fondo::after {
        content: "";
        position: absolute;
        border-radius: 50%;
        filter: blur(80px);
        opacity: 0.32;
        animation: flotar 8s ease-in-out infinite alternate;
    }
    .portada-fondo::before {
        width: 340px; height: 340px;
        background: #8B95F6;
        top: 8%; left: 8%;
    }
    .portada-fondo::after {
        width: 320px; height: 320px;
        background: #67D2D0;
        bottom: 4%; right: 8%;
        animation-delay: 1.4s;
    }
    .portada-iconos {
        position: absolute;
        inset: 0;
        z-index: 0;
        pointer-events: none;
    }
    .icono-flotante {
        position: absolute;
        font-size: 2rem;
        opacity: 0.35;
        animation: flotar-icono 6s ease-in-out infinite;
    }
    .icono-flotante.i1 { top: 12%; left: 10%; animation-delay: 0s; }
    .icono-flotante.i2 { top: 18%; right: 12%; animation-delay: 1s; font-size: 2.4rem; }
    .icono-flotante.i3 { bottom: 20%; left: 14%; animation-delay: 2s; }
    .icono-flotante.i4 { bottom: 14%; right: 8%; animation-delay: 0.6s; font-size: 2.6rem; }
    .icono-flotante.i5 { top: 46%; left: 3%; animation-delay: 1.6s; font-size: 1.6rem; }
    @keyframes flotar-icono {
        0%, 100% { transform: translateY(0) rotate(0deg); }
        50% { transform: translateY(-14px) rotate(6deg); }
    }
    .portada-titulo {
        font-size: 3.3rem;
        line-height: 1.08;
        font-weight: 800;
        margin-bottom: 4px;
        background: linear-gradient(90deg, #F8FAFC 0%, #8FA1BC 60%, #67D2D0 100%);
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
        z-index: 1;
        position: relative;
    }
    .portada-tagline {
        color: #9FB4CE;
        font-size: 1.08rem;
        max-width: 480px;
        margin: 18px auto 6px auto;
        z-index: 1;
        position: relative;
    }
    @media (max-width: 640px) {
        .portada-titulo { font-size: 2.3rem; }
        .icono-flotante { font-size: 1.5rem !important; }
    }

    /* Streamlit no apila st.columns solo en pantallas angostas: sin esto,
       cada columna queda apretada a una fracción del ancho del celular
       (por ejemplo, el gráfico de Evolución financiera quedaba a la mitad
       del ancho de la pantalla). Se fuerza que se apilen en una sola
       columna de ancho completo por debajo de ~640px. */
    @media (max-width: 640px) {
        div[data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }
    }
</style>
""", unsafe_allow_html=True)


if "vista" not in st.session_state:
    st.session_state.vista = "portada"
if "usar_ejemplo" not in st.session_state:
    st.session_state.usar_ejemplo = False


# =========================================================
# PORTADA: pantalla de bienvenida, antes de mostrar las opciones
# =========================================================

if st.session_state.vista == "portada":
    st.markdown("""
        <div class="portada-wrap">
            <div class="portada-fondo"></div>
            <div class="portada-iconos">
                <span class="icono-flotante i1">💰</span>
                <span class="icono-flotante i2">📈</span>
                <span class="icono-flotante i3">💳</span>
                <span class="icono-flotante i4">🏦</span>
                <span class="icono-flotante i5">📊</span>
            </div>
            <div class="portada-titulo">Financial<br/>Overview</div>
            <div class="hero-accent" style="margin-left:auto;margin-right:auto;"></div>
            <div class="portada-tagline">
                Tu panel personal para entender, ordenar y proyectar tus finanzas —
                gratis, sin cuentas y sin subir tus datos a ningún lado.
            </div>
        </div>
    """, unsafe_allow_html=True)

    _, col_centro, _ = st.columns([1, 1.4, 1])
    with col_centro:
        if st.button("Comenzar →", width="stretch", type="primary", key="btn_portada"):
            st.session_state.vista = "inicio"
            st.rerun()

    st.stop()


# =========================================================
# PANTALLA INICIAL: elegir qué querés hacer antes de subir nada
# =========================================================

if st.session_state.vista == "inicio":
    st.markdown("""
        <div class="hero-wrap">
            <div class="hero-fondo"></div>
            <div class="hero-titulo">💰 Financial Overview</div>
            <div class="hero-accent"></div>
            <div class="hero-subtitulo">Entendé a dónde va tu plata, en segundos. Subí tu resumen y obtené
                gráficos, categorías y consejos automáticos al instante.</div>
            <div class="badge-row">
                <span class="badge-pill">🔒 100% local, no se guarda en ningún lado</span>
                <span class="badge-pill">🤖 Sin IA de pago ni cuentas</span>
                <span class="badge-pill">📱 Anda en el celu y en la compu</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("#### ¿Qué querés hacer?")

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown(
                '<span class="badge-pill" style="margin-bottom:8px;">⭐ Recomendado</span>',
                unsafe_allow_html=True,
            )
            st.markdown("##### 📤 Analizar mis movimientos")
            st.caption("Subí tu resumen bancario o de Mercado Pago (CSV, Excel o PDF) y generá tu dashboard.")
            if st.button("Empezar", width="stretch", type="primary", key="btn_analizar"):
                st.session_state.vista = "cargar"
                st.session_state.usar_ejemplo = False
                st.rerun()
    with col2:
        with st.container(border=True):
            st.markdown("##### 🧪 Probar con datos de ejemplo")
            st.caption("Mirá cómo funciona la app con datos ficticios, sin subir ningún archivo tuyo.")
            if st.button("Ver demo", width="stretch", key="btn_demo"):
                st.session_state.vista = "cargar"
                st.session_state.usar_ejemplo = True
                st.rerun()

    st.markdown("#####  ")
    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            st.markdown("##### 📊 Varios análisis")
            st.caption("Evolución financiera, gastos por categoría, tasa de ahorro y tus mayores gastos del mes.")
    with c2:
        with st.container(border=True):
            st.markdown("##### 🧠 Consejos automáticos")
            st.caption("Detecta aumentos, categorías nuevas y meses de ahorro flojo, sin IA externa ni costos.")
    with c3:
        with st.container(border=True):
            st.markdown("##### 🏷️ Clasificación de gastos")
            st.caption("Categoriza automáticamente por palabras clave, y corregís lo que haga falta a mano.")

    st.stop()


# =========================================================
# CARGA DE ARCHIVO
# =========================================================

st.markdown("## 💰 Financial Overview")
if st.button("← Volver al inicio"):
    st.session_state.vista = "inicio"
    st.session_state.usar_ejemplo = False
    st.rerun()

if st.session_state.usar_ejemplo:
    st.info("📎 Estás viendo datos de ejemplo, no los tuyos. Tocá \"← Volver al inicio\" cuando quieras subir tu propio archivo.")
    df_raw = pd.read_csv(Path(__file__).parent / "movimientos_ejemplo_2.csv")
    tipo_fuente = "tabla"
else:
    archivo = st.file_uploader(
        "Subí tu resumen o extracto (CSV, Excel o PDF de Mercado Pago)",
        type=["csv", "xlsx", "xls", "pdf"],
        help="Funciona con resúmenes de distintos bancos, en CSV o Excel: en el siguiente paso "
             "vas a poder indicar qué columna es cuál. Si tu celular guardó el archivo como "
             ".xlsx, también anda. Los PDF de \"Resumen de cuenta\" de Mercado Pago se reconocen "
             "automáticamente.",
    )
    if archivo is None:
        st.stop()

    try:
        df_raw, tipo_fuente = leer_archivo_robusto(archivo)
    except Exception as e:
        st.error(f"No pude leer el archivo: {e}")
        st.stop()


# =========================================================
# MAPEO DE COLUMNAS (los CSV de distintos bancos no vienen todos igual)
# =========================================================

with st.expander("Vista previa del archivo", expanded=False):
    st.dataframe(df_raw.head(10), width="stretch")

if tipo_fuente == "pdf_mercadopago":
    st.success(
        f"Reconocí un resumen de cuenta de Mercado Pago — extraje {len(df_raw)} movimientos "
        "automáticamente, sin necesidad de mapear columnas."
    )
    mapeo = mapeo_fijo_pdf_mercadopago()
    modo_importe = "unica"
    formato_numero = "punto"
    formato_fecha = "auto"
elif st.session_state.usar_ejemplo:
    mapeo = {"fecha": "fecha", "descripcion": "descripcion", "categoria": None, "importe": "importe"}
    modo_importe = "unica"
    formato_numero = "punto"
    formato_fecha = "auto"
else:
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
k1.metric("💰 Ingresos", f"${ingresos_actual:,.0f}",
          f"{variacion_ingresos:+.1f}%" if variacion_ingresos is not None else None)
k2.metric("💸 Gastos", f"${gastos_actual:,.0f}",
          f"{variacion_gastos:+.1f}%" if variacion_gastos is not None else None,
          delta_color="inverse")
k3.metric("🏦 Saldo", f"${saldo_actual:,.0f}",
          f"{variacion_saldo:+.1f}%" if variacion_saldo is not None else None)
k4.metric("📈 Tasa de ahorro", f"{tasa_ahorro:.1f}%")


# =========================================================
# SECCIONES (apartados)
# =========================================================

tab_resumen, tab_categorias, tab_consejos, tab_preguntas, tab_proyeccion, tab_movimientos = st.tabs(
    ["📈 Resumen", "🏷️ Categorías", "🧠 Consejos", "💬 Preguntas", "🎯 Proyección", "📋 Movimientos"]
)

with tab_resumen:
    with st.container(border=True):
        st.markdown("##### 📈 Evolución financiera")

        # Con un solo mes cargado, agrupar por mes muestra un solo punto sin
        # sentido — por default se elige la granularidad más chica que sí
        # tenga más de un período, para que el gráfico sea útil de entrada.
        opciones_gran = {"Día": "dia", "Semana": "semana", "Mes": "mes", "Año": "año"}
        indice_default = 2  # "Mes"
        if len(periodos_disponibles) < 2:
            for i, clave in enumerate(["dia", "semana", "mes", "año"]):
                if df_movimientos["fecha"].dt.to_period(FREQ_POR_GRANULARIDAD[clave]).nunique() > 1:
                    indice_default = i
                    break

        granularidad_label = st.radio(
            "Ver evolución por:", list(opciones_gran.keys()),
            index=indice_default, horizontal=True, key="granularidad_evolucion",
        )
        granularidad = opciones_gran[granularidad_label]
        resumen_gran = resumen_por_granularidad(df_movimientos, granularidad)
        st.plotly_chart(grafico_evolucion(resumen_gran, granularidad), width="stretch")

    with st.container(border=True):
        st.markdown("##### 🍩 Gastos por categoría")
        gastos_cat_actual = gastos_por_categoria(df_solo_gastos, periodo_seleccionado)
        st.plotly_chart(grafico_donut(gastos_cat_actual), width="stretch")

    with st.container(border=True):
        st.markdown("##### 🔝 Mayores gastos individuales del mes")
        st.plotly_chart(grafico_top_gastos(df_solo_gastos, periodo_seleccionado), width="stretch")

with tab_categorias:
    cat_mes = gastos_categoria_por_mes(df_solo_gastos)
    with st.container(border=True):
        st.markdown("##### 📊 Evolución de gastos por categoría")
        st.plotly_chart(grafico_categorias_tiempo(cat_mes), width="stretch")
    with st.container(border=True):
        st.markdown("##### 💹 Tasa de ahorro por mes")
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

with tab_preguntas:
    st.caption(
        "Respuestas generadas al instante con tus propios datos, no es una IA real conectada "
        "a internet — así que no tiene costo ni límite de uso."
    )

    contexto_preguntas = {
        "df_movimientos": df_movimientos,
        "df_solo_gastos": df_solo_gastos,
        "resumen": resumen,
        "periodo_seleccionado": periodo_seleccionado,
        "gastos_actual": gastos_actual,
        "gastos_cat": gastos_por_categoria(df_solo_gastos, periodo_seleccionado),
    }

    if "chat_preguntas" not in st.session_state:
        st.session_state.chat_preguntas = []

    st.markdown("###### Preguntas sugeridas")
    cols_preguntas = st.columns(2)
    for i, pregunta in enumerate(PREGUNTAS_SUGERIDAS):
        if cols_preguntas[i % 2].button(pregunta, key=f"pregunta_{i}", width="stretch"):
            respuesta = responder_pregunta(pregunta, contexto_preguntas)
            st.session_state.chat_preguntas.append({"role": "user", "content": pregunta})
            st.session_state.chat_preguntas.append({"role": "assistant", "content": respuesta})
            st.rerun()

    st.markdown("###### Conversación")
    with st.container(border=True):
        if not st.session_state.chat_preguntas:
            st.caption("Elegí una pregunta de arriba o escribí la tuya abajo para empezar.")
        for mensaje in st.session_state.chat_preguntas:
            with st.chat_message(mensaje["role"], avatar="🧑" if mensaje["role"] == "user" else "🤖"):
                st.markdown(mensaje["content"])

    pregunta_libre = st.chat_input("Escribí tu pregunta sobre tus movimientos...")
    if pregunta_libre:
        respuesta = responder_pregunta(pregunta_libre, contexto_preguntas)
        st.session_state.chat_preguntas.append({"role": "user", "content": pregunta_libre})
        st.session_state.chat_preguntas.append({"role": "assistant", "content": respuesta})
        st.rerun()

with tab_proyeccion:
    st.caption(
        "Estimación directa a partir del ahorro promedio de los meses que ya cargaste — cálculo "
        "simple, sin IA."
    )

    with st.container(border=True):
        st.markdown("##### 🎯 ¿Cuánto necesito ahorrar para comprar algo?")

        col_monto, col_plazo = st.columns(2)
        with col_monto:
            monto_objetivo = st.number_input(
                "Monto que querés juntar ($)", min_value=0.0, step=10000.0, value=500000.0, format="%.0f",
            )
        with col_plazo:
            meses_deseados = st.number_input(
                "¿En cuántos meses te gustaría lograrlo? (opcional)", min_value=0, step=1, value=0,
            )

        resultado = proyectar_ahorro(resumen, monto_objetivo, meses_deseados or None)
        promedio = resultado["promedio_ahorro"]

        st.markdown("---")
        st.metric("Ahorro promedio mensual (histórico)", f"${promedio:,.0f}")

        if promedio <= 0:
            st.warning(
                "Con tu ritmo actual no estás ahorrando (el saldo promedio de tus meses cargados es "
                "negativo o cero), así que a este paso no vas a alcanzar la meta. Necesitarías reducir "
                "gastos o aumentar ingresos."
            )
        elif monto_objetivo > 0:
            fecha = resultado["fecha_estimada"]
            fecha_texto = f"{MESES_ES[fecha.month]} {fecha.year}"
            st.success(
                f"A tu ritmo actual, vas a juntar ${monto_objetivo:,.0f} en aproximadamente "
                f"**{resultado['meses_necesarios']} mes(es)** (alrededor de {fecha_texto})."
            )

        if meses_deseados and monto_objetivo > 0:
            necesario = resultado["ahorro_necesario_mensual"]
            diferencia = resultado["diferencia_mensual"]
            st.markdown(
                f"Para lograrlo en **{meses_deseados} mes(es)**, necesitarías ahorrar "
                f"**${necesario:,.0f} por mes**."
            )
            if diferencia > 0:
                st.info(
                    f"Eso es ${diferencia:,.0f} más de lo que venís ahorrando en promedio — "
                    "tendrías que ajustar gastos o sumar ingresos."
                )
            else:
                st.success(f"¡Ya vas a un ritmo suficiente! Estás {abs(diferencia):,.0f} por arriba de lo necesario por mes.")

with tab_movimientos:
    st.caption("Movimientos del período seleccionado. Podés corregir la categoría de cualquiera.")
    df_periodo = df_movimientos[df_movimientos["periodo"] == periodo_seleccionado].copy()
    categorias_existentes = sorted(
        set(df_movimientos["categoria"]) | set(REGLAS_CATEGORIAS.keys())
        | {"Ingresos", "Sin clasificar", "Movimiento interno"}
    )

    with st.container(border=True):
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
            st.success("Categorías actualizadas. Descargá el CSV corregido abajo para no perder el cambio.")

        csv_actualizado = df_movimientos.drop(columns=["mes", "año", "periodo", "tipo"]).to_csv(index=False)
        st.download_button(
            "⬇️ Descargar CSV con las categorías corregidas",
            data=csv_actualizado,
            file_name="movimientos_corregidos.csv",
            mime="text/csv",
        )
