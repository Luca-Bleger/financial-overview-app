"""Procesamiento de datos: ingesta flexible de CSV + categorización.

Los resúmenes/extractos que suba cada usuario NO van a tener siempre la
misma estructura de columnas (distintos bancos, distintos formatos de
número, débito/crédito separado o un importe único con signo). Por eso acá
no asumimos nombres de columna fijos: el usuario mapea sus columnas reales
a los campos que necesitamos, y esta capa se encarga de normalizarlas.
"""

import math
import unicodedata

import numpy as np
import pandas as pd

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

REGLAS_CATEGORIAS = {
    # Patrones de ingreso/movimiento: se revisan primero porque son prefijos
    # de descripción, no nombres de comercio, y conviene que ganen por sobre
    # cualquier coincidencia casual de palabra clave más abajo.
    "Sueldo": ["SUELDO", "HABERES", "AGUINALDO", "NOMINA"],
    "Rendimientos": ["RENDIMIENTOS"],
    "Devoluciones": ["DEVOLUCION DE PAGO", "DEVOLUCIÓN DE PAGO", "REEMBOLSO"],
    "Transferencias": ["TRANSFERENCIA ENVIADA", "TRANSFERENCIA RECIBIDA"],
    # Pagos con QR: se separan del resto de compras porque agrupan comercios
    # muy variados (kioscos, ferias, changarines) bajo un mismo medio de
    # pago — conviene verlos aparte para detectar el gasto "efectivo digital"
    # del día a día, en vez de que se mezclen en "Sin clasificar".
    "Pagos con QR": ["PAGO QR", "COBRO QR", "COMPRA CON QR", " QR "],
    # ARCA (ex-AFIP): se separa de "Servicios" porque son pagos a un
    # organismo público (impuestos, monotributo), no un servicio contratado.
    "ARCA": ["PAGO DE SERVICIO ARCA", " ARCA", "ARCA ", "AFIP", "MONOTRIBUTO"],
    # Va antes que "Créditos y deudas" porque esa usa la palabra genérica
    # "CUOTA", que si no perdería contra "CUOTA SOCIAL" y la clasificaría mal.
    "Cuota social": ["CUOTA SOCIAL", "CLUB SOCIAL", "ASOCIACION CIVIL", "ASOCIACIÓN CIVIL"],
    # Categorías de gasto
    "Alimentación": [
        "DISCO", "COTO", "PEDIDOSYA", "SUPERMERCADO", "CARREFOUR", "DIA ", "JUMBO",
        "RAPPI", "ARCOS DORADOS", "BUENOS DIAS SUPERMERCADOS", "ALMACEN",
    ],
    "Entretenimiento": [
        "NETFLIX", "SPOTIFY", "HBO", "DISNEY", "YOUTUBE", "PRIME VIDEO", "CINE",
        "GOOGLE ONE", "OPERATORIA DE CINES", "OPENAI", "CHATGPT",
    ],
    "Suscripciones": [
        "SUSCRIPCION", "SUSCRIPCIÓN", "MEMBRESIA", "MEMBRESÍA", "ICLOUD",
        "AMAZON PRIME", "ADOBE", "CANVA", "XBOX", "PLAYSTATION PLUS",
    ],
    "Transporte": ["UBER", "CABIFY", "SUBE", "NAFTA", "YPF", "SHELL", "PEAJE", "ESTACIONAMIENTO"],
    "Salud": ["FARMACITY", "FARMACIA", "OSDE", "SWISS MEDICAL", "MEDIC"],
    "Gym / Deportes": [
        "GIMNASIO", "GYM ", "CROSSFIT", "PADEL", "MEGATLON", "SPORTCLUB", "CLUB DEPORTIVO",
    ],
    "Peluquería": ["PELUQUERIA", "PELUQUERÍA", "BARBERIA", "BARBERÍA", "ESTETICA", "ESTÉTICA"],
    "Ropa": ["ZARA", "H&M", "NIKE", "ADIDAS"],
    "Servicios": [
        "EDENOR", "EDESUR", "METROGAS", "AYSA", "TELECOM", "PERSONAL", "MOVISTAR", "CLARO",
    ],
    "Vivienda": ["ALQUILER", "EXPENSAS", "HIPOTECA"],
    "Créditos y deudas": ["CUOTA", "CREDITOS DE MERCADO PAGO", "CRÉDITOS DE MERCADO PAGO"],
}

# Movimientos que no son ingresos ni gastos reales: mover plata entre la
# cuenta y el "fondo" de Ahorro dentro de la misma billetera. Si se cuentan
# como ingreso/gasto, inflan artificialmente el dashboard (aparecen decenas
# de veces por mes). Se identifican y se excluyen del cálculo financiero,
# aunque siguen visibles en la tabla de movimientos para que quede claro
# a dónde fue esa plata.
PATRONES_MOVIMIENTO_INTERNO = [
    "DINERO RETIRADO AHORRO",
    "DINERO RESERVADO AHORRO",
    "DINERO RETIRADO DE AHORRO",
    "DINERO RESERVADO DE AHORRO",
]


def es_movimiento_interno(descripcion):
    d = str(descripcion).upper()
    return any(p in d for p in PATRONES_MOVIMIENTO_INTERNO)


def categorizar(descripcion, importe):
    if es_movimiento_interno(descripcion):
        return "Movimiento interno"

    descripcion_norm = str(descripcion).upper()

    for categoria, palabras_clave in REGLAS_CATEGORIAS.items():
        if any(palabra in descripcion_norm for palabra in palabras_clave):
            return categoria

    return "Ingresos" if importe > 0 else "Sin clasificar"


def determinar_tipo(descripcion, importe):
    if es_movimiento_interno(descripcion):
        return "Interno"
    return "Ingreso" if importe > 0 else "Gasto"


def calcular_variacion(actual, anterior):
    if anterior in (0, None):
        return None
    return ((actual - anterior) / abs(anterior)) * 100


# ---------------------------------------------------------------------
# INGESTA FLEXIBLE DE CSV
# ---------------------------------------------------------------------

def leer_archivo_robusto(archivo):
    """Lee el archivo subido: CSV, Excel (.xlsx/.xls) o PDF de Mercado Pago.

    Es común que un CSV termine convertido a Excel sin querer (por ejemplo,
    si se abrió con Google Sheets en el celular y se volvió a guardar), así
    que esta función detecta el tipo real de archivo en vez de asumir por
    la extensión.

    Devuelve (df, tipo_fuente). tipo_fuente es "pdf_mercadopago" cuando ya
    se reconoció y extrajo la estructura completa (fecha/descripcion/
    importe) sin necesidad de que el usuario mapee columnas, o "tabla" para
    CSV/Excel genéricos que sí necesitan el paso de mapeo.
    """

    nombre = getattr(archivo, "name", "") or ""

    archivo.seek(0)
    firma = archivo.read(5)
    archivo.seek(0)

    if nombre.lower().endswith(".pdf") or firma[:4] == b"%PDF":
        from pdf_mercadopago import extraer_movimientos_pdf

        df = extraer_movimientos_pdf(archivo)
        return df, "pdf_mercadopago"

    es_excel_por_nombre = nombre.lower().endswith((".xlsx", ".xls"))
    # Los .xlsx son en realidad un .zip (firma "PK\x03\x04"); los .xls viejos
    # (formato binario OLE) arrancan con "\xD0\xCF\x11\xE0".
    es_excel_por_contenido = firma[:2] == b"PK" or firma[:4] == b"\xd0\xcf\x11\xe0"

    if es_excel_por_nombre or es_excel_por_contenido:
        try:
            # Muchos bancos meten un par de filas de metadata (titular,
            # número de cuenta, período) ANTES de la fila real de
            # encabezados — sin detectar esto, esa fila de metadata se leía
            # como si fuera el encabezado y todo el mapeo salía mal.
            archivo.seek(0)
            vista_previa = pd.read_excel(archivo, header=None, nrows=15)
            lineas_vista = vista_previa.astype(str).agg(" ".join, axis=1).tolist()
            fila_encabezado = _detectar_fila_encabezado(lineas_vista)

            archivo.seek(0)
            return pd.read_excel(archivo, header=fila_encabezado), "tabla"
        except Exception as e:
            raise ValueError(
                f"El archivo parece ser Excel pero no pude leerlo. Detalle: {e}"
            )

    return _leer_csv_robusto(archivo), "tabla"


def mapeo_fijo_pdf_mercadopago():
    """El PDF de Mercado Pago ya se parsea con columnas fecha/descripcion/
    importe conocidas: no hace falta que el usuario mapee nada."""
    return {"fecha": "fecha", "descripcion": "descripcion", "categoria": None, "importe": "importe"}


_PALABRAS_FECHA = ["fecha", "date"]
_PALABRAS_DESCRIPCION = ["descripcion", "detalle", "concepto", "movimiento", "description"]
_PALABRAS_IMPORTE = ["importe", "monto", "amount", "valor", "debito", "credito", "debe", "haber"]


def _detectar_fila_encabezado(lineas, max_filas=15):
    """Bancos distintos exportan distinto: algunos meten un par de líneas de
    metadata (titular, número de cuenta, período) ANTES de la fila real de
    encabezados. Sin esto, esa fila de metadata se leía como si fuera el
    encabezado real y todo el mapeo de columnas salía mal. Busca, entre las
    primeras filas, cuál tiene más pinta de encabezado real (que mencione
    fecha + descripción + algún campo de importe), y devuelve su número de
    fila — 0 si ninguna se destaca, para no romper archivos que ya vienen
    bien formados desde la primera fila."""

    mejor_indice = 0
    mejor_puntaje = 0
    for i, linea in enumerate(lineas[:max_filas]):
        normalizada = _normalizar_texto(linea)
        puntaje = (
            any(p in normalizada for p in _PALABRAS_FECHA)
            + any(p in normalizada for p in _PALABRAS_DESCRIPCION)
            + any(p in normalizada for p in _PALABRAS_IMPORTE)
        )
        if puntaje > mejor_puntaje:
            mejor_puntaje = puntaje
            mejor_indice = i
    return mejor_indice if mejor_puntaje >= 2 else 0


def _leer_csv_robusto(archivo):
    """Intenta leer el CSV probando separadores y encodings comunes en
    exports bancarios (utf-8, latin-1, separado por coma o por punto y coma),
    saltando filas de metadata antes del encabezado real si las detecta."""

    archivo.seek(0)
    crudo = archivo.read()
    archivo.seek(0)

    texto = None
    for encoding in ("utf-8", "latin-1"):
        try:
            texto = crudo.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    fila_encabezado = _detectar_fila_encabezado(texto.splitlines()) if texto else 0

    intentos = [
        dict(sep=None, engine="python", encoding="utf-8"),
        dict(sep=None, engine="python", encoding="latin-1"),
        dict(sep=";", encoding="utf-8"),
        dict(sep=";", encoding="latin-1"),
    ]

    ultimo_error = None
    for opciones in intentos:
        try:
            archivo.seek(0)
            df = pd.read_csv(archivo, skiprows=fila_encabezado, **opciones)
            if df.shape[1] >= 2:
                return df
        except Exception as e:
            ultimo_error = e

    raise ValueError(f"No pude leer el archivo como CSV ni como Excel. Detalle: {ultimo_error}")


def _normalizar_texto(s):
    s = str(s).strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return s


def sugerir_columna(columnas, candidatos):
    """Heurística simple: busca la primera columna cuyo nombre normalizado
    contenga alguna de las palabras candidatas. Devuelve el índice o None."""

    normalizadas = [_normalizar_texto(c) for c in columnas]
    for candidato in candidatos:
        for i, nombre in enumerate(normalizadas):
            if candidato in nombre:
                return i
    return None


def sugerencias_de_mapeo(columnas):
    return {
        "fecha": sugerir_columna(columnas, ["fecha", "date"]),
        "descripcion": sugerir_columna(columnas, ["descripcion", "detalle", "concepto", "movimiento", "description"]),
        "importe": sugerir_columna(columnas, ["importe", "monto", "amount", "valor"]),
        "debito": sugerir_columna(columnas, ["debito", "debe", "egreso", "salida"]),
        "credito": sugerir_columna(columnas, ["credito", "haber", "ingreso", "entrada"]),
        "categoria": sugerir_columna(columnas, ["categoria", "category", "rubro"]),
    }


def _parsear_fecha(serie, formato_fecha):
    """Convierte la columna de fecha a datetime.

    Ojo: pandas con dayfirst=True puede interpretar mal fechas que ya vienen
    en formato ISO (AAAA-MM-DD), invirtiendo mes y día. Por eso, si la
    mayoría de los valores matchean un patrón ISO, se parsean directo sin
    aplicar dayfirst (que solo tiene sentido para fechas ambiguas tipo
    DD/MM/AAAA o MM/DD/AAAA).
    """

    texto = serie.astype(str).str.strip()
    parece_iso = texto.str.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}").fillna(False).mean() > 0.5

    if parece_iso:
        return pd.to_datetime(texto, errors="coerce")

    dayfirst = formato_fecha != "mes_primero"
    return pd.to_datetime(texto, dayfirst=dayfirst, errors="coerce")


def _parsear_numero(serie, formato):
    """formato: 'punto' -> 1234.56 | 'coma' -> 1.234,56"""

    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_numeric(serie, errors="coerce")

    texto = serie.astype(str).str.strip()
    texto = texto.str.replace(r"[^\d,.\-]", "", regex=True)

    if formato == "coma":
        texto = texto.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    else:
        texto = texto.str.replace(",", "", regex=False)

    return pd.to_numeric(texto, errors="coerce")


def construir_movimientos(df_raw, mapeo, modo_importe, formato_numero, formato_fecha):
    """Arma el df_movimientos estándar a partir del CSV crudo y el mapeo de
    columnas elegido por el usuario.

    mapeo: dict con claves 'fecha', 'descripcion', 'categoria' (nombres de
        columna reales del CSV, o None si no aplica) y, según modo_importe,
        'importe' o ('debito', 'credito').
    modo_importe: "unica" o "separado".
    formato_numero: "punto" o "coma".
    formato_fecha: "auto", "dia_primero" o "mes_primero".
    """

    df = pd.DataFrame()
    df["fecha_original"] = df_raw[mapeo["fecha"]]
    df["descripcion"] = df_raw[mapeo["descripcion"]].astype(str)

    if modo_importe == "unica":
        df["importe"] = _parsear_numero(df_raw[mapeo["importe"]], formato_numero)
    else:
        debito = _parsear_numero(df_raw[mapeo["debito"]], formato_numero).fillna(0)
        credito = _parsear_numero(df_raw[mapeo["credito"]], formato_numero).fillna(0)
        df["importe"] = credito - debito.abs()

    df["fecha"] = _parsear_fecha(df["fecha_original"], formato_fecha)

    filas_totales = len(df)
    df = df.dropna(subset=["fecha", "importe"])
    filas_invalidas = filas_totales - len(df)

    if mapeo.get("categoria"):
        df["categoria"] = df_raw.loc[df.index, mapeo["categoria"]]
    else:
        df["categoria"] = None

    sin_categoria = df["categoria"].isna() | (df["categoria"].astype(str).str.strip() == "")
    df.loc[sin_categoria, "categoria"] = df[sin_categoria].apply(
        lambda fila: categorizar(fila["descripcion"], fila["importe"]), axis=1
    )

    df = df.drop(columns=["fecha_original"])
    df = finalizar_movimientos(df)

    return df, filas_invalidas


def finalizar_movimientos(df):
    """Agrega las columnas derivadas (tipo/mes/año/periodo) y ordena por
    fecha. Es el mismo paso final tanto para movimientos recién parseados
    de un archivo como para movimientos recuperados de la base de datos
    (ver db.py), así ambos caminos terminan con el mismo formato."""
    df = df.copy()
    df["tipo"] = df.apply(lambda fila: determinar_tipo(fila["descripcion"], fila["importe"]), axis=1)
    df["mes"] = df["fecha"].dt.month
    df["año"] = df["fecha"].dt.year
    df["periodo"] = df["fecha"].dt.to_period("M")
    return df.sort_values("fecha").reset_index(drop=True)


# ---------------------------------------------------------------------
# AGREGACIONES
# ---------------------------------------------------------------------

def resumen_por_periodo(df_movimientos):
    resumen = df_movimientos.groupby(["periodo", "tipo"])["importe"].sum().unstack()
    resumen["Gasto"] = abs(resumen.get("Gasto", 0))
    resumen["Ingreso"] = resumen.get("Ingreso", 0)
    resumen["Saldo"] = resumen["Ingreso"] - resumen["Gasto"]
    return resumen.sort_index()


def periodo_anterior_de(periodos_disponibles, periodo_seleccionado):
    idx = periodos_disponibles.index(periodo_seleccionado)
    return periodos_disponibles[idx - 1] if idx > 0 else None


def gastos_por_categoria(df_solo_gastos, periodo_seleccionado):
    return (
        df_solo_gastos[df_solo_gastos["periodo"] == periodo_seleccionado]
        .groupby("categoria")["importe"].sum()
        .sort_values(ascending=False)
    )


def gastos_categoria_por_mes(df_solo_gastos):
    """Pivot categoría x periodo, para ver la evolución de cada categoría en el tiempo."""
    return (
        df_solo_gastos
        .groupby(["categoria", "periodo"])["importe"].sum()
        .unstack(fill_value=0)
    )


FREQ_POR_GRANULARIDAD = {"dia": "D", "semana": "W", "mes": "M", "año": "Y"}


def resumen_por_granularidad(df_movimientos, granularidad="mes"):
    """Igual que resumen_por_periodo, pero agrupando por día, semana, mes o
    año en vez de siempre por mes — para el gráfico de evolución, que puede
    querer mostrar más o menos detalle según cuántos datos haya cargados."""
    freq = FREQ_POR_GRANULARIDAD[granularidad]
    clave = df_movimientos["fecha"].dt.to_period(freq)
    resumen = df_movimientos.assign(_clave=clave).groupby(["_clave", "tipo"])["importe"].sum().unstack()
    resumen["Gasto"] = abs(resumen.get("Gasto", 0))
    resumen["Ingreso"] = resumen.get("Ingreso", 0)
    resumen["Saldo"] = resumen["Ingreso"] - resumen["Gasto"]
    resumen.index.name = "clave"
    return resumen.sort_index()


def clave_movimiento(fila):
    """Identificador estable de un movimiento (fecha+descripción+importe),
    para poder guardar una corrección manual de categoría en session_state y
    reaplicarla en cada rerun, sin depender de la posición en el DataFrame."""
    return f"{fila['fecha'].date()}|{fila['descripcion']}|{fila['importe']}"


def aplicar_correcciones(df_movimientos, correcciones):
    """Reaplica correcciones de categoría hechas a mano (dict clave -> nueva
    categoría) sobre un df_movimientos recién reconstruido desde el archivo
    original, para que persistan entre reruns sin tener que descargar y
    volver a subir el CSV."""
    if not correcciones:
        return df_movimientos
    claves = df_movimientos.apply(clave_movimiento, axis=1)
    for clave, categoria in correcciones.items():
        df_movimientos.loc[claves == clave, "categoria"] = categoria
    return df_movimientos


def sin_clasificar_frecuentes(df_movimientos, minimo=2):
    """Agrupa los movimientos "Sin clasificar" por descripción exacta, para
    detectar cuáles son recurrentes (el mismo comercio/concepto aparece
    varias veces) — esos convienen clasificarse primero porque una sola
    corrección masiva ordena de golpe todas sus apariciones."""
    df = df_movimientos[df_movimientos["categoria"] == "Sin clasificar"]
    if df.empty:
        return pd.DataFrame(columns=["descripcion", "cantidad", "total"])

    agrupado = (
        df.groupby("descripcion")["importe"]
        .agg(cantidad="count", total=lambda s: s.abs().sum())
        .reset_index()
        .sort_values(["cantidad", "total"], ascending=False)
    )
    return agrupado[agrupado["cantidad"] >= minimo]


def detectar_gastos_fijos(df_movimientos, minimo_meses=2):
    """Detecta gastos "fijos": la misma descripción apareciendo como gasto
    en 2 o más meses distintos — la señal más simple de un gasto recurrente
    (alquiler, cuota, suscripción) en vez de uno puntual. El promedio se
    calcula solo sobre esas apariciones, para estimar cuánto sale por mes."""
    gastos = df_movimientos[df_movimientos["tipo"] == "Gasto"].copy()
    gastos["importe_abs"] = gastos["importe"].abs()
    if gastos.empty:
        return pd.DataFrame(columns=["descripcion", "categoria", "meses", "promedio"])

    agrupado = gastos.groupby("descripcion").agg(
        meses=("periodo", "nunique"),
        promedio=("importe_abs", "mean"),
        categoria=("categoria", "first"),
    ).reset_index()
    fijos = agrupado[agrupado["meses"] >= minimo_meses].sort_values("promedio", ascending=False)
    return fijos.reset_index(drop=True)


def construir_plan_inicial(df_movimientos, df_solo_gastos):
    """Arma la tabla editable de planificación: una fila por cada gasto fijo
    detectado, más una fila por categoría con el promedio mensual del resto
    (gasto variable). Es solo el punto de partida — el usuario la puede
    editar libremente después (agregar, borrar, modificar montos)."""
    fijos = detectar_gastos_fijos(df_movimientos)
    descripciones_fijas = set(fijos["descripcion"]) if not fijos.empty else set()

    filas = []
    for _, fila in fijos.iterrows():
        filas.append({
            "descripcion": fila["descripcion"],
            "categoria": fila["categoria"],
            "tipo": "Fijo",
            "monto": round(float(fila["promedio"]), -2),
        })

    variable = df_solo_gastos[~df_solo_gastos["descripcion"].isin(descripciones_fijas)]
    if not variable.empty:
        n_periodos = max(variable["periodo"].nunique(), 1)
        por_categoria = variable.groupby("categoria")["importe"].sum() / n_periodos
        for categoria, monto in por_categoria.items():
            if monto > 0:
                filas.append({
                    "descripcion": f"{categoria} (variable, promedio)",
                    "categoria": categoria,
                    "tipo": "Variable",
                    "monto": round(float(monto), -2),
                })

    return pd.DataFrame(filas, columns=["descripcion", "categoria", "tipo", "monto"])


def sugerir_recortes(df_plan, objetivo_ahorro_extra, recorte_maximo_pct=0.5):
    """Reglas simples (sin IA) para responder "si quiero ahorrar $X más,
    ¿qué gasto debería recortar?": ataca primero los gastos variables más
    grandes, sin proponer recortar más de la mitad de ninguno — los gastos
    fijos no se tocan, porque por definición son más difíciles de bajar."""
    if df_plan is None or df_plan.empty or objetivo_ahorro_extra <= 0:
        return [], objetivo_ahorro_extra

    variables = df_plan[(df_plan["tipo"] == "Variable") & (df_plan["monto"] > 0)]
    variables = variables.sort_values("monto", ascending=False)

    restante = objetivo_ahorro_extra
    sugerencias = []
    for _, fila in variables.iterrows():
        if restante <= 0:
            break
        tope = fila["monto"] * recorte_maximo_pct
        recorte = min(tope, restante)
        if recorte >= 1:
            sugerencias.append({
                "descripcion": fila["descripcion"],
                "monto_actual": fila["monto"],
                "recorte_sugerido": recorte,
                "monto_nuevo": fila["monto"] - recorte,
            })
            restante -= recorte

    return sugerencias, max(restante, 0)


def proyectar_ahorro(resumen, monto_objetivo, meses_deseados=None):
    """Proyección simple de ahorro: a partir del saldo promedio de los meses
    ya cargados, estima cuánto tardarías en juntar `monto_objetivo`, y si se
    indica `meses_deseados`, cuánto necesitarías ahorrar por mes para
    lograrlo en ese plazo. Cálculo directo, sin IA."""
    promedio_ahorro = resumen["Saldo"].mean() if len(resumen) else 0

    resultado = {
        "promedio_ahorro": promedio_ahorro,
        "meses_necesarios": None,
        "fecha_estimada": None,
        "ahorro_necesario_mensual": None,
        "diferencia_mensual": None,
    }

    if promedio_ahorro > 0 and monto_objetivo > 0:
        meses_necesarios = math.ceil(monto_objetivo / promedio_ahorro)
        resultado["meses_necesarios"] = meses_necesarios
        resultado["fecha_estimada"] = pd.Timestamp.now().normalize() + pd.DateOffset(months=meses_necesarios)

    if meses_deseados:
        ahorro_necesario = monto_objetivo / meses_deseados
        resultado["ahorro_necesario_mensual"] = ahorro_necesario
        resultado["diferencia_mensual"] = ahorro_necesario - promedio_ahorro

    return resultado
