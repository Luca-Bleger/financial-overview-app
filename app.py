from pathlib import Path

import pandas as pd
import streamlit as st

from data import (
    FREQ_POR_GRANULARIDAD, MESES_ES, REGLAS_CATEGORIAS, aplicar_correcciones,
    calcular_variacion, clave_movimiento, construir_movimientos,
    detectar_gastos_fijos, gastos_categoria_por_mes, gastos_por_categoria,
    leer_archivo_robusto, mapeo_fijo_pdf_mercadopago, periodo_anterior_de,
    proyectar_ahorro, resumen_por_granularidad, resumen_por_periodo,
    sin_clasificar_frecuentes, sugerencias_de_mapeo,
)
from charts import (
    grafico_categorias_tiempo, grafico_comparacion_meses, grafico_donut,
    grafico_evolucion, grafico_tasa_ahorro, grafico_top_gastos,
)
from insights import generar_insights
from preguntas import PREGUNTAS_SUGERIDAS, responder as responder_pregunta
import db

st.set_page_config(
    page_title="Financial Overview",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    /* Letra más grande en toda la app: al ser el tamaño base (rem), todo lo
       que ya está definido en rem (botones, métricas, títulos) crece con
       esto también. Streamlit por default pone el texto de párrafo a
       0.875rem (más chico que el root) — se sobreescribe puntualmente
       abajo para que captions, textos de ayuda y etiquetas también se
       vean grandes, no solo lo que ya estaba en rem. */
    html { font-size: 20px; }
    /* Tipografía consistente en toda la app — sin esto, algunos elementos
       (como las flechitas de variación en los KPIs) podían caer en una
       fuente de respaldo distinta al resto y desentonar visualmente. */
    html, body, [class*="css"], div[data-testid="stMetricDelta"] {
        font-family: "Source Sans Pro", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
    }
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p,
    [data-testid="stWidgetLabel"] p,
    .stTabs [data-baseweb="tab"] p,
    [data-testid="stChatMessageContent"] p {
        font-size: 1.05rem !important;
    }
    small { font-size: 1rem !important; }

    .block-container { padding-top: 2rem; max-width: 1600px; animation: fadeSlideUp 0.5s ease-out; }

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
        border-left: 5px solid #67D2D0;
        border-radius: 10px;
        padding: 24px 26px;
        transition: border-color 0.2s ease, transform 0.2s ease;
    }
    div[data-testid="stMetric"]:hover {
        border-color: #67D2D0;
        transform: translateY(-2px);
    }
    div[data-testid="stMetricLabel"] { color: #8FA1BC; font-size: 1.15rem; }
    div[data-testid="stMetricValue"] { font-size: 2.7rem !important; font-weight: 800; }
    div[data-testid="stMetricDelta"] { font-size: 1.15rem !important; }

    /* Un color distinto de borde izquierdo por KPI (Ingresos/Gastos/Saldo/
       Tasa de ahorro), para que se distingan de un vistazo en vez de ser
       cuatro tarjetas idénticas. */
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(1) div[data-testid="stMetric"] {
        border-left-color: #8B95F6 !important;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(2) div[data-testid="stMetric"] {
        border-left-color: #FF8194 !important;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(3) div[data-testid="stMetric"] {
        border-left-color: #67D2D0 !important;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(4) div[data-testid="stMetric"] {
        border-left-color: #FFAB5C !important;
    }

    /* Títulos de sección (##### dentro de las tarjetas): un poco más
       grandes que el default de Streamlit para que se sientan como
       secciones reales de un dashboard, no subtítulos menores. */
    div[data-testid="stVerticalBlockBorderWrapper"] h5 {
        font-size: 1.3rem !important;
    }

    /* Consejos (pestaña Consejos): mismo lenguaje visual que las tarjetas,
       con un realce al pasar el mouse para que se sientan "presionables". */
    div[data-testid="stExpander"] {
        background-color: #152033;
        border-color: #263752 !important;
        border-radius: 12px !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
        margin-bottom: 8px;
    }
    div[data-testid="stExpander"]:hover {
        border-color: #67D2D0 !important;
        box-shadow: 0 6px 18px rgba(103, 210, 208, 0.10);
    }
    div[data-testid="stExpander"] summary {
        font-size: 1.05rem;
    }

    /* Inputs numéricos (proyección de ahorro): letra más grande, más fácil
       de leer en celular. */
    div[data-testid="stNumberInput"] input {
        font-size: 1.3rem !important;
        font-weight: 600;
    }
    div[data-testid="stNumberInput"] label p {
        font-size: 1rem !important;
    }

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

    /* Botones: efecto de elevación suave al pasar el mouse/tocar, y letra
       más grande — sobre todo el CTA principal (type="primary"). */
    div[data-testid="stButton"] button {
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        font-size: 1.05rem;
        padding: 0.6rem 1.1rem;
    }
    div[data-testid="stButton"] button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
    }
    div[data-testid="stButton"] button[kind="primary"] {
        font-size: 1.75rem;
        font-weight: 800;
        padding: 1rem 1.4rem;
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

    /* El degradado de texto (background-clip:text + text-fill-color
       transparent) rompe el color de los emojis si están adentro del mismo
       elemento — el emoji queda "hueco"/sin color en vez de mostrarse a
       todo color. Por eso el degradado va en un <span> aparte que envuelve
       solo las palabras, y el emoji queda afuera con su color normal. */
    .hero-titulo {
        font-size: 2.6rem;
        font-weight: 800;
        margin-bottom: 0;
    }
    .hero-titulo-texto {
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
    .icono-flotante.i1 { top: 10%; left: 9%; animation-delay: 0s; }
    .icono-flotante.i2 { top: 16%; right: 11%; animation-delay: 1s; font-size: 2.6rem; }
    .icono-flotante.i3 { bottom: 22%; left: 13%; animation-delay: 2s; }
    .icono-flotante.i4 { bottom: 12%; right: 7%; animation-delay: 0.6s; font-size: 2.8rem; }
    .icono-flotante.i5 { top: 44%; left: 2%; animation-delay: 1.6s; font-size: 1.7rem; }
    .icono-flotante.i6 { top: 6%; left: 42%; animation-delay: 2.4s; font-size: 1.8rem; }
    .icono-flotante.i7 { bottom: 8%; left: 40%; animation-delay: 0.9s; font-size: 1.6rem; }
    .icono-flotante.i8 { top: 50%; right: 2%; animation-delay: 1.3s; font-size: 2rem; }
    .icono-flotante.i9 { bottom: 4%; left: 22%; animation-delay: 1.8s; font-size: 1.5rem; }
    .icono-flotante.i10 { bottom: 6%; right: 20%; animation-delay: 0.4s; font-size: 1.9rem; }
    .icono-flotante.i11 { top: 30%; left: 20%; animation-delay: 2.2s; font-size: 1.4rem; }
    .icono-flotante.i12 { top: 26%; right: 22%; animation-delay: 0.2s; font-size: 1.5rem; }
    .icono-flotante.i13 { top: 60%; left: 8%; animation-delay: 2.6s; font-size: 1.6rem; }
    .icono-flotante.i14 { top: 62%; right: 9%; animation-delay: 1.1s; font-size: 1.7rem; }
    @keyframes flotar-icono {
        0%, 100% { transform: translateY(0) rotate(0deg); }
        50% { transform: translateY(-14px) rotate(6deg); }
    }
    .portada-titulo {
        font-size: 4.2rem;
        line-height: 1.05;
        font-weight: 800;
        margin-bottom: 4px;
        background: linear-gradient(90deg, #F8FAFC 0%, #8FA1BC 60%, #67D2D0 100%);
        background-size: 200% 100%;
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: brillo 4s ease-in-out infinite;
        z-index: 1;
        position: relative;
    }
    .portada-tagline {
        color: #CBD5E1;
        font-size: 1.2rem;
        max-width: 560px;
        margin: 20px auto 8px auto;
        z-index: 1;
        position: relative;
    }
    @media (max-width: 640px) {
        .portada-titulo { font-size: 2.6rem; }
        .portada-tagline { font-size: 1.05rem; }
        .icono-flotante { font-size: 1.4rem !important; }
    }

    /* Franja de features debajo del botón: para que la portada no se sienta
       vacía por debajo del "Comenzar", y para reforzar en un vistazo qué
       hace la app. */
    .portada-features {
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        gap: 14px;
        margin-top: 44px;
        max-width: 780px;
        z-index: 1;
        position: relative;
    }
    .portada-feature-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 6px;
        width: 150px;
        padding: 16px 12px;
        border-radius: 14px;
        background: rgba(21, 32, 51, 0.6);
        border: 1px solid #263752;
        backdrop-filter: blur(2px);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .portada-feature-item:hover {
        transform: translateY(-3px);
        border-color: #67D2D0;
    }
    .portada-feature-item .icono {
        font-size: 1.6rem;
    }
    .portada-feature-item .texto {
        font-size: 0.85rem;
        color: #9FB4CE;
        font-weight: 600;
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
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None


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
                <span class="icono-flotante i6">💵</span>
                <span class="icono-flotante i7">🪙</span>
                <span class="icono-flotante i8">🧾</span>
                <span class="icono-flotante i9">📉</span>
                <span class="icono-flotante i10">💹</span>
                <span class="icono-flotante i11">🧮</span>
                <span class="icono-flotante i12">💲</span>
                <span class="icono-flotante i13">🏧</span>
                <span class="icono-flotante i14">📱</span>
            </div>
            <div class="portada-titulo">Financial<br/>Overview</div>
            <div class="hero-accent" style="margin-left:auto;margin-right:auto;"></div>
            <div class="portada-tagline">
                Convertí tus movimientos en decisiones: cargá un resumen y en segundos vas a
                ver a dónde va cada peso, qué podés mejorar y cuánto te falta para tu próxima meta.
            </div>
        </div>
    """, unsafe_allow_html=True)

    _, col_centro, _ = st.columns([1, 1.8, 1])
    with col_centro:
        if st.button("Comenzar →", width="stretch", type="primary", key="btn_portada"):
            st.session_state.vista = "auth"
            st.rerun()

    st.markdown("""
        <div class="portada-features">
            <div class="portada-feature-item">
                <span class="icono">🏦</span>
                <span class="texto">Cualquier banco</span>
            </div>
            <div class="portada-feature-item">
                <span class="icono">⚡</span>
                <span class="texto">Carga rápida</span>
            </div>
            <div class="portada-feature-item">
                <span class="icono">🔒</span>
                <span class="texto">Tus datos, tu cuenta</span>
            </div>
            <div class="portada-feature-item">
                <span class="icono">🎯</span>
                <span class="texto">Metas y proyecciones</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.stop()


# =========================================================
# LOGIN / REGISTRO: primero la cuenta, así lo que subas después ya se
# puede guardar y acumular desde el arranque.
# =========================================================

if st.session_state.vista == "auth":
    st.markdown("#### Iniciá sesión o creá tu cuenta")
    st.caption(
        "Cada mes que subas se suma a tu historial — así vas a poder ver la evolución completa "
        "con el tiempo, no solo el último archivo."
    )

    tab_login, tab_registro = st.tabs(["Iniciar sesión", "Crear cuenta"])

    with tab_login:
        with st.form("form_login"):
            email_login = st.text_input("Email")
            pass_login = st.text_input("Contraseña", type="password")
            enviado_login = st.form_submit_button("Iniciar sesión", type="primary")
        if enviado_login:
            try:
                resp = db.iniciar_sesion(email_login, pass_login)
                st.session_state.auth_user = {"id": resp.user.id, "email": resp.user.email}
                st.session_state.vista = "inicio"
                st.rerun()
            except Exception as e:
                mensaje = str(e)
                if "Email not confirmed" in mensaje:
                    st.error(
                        "Todavía no confirmaste tu email — revisá tu casilla (y la carpeta de "
                        "spam) y tocá el enlace de confirmación antes de iniciar sesión."
                    )
                elif "Invalid login credentials" in mensaje:
                    st.error("Email o contraseña incorrectos.")
                else:
                    st.error(f"No pude iniciar sesión: {mensaje}")

    with tab_registro:
        with st.form("form_registro"):
            email_registro = st.text_input("Email", key="email_registro")
            pass_registro = st.text_input("Contraseña (mínimo 6 caracteres)", type="password", key="pass_registro")
            enviado_registro = st.form_submit_button("Crear cuenta", type="primary")
        if enviado_registro:
            try:
                resp = db.registrarse(email_registro, pass_registro)
                if resp.session is not None:
                    st.session_state.auth_user = {"id": resp.user.id, "email": resp.user.email}
                    st.session_state.vista = "inicio"
                    st.rerun()
                else:
                    st.success(
                        "Cuenta creada — revisá tu email para confirmarla y después iniciá sesión "
                        "en la pestaña de al lado."
                    )
            except Exception as e:
                st.error(f"No pude crear la cuenta: {e}")

    st.markdown("---")
    col_atras, col_demo = st.columns(2)
    with col_atras:
        if st.button("← Volver", width="stretch"):
            st.session_state.vista = "portada"
            st.rerun()
    with col_demo:
        if st.button("Prefiero probar sin cuenta primero", width="stretch"):
            st.session_state.vista = "cargar"
            st.session_state.usar_ejemplo = True
            st.rerun()

    st.stop()


# =========================================================
# PANTALLA INICIAL: elegir qué querés hacer antes de subir nada
# =========================================================

if st.session_state.vista == "inicio":
    st.markdown("""
        <div class="hero-wrap">
            <div class="hero-fondo"></div>
            <div class="hero-titulo">💰 <span class="hero-titulo-texto">Financial Overview</span></div>
            <div class="hero-accent"></div>
            <div class="hero-subtitulo">Tu copiloto financiero: subí un resumen y en segundos tenés
                gráficos, categorías, proyecciones de ahorro y respuestas a tus preguntas.</div>
            <div class="badge-row">
                <span class="badge-pill">📊 +10 gráficos y análisis</span>
                <span class="badge-pill">🎯 Proyectá tus metas de ahorro</span>
                <span class="badge-pill">💬 Preguntale a tus datos</span>
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
    st.session_state.subvista_planificacion = False
    st.rerun()

usuario_id = None
archivo = None

if st.session_state.usar_ejemplo:
    st.info("📎 Estás viendo datos de ejemplo, no los tuyos. Tocá \"← Volver al inicio\" cuando quieras subir tu propio archivo.")
    df_raw = pd.read_csv(Path(__file__).parent / "movimientos_ejemplo_2.csv")
    tipo_fuente = "tabla"
    hay_archivo_nuevo = True
else:
    # El login/registro ahora pasa antes, en la pantalla "auth" — llegar
    # hasta acá sin sesión solo puede pasar por una navegación rara (por
    # ejemplo, volver atrás en el navegador). En ese caso, se manda de
    # vuelta a esa pantalla en vez de duplicar el formulario acá.
    if st.session_state.auth_user is None:
        st.session_state.vista = "auth"
        st.rerun()

    usuario_id = st.session_state.auth_user["id"]
    col_cuenta, col_salir = st.columns([4, 1])
    with col_cuenta:
        st.caption(f"📧 Conectado como **{st.session_state.auth_user['email']}**.")
    with col_salir:
        if st.button("Cerrar sesión"):
            db.cerrar_sesion()
            st.session_state.auth_user = None
            st.rerun()

    archivo = st.file_uploader(
        "Subí un resumen nuevo para sumarlo a tu historial (CSV, Excel o PDF de Mercado Pago) "
        "— opcional si ya tenés datos guardados",
        type=["csv", "xlsx", "xls", "pdf"],
        help="Funciona con resúmenes de distintos bancos, en CSV o Excel: en el siguiente paso "
             "vas a poder indicar qué columna es cuál. Si tu celular guardó el archivo como "
             ".xlsx, también anda. Los PDF de \"Resumen de cuenta\" de Mercado Pago se reconocen "
             "automáticamente. Los movimientos que ya tenías guardados no se duplican.",
    )
    hay_archivo_nuevo = archivo is not None
    if hay_archivo_nuevo:
        try:
            with st.spinner("Leyendo tu archivo..."):
                df_raw, tipo_fuente = leer_archivo_robusto(archivo)
        except Exception as e:
            st.error(f"No pude leer el archivo: {e}")
            st.stop()


# =========================================================
# MAPEO DE COLUMNAS (los CSV de distintos bancos no vienen todos igual) —
# solo corre si hay un archivo nuevo para procesar este turno.
# =========================================================

if hay_archivo_nuevo:
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
        df_nuevo, filas_invalidas = construir_movimientos(
            df_raw, mapeo, modo_importe, formato_numero, formato_fecha
        )
    except Exception as e:
        st.error(f"No pude procesar el archivo con este mapeo: {e}")
        st.stop()

    if df_nuevo.empty:
        st.error("No quedó ningún movimiento válido con este mapeo de columnas. Revisá la configuración de arriba.")
        st.stop()

    if filas_invalidas > 0:
        st.warning(f"Se descartaron {filas_invalidas} fila(s) porque no se pudo interpretar la fecha o el importe.")

    if usuario_id is not None:
        cantidad = db.guardar_movimientos(usuario_id, df_nuevo, fuente=archivo.name if archivo else "ejemplo")
        st.success(f"Se guardaron {cantidad} movimiento(s) en tu historial (los que ya tenías no se duplican).")

st.markdown("---")


# =========================================================
# DATOS A USAR: historial acumulado desde la base (usuarios con cuenta) o
# solo el archivo de ejemplo con correcciones de sesión (demo).
# =========================================================

if usuario_id is not None:
    df_movimientos = db.cargar_movimientos(usuario_id)
    if df_movimientos.empty:
        st.info("Todavía no tenés movimientos guardados. Subí tu primer resumen más arriba para empezar.")
        st.stop()
else:
    df_movimientos = df_nuevo
    # Correcciones de categoría hechas a mano en la pestaña Movimientos: se
    # reaplican acá, ANTES de calcular KPIs/gráficos/resumen, para que todo
    # el dashboard se actualice al instante apenas se corrige algo. Solo
    # aplica al modo demo — con cuenta, la corrección se guarda directo en
    # la base (ver pestaña Movimientos).
    if "correcciones_categoria" not in st.session_state:
        st.session_state.correcciones_categoria = {}
    df_movimientos = aplicar_correcciones(df_movimientos, st.session_state.correcciones_categoria)


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
# PLANIFICACIÓN: pantalla aparte del dashboard con pestañas — usa los
# mismos movimientos ya cargados, pero vive en su propio espacio en vez de
# competir por lugar con Resumen/Categorías/etc.
# =========================================================

if st.session_state.get("subvista_planificacion", False):
    if st.button("← Volver al dashboard"):
        st.session_state.subvista_planificacion = False
        st.rerun()

    st.markdown("## 📅 Planificación financiera")
    st.caption(
        "Pantalla aparte del resto del dashboard, pensada para planificar — usa los mismos "
        "movimientos que ya cargaste. Cálculo directo, sin IA."
    )

    gastos_fijos = detectar_gastos_fijos(df_movimientos)
    total_fijos = 0.0
    descripciones_fijas = set()

    with st.container(border=True):
        st.markdown("##### 🔒 Tus gastos fijos detectados")
        if gastos_fijos.empty:
            st.caption(
                "Todavía no detecto gastos que se repitan en 2 o más meses distintos — a medida "
                "que cargues más meses, los vamos a poder identificar acá."
            )
        else:
            st.caption(
                "Movimientos con la misma descripción en 2 o más meses — la señal de un gasto "
                "recurrente (alquiler, cuota, suscripción). Destildá el que no corresponda."
            )
            for _, fila in gastos_fijos.iterrows():
                incluido = st.checkbox(
                    f"**{fila['descripcion']}** ({fila['categoria']}) — "
                    f"${fila['promedio']:,.0f}/mes, visto en {fila['meses']:.0f} meses",
                    value=True, key=f"fijo_{fila['descripcion']}",
                )
                if incluido:
                    total_fijos += fila["promedio"]
                    descripciones_fijas.add(fila["descripcion"])
            st.markdown(f"**Total de gastos fijos: ${total_fijos:,.0f} por mes**")

    with st.container(border=True):
        st.markdown("##### 📅 Planificar el próximo mes")
        st.caption(
            "Los gastos fijos ya se descuentan solos. Ingresá tu ingreso esperado y cuánto "
            "esperás gastar en el resto (variable), y te mostramos cómo se distribuiría según tu "
            "historial."
        )

        promedio_ingreso_historico = resumen["Ingreso"].mean() if not resumen.empty else 0.0
        df_variable_historico = df_solo_gastos[~df_solo_gastos["descripcion"].isin(descripciones_fijas)]
        gasto_variable_historico_mensual = (
            df_variable_historico.groupby("periodo")["importe"].sum().mean()
            if not df_variable_historico.empty else 0.0
        )

        col_ing_plan, col_var_plan = st.columns(2)
        with col_ing_plan:
            ingreso_plan = st.number_input(
                "Ingresos esperados este mes ($)", min_value=0.0, step=10000.0,
                value=float(round(promedio_ingreso_historico, -2)), key="ingreso_plan",
            )
        with col_var_plan:
            gasto_variable_plan = st.number_input(
                "Gastos variables esperados, sin contar los fijos ($)", min_value=0.0, step=10000.0,
                value=float(round(gasto_variable_historico_mensual, -2)), key="gasto_variable_plan",
            )

        st.metric("Gastos fijos (detectados automáticamente)", f"${total_fijos:,.0f}")

        distribucion_historica = df_variable_historico.groupby("categoria")["importe"].sum()
        distribucion_historica = distribucion_historica[distribucion_historica > 0].sort_values(ascending=False)
        total_historico_variable = distribucion_historica.sum()

        if total_historico_variable > 0 and gasto_variable_plan > 0:
            st.markdown(f"Así se distribuirían tus **${gasto_variable_plan:,.0f}** de gastos variables, según tu historial:")
            for categoria, monto_historico in distribucion_historica.items():
                porcentaje = monto_historico / total_historico_variable
                monto_sugerido = porcentaje * gasto_variable_plan
                st.progress(min(porcentaje, 1.0), text=f"{categoria} — ${monto_sugerido:,.0f} ({porcentaje * 100:.0f}%)")

        saldo_plan = ingreso_plan - total_fijos - gasto_variable_plan
        tasa_plan = (saldo_plan / ingreso_plan * 100) if ingreso_plan else 0
        if saldo_plan >= 0:
            st.success(
                f"Con estos números (fijos + variables), terminarías el mes con "
                f"**${saldo_plan:,.0f}** de saldo (tasa de ahorro proyectada: {tasa_plan:.1f}%)."
            )
        else:
            st.warning(
                f"Con estos números, terminarías el mes en **-${abs(saldo_plan):,.0f}** — entre "
                "gastos fijos y variables superás tus ingresos esperados."
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

    with st.container(border=True):
        st.markdown("##### 📚 Dónde suele guardarse la plata que se ahorra")
        st.caption(
            "Información general para conocer las opciones más comunes — **no es una "
            "recomendación personalizada** (no somos asesores financieros). Antes de decidir, "
            "comparalo con tu situación y, si hace falta, consultá a un profesional matriculado."
        )
        col_opt1, col_opt2, col_opt3 = st.columns(3)
        with col_opt1:
            st.markdown("**🏦 Plazo fijo**")
            st.caption(
                "Depositás un monto por un plazo fijo (30 días o más) a cambio de un interés "
                "pactado de antemano. Bajo riesgo, pero el dinero queda inmovilizado hasta el "
                "vencimiento."
            )
        with col_opt2:
            st.markdown("**📈 Fondo común de inversión**")
            st.caption(
                "Varias personas ponen su dinero en un fondo administrado por una sociedad "
                "gerente, que invierte en distintos activos. Más liquidez que un plazo fijo, "
                "pero el rendimiento no está garantizado."
            )
        with col_opt3:
            st.markdown("**💵 Dólares u otra moneda**")
            st.caption(
                "Convertir parte del ahorro a otra moneda para cubrirse de la devaluación del "
                "peso. No genera renta por sí solo, y tiene el riesgo de la cotización."
            )

    st.stop()

if st.button("📅 Ir a Planificación financiera →"):
    st.session_state.subvista_planificacion = True
    st.rerun()


# =========================================================
# SECCIONES (apartados)
# =========================================================

tab_resumen, tab_categorias, tab_consejos, tab_preguntas, tab_movimientos = st.tabs(
    ["📈 Resumen", "🏷️ Categorías", "🧠 Consejos", "💬 Preguntas", "📋 Movimientos"]
)

with tab_resumen:
    with st.container(border=True):
        st.markdown("##### 📈 Evolución financiera")
        st.caption("Usa todos los meses que cargaste, sin importar el período elegido arriba.")

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
        st.caption(f"Mes seleccionado: **{nombre_seleccionado}**.")
        gastos_cat_actual = gastos_por_categoria(df_solo_gastos, periodo_seleccionado)
        st.plotly_chart(grafico_donut(gastos_cat_actual), width="stretch")

    with st.container(border=True):
        st.markdown("##### 🔝 Mayores gastos individuales del mes")
        st.caption(f"Mes seleccionado: **{nombre_seleccionado}**.")
        st.plotly_chart(grafico_top_gastos(df_solo_gastos, periodo_seleccionado), width="stretch")

    with st.container(border=True):
        st.markdown("##### 🆚 Comparar meses")
        st.caption("Elegí qué meses poner uno al lado del otro.")
        opciones_comparar = list(opciones_periodo.keys())
        default_comparar = opciones_comparar[-2:] if len(opciones_comparar) >= 2 else opciones_comparar
        meses_a_comparar = st.multiselect(
            "Meses a comparar", opciones_comparar, default=default_comparar, key="meses_comparar",
        )
        if len(meses_a_comparar) < 2:
            st.info("Elegí al menos 2 meses para comparar.")
        else:
            periodos_comparar = sorted(opciones_periodo[nombre] for nombre in meses_a_comparar)
            st.plotly_chart(grafico_comparacion_meses(resumen.loc[periodos_comparar]), width="stretch")

with tab_categorias:
    cat_mes = gastos_categoria_por_mes(df_solo_gastos)
    with st.container(border=True):
        st.markdown("##### 📊 Evolución de gastos por categoría")
        st.caption("Todos los meses cargados.")
        st.plotly_chart(grafico_categorias_tiempo(cat_mes), width="stretch")
    with st.container(border=True):
        st.markdown("##### 💹 Tasa de ahorro por mes")
        st.caption("Todos los meses cargados.")
        st.plotly_chart(grafico_tasa_ahorro(resumen), width="stretch")

with tab_consejos:
    st.caption(
        "Generados automáticamente a partir de tus datos — sin IA externa, sin costo. "
        "Tocá cualquiera para ver más detalle."
    )
    insights = generar_insights(df_movimientos, df_solo_gastos, resumen, periodo_seleccionado)
    icono_por_tipo = {"positivo": "✅", "alerta": "⚠️", "info": "ℹ️"}
    for item in insights:
        icono = icono_por_tipo[item["tipo"]]
        with st.expander(f"{icono} {item['mensaje']}"):
            st.markdown(item["detalle"])

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

with tab_movimientos:
    st.caption(
        "Movimientos del período seleccionado. Corregí la categoría de cualquiera y se actualiza "
        "al instante en todo el dashboard — no hace falta descargar ni volver a subir nada."
    )
    categorias_existentes = sorted(
        set(df_movimientos["categoria"]) | set(REGLAS_CATEGORIAS.keys())
        | {"Ingresos", "Sin clasificar", "Movimiento interno"}
    )

    # --- Clasificar lo que falta: todos los "Sin clasificar" juntos, de
    # cualquier mes, en un solo lugar — para ir limpiándolos todos de una
    # sentada en vez de tener que cambiar de mes uno por uno. Cada
    # corrección se guarda igual que en la tabla de abajo (a la base si hay
    # cuenta, o a la sesión en modo demo), así que actualiza todo el
    # dashboard al instante.
    df_sin_clasificar = df_movimientos[df_movimientos["categoria"] == "Sin clasificar"].sort_values("fecha").reset_index(drop=True)
    if not df_sin_clasificar.empty:
        with st.container(border=True):
            st.markdown("##### 🗂️ Clasificar lo que falta")
            st.caption(
                f"Tenés **{len(df_sin_clasificar)}** movimiento(s) sin clasificar, de todos los meses "
                "juntos acá. Asignales categoría y se actualiza al instante en todos los gráficos y KPIs."
            )
            editado_sc = st.data_editor(
                df_sin_clasificar[["fecha", "descripcion", "importe", "categoria"]],
                column_config={
                    "categoria": st.column_config.SelectboxColumn("categoria", options=categorias_existentes),
                    "importe": st.column_config.NumberColumn("importe", format="$%.0f"),
                },
                disabled=["fecha", "descripcion", "importe"],
                width="stretch",
                hide_index=True,
                key="editor_sin_clasificar",
            )
            cambios_sc = editado_sc["categoria"] != df_sin_clasificar["categoria"]
            if cambios_sc.any():
                if usuario_id is not None:
                    for id_mov, nueva_categoria in zip(df_sin_clasificar[cambios_sc]["id"], editado_sc["categoria"][cambios_sc]):
                        db.actualizar_categoria(usuario_id, id_mov, nueva_categoria)
                else:
                    claves_cambiadas_sc = df_sin_clasificar[cambios_sc].apply(clave_movimiento, axis=1)
                    for clave, nueva_categoria in zip(claves_cambiadas_sc, editado_sc["categoria"][cambios_sc]):
                        st.session_state.correcciones_categoria[clave] = nueva_categoria
                st.rerun()

    filtro_categoria = st.selectbox(
        "Filtrar por categoría", ["Todas"] + categorias_existentes, key="filtro_categoria_movimientos",
    )

    df_periodo = df_movimientos[df_movimientos["periodo"] == periodo_seleccionado].copy()
    if filtro_categoria != "Todas":
        df_periodo = df_periodo[df_periodo["categoria"] == filtro_categoria]
    df_periodo = df_periodo.reset_index(drop=True)

    with st.container(border=True):
        if df_periodo.empty:
            st.caption("No hay movimientos con ese filtro en este período.")
        else:
            editado = st.data_editor(
                df_periodo[["fecha", "descripcion", "importe", "categoria"]],
                column_config={
                    "categoria": st.column_config.SelectboxColumn("categoria", options=categorias_existentes),
                    "importe": st.column_config.NumberColumn("importe", format="$%.0f"),
                },
                disabled=["fecha", "descripcion", "importe"],
                width="stretch",
                hide_index=True,
                key=f"editor_{periodo_seleccionado}_{filtro_categoria}",
            )

            cambios = editado["categoria"] != df_periodo["categoria"]
            if cambios.any():
                if usuario_id is not None:
                    for id_mov, nueva_categoria in zip(df_periodo[cambios]["id"], editado["categoria"][cambios]):
                        db.actualizar_categoria(usuario_id, id_mov, nueva_categoria)
                else:
                    claves_cambiadas = df_periodo[cambios].apply(clave_movimiento, axis=1)
                    for clave, nueva_categoria in zip(claves_cambiadas, editado["categoria"][cambios]):
                        st.session_state.correcciones_categoria[clave] = nueva_categoria
                st.rerun()

        columnas_export = [c for c in ["mes", "año", "periodo", "tipo", "id"] if c in df_movimientos.columns]
        csv_actualizado = df_movimientos.drop(columns=columnas_export).to_csv(index=False)
        st.download_button(
            "⬇️ Descargar CSV con todas las categorías corregidas",
            data=csv_actualizado,
            file_name="movimientos_corregidos.csv",
            mime="text/csv",
        )

    frecuentes = sin_clasificar_frecuentes(df_movimientos)
    if not frecuentes.empty:
        with st.container(border=True):
            st.markdown("##### ⚠️ Sin clasificar, y se repiten")
            st.caption(
                "Estas descripciones aparecen varias veces sin categoría — clasificarlas una vez "
                "ordena de golpe todas sus apariciones, en cualquier mes."
            )
            for _, fila in frecuentes.head(8).iterrows():
                col_desc, col_cat, col_btn = st.columns([3, 2, 1])
                col_desc.markdown(f"**{fila['descripcion']}**  \n{fila['cantidad']:.0f} veces · ${fila['total']:,.0f} en total")
                nueva_cat = col_cat.selectbox(
                    "Categoría", categorias_existentes, key=f"masiva_cat_{fila['descripcion']}",
                    label_visibility="collapsed",
                )
                if col_btn.button("Aplicar", key=f"masiva_btn_{fila['descripcion']}"):
                    coincidencias = df_movimientos[df_movimientos["descripcion"] == fila["descripcion"]]
                    if usuario_id is not None:
                        for id_mov in coincidencias["id"]:
                            db.actualizar_categoria(usuario_id, id_mov, nueva_cat)
                    else:
                        for clave in coincidencias.apply(clave_movimiento, axis=1):
                            st.session_state.correcciones_categoria[clave] = nueva_cat
                    st.rerun()
