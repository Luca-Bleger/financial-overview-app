"""Extracción de movimientos desde un PDF de "Resumen de cuenta" de Mercado Pago.

El PDF no tiene una tabla con bordes que las librerías puedan detectar
directamente: es texto posicionado en columnas. Además, cuando una
descripción es larga, su texto se parte en varias líneas que a veces
aparecen ANTES y a veces DESPUÉS de la línea con fecha/ID/importe/saldo
(según cómo el generador del PDF centra verticalmente el texto). Por eso
no se puede parsear línea por línea: hay que ubicar cada palabra por su
posición (x, y) en la página y agruparla por cercanía vertical a la fila
de fecha/importe más próxima.
"""

import re

import pandas as pd

PATRON_FECHA = re.compile(r"^\d{2}-\d{2}-\d{4}$")
PATRON_PAGINA = re.compile(r"^\d+/\d+$")


def parece_mercadopago(primer_texto):
    texto = (primer_texto or "").upper()
    return "MERCADO PAGO" in texto and "RESUMEN DE CUENTA" in texto


PATRON_ID_OPERACION = re.compile(r"^\d{9,}$")


def _detectar_limites_columnas(words):
    """Ubica los límites x de cada columna en la página.

    La columna Descripción es mucho más ancha que su etiqueta de encabezado
    ("Descripción" es una palabra corta, pero el texto real de las
    descripciones ocupa casi todo el ancho hasta la columna ID). Por eso NO
    se puede usar el punto medio entre las posiciones de los encabezados
    "Descripción" e "ID" — eso corta la columna a la mitad y descarta
    palabras que están más a la derecha (por ejemplo "Ahorro" en "Dinero
    reservado Ahorro"). En cambio, el límite derecho de Descripción se
    calcula a partir de dónde arrancan REALMENTE los números de operación
    en los datos (mediana de esa posición en toda la página), no de dónde
    está el texto del encabezado.

    "Saldo" también aparece en el cuadro-resumen de la página 1 ("Saldo
    inicial", "Saldo final") en una posición distinta a la del encabezado
    real de la tabla, por eso los encabezados se buscan a la misma altura
    ("top") que "Fecha", que solo aparece una vez por página.
    """

    fecha_word = next((w for w in words if w["text"] == "Fecha"), None)
    if fecha_word is None:
        return None
    fecha_top = fecha_word["top"]

    def _mas_cercana_a_fecha(candidatos):
        candidatos = [w for w in candidatos if abs(w["top"] - fecha_top) < 15]
        if not candidatos:
            return None
        return min(candidatos, key=lambda w: abs(w["top"] - fecha_top))

    descripcion_word = _mas_cercana_a_fecha([w for w in words if w["text"].startswith("Descrip")])
    valor_word = _mas_cercana_a_fecha([w for w in words if w["text"] == "Valor"])
    saldo_word = _mas_cercana_a_fecha([w for w in words if w["text"] == "Saldo"])

    ids_detectados = sorted(w["x0"] for w in words if PATRON_ID_OPERACION.match(w["text"]))

    if not all([descripcion_word, valor_word, saldo_word]) or not ids_detectados:
        return None

    id_x0 = ids_detectados[len(ids_detectados) // 2]  # mediana

    orden = [fecha_word["x0"], descripcion_word["x0"], id_x0, valor_word["x0"], saldo_word["x0"]]

    def mid(a, b):
        return (a + b) / 2

    limites = {
        "fecha": (0, mid(orden[0], orden[1])),
        "descripcion": (mid(orden[0], orden[1]), id_x0 - 4),
        "id": (id_x0 - 4, mid(orden[2], orden[3])),
        "valor": (mid(orden[2], orden[3]), mid(orden[3], orden[4])),
        "saldo": (mid(orden[3], orden[4]), 100000),
    }
    return limites


def _en_rango(x0, rango):
    return rango[0] <= x0 < rango[1]


def _limpiar_importe(texto):
    texto = texto.replace("$", "").strip()
    texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def _recortar_pie_de_pagina(words):
    """El pie de página (fecha de generación, dirección y CUIT de Mercado
    Libre) cae dentro de la columna Descripción y, si no se excluye, se
    pega a la descripción de la última fila de la página. Se detecta por
    marcadores de texto que solo aparecen ahí, y se recorta todo lo que
    esté a la altura del primero de ellos (más arriba) en adelante."""

    marcadores = [
        w for w in words
        if "Caseros" in w["text"] or "generaci" in w["text"].lower()
    ]
    if not marcadores:
        return words
    limite_top = min(w["top"] for w in marcadores) - 2
    return [w for w in words if w["top"] < limite_top]


def _ordenar_por_lineas(palabras, tolerancia=2.0):
    """Reordena palabras de un bloque de texto multilínea agrupándolas por
    línea real (palabras cuyo "top" está a menos de `tolerancia` puntos de
    distancia entre sí), en vez de redondear el "top" a un entero — dos
    palabras de la misma línea visual pueden diferir en top por ~1pt sin
    cruzar un límite de redondeo consistente, lo que mezclaba el orden en
    descripciones de 3 o más líneas."""

    if not palabras:
        return []

    ordenadas = sorted(palabras, key=lambda w: w["top"])
    lineas = [[ordenadas[0]]]
    for w in ordenadas[1:]:
        if abs(w["top"] - lineas[-1][-1]["top"]) <= tolerancia:
            lineas[-1].append(w)
        else:
            lineas.append([w])

    lineas_con_top = [
        (sum(w["top"] for w in linea) / len(linea), sorted(linea, key=lambda w: w["x0"]))
        for linea in lineas
    ]
    lineas_con_top.sort(key=lambda t: t[0])

    return [w for _, linea in lineas_con_top for w in linea]


def _extraer_filas_pagina(page):
    words = page.extract_words()
    words = _recortar_pie_de_pagina(words)
    limites = _detectar_limites_columnas(words)
    if limites is None:
        return []

    # Anclas: palabras con formato de fecha, dentro de la columna Fecha
    anclas = [
        w for w in words
        if PATRON_FECHA.match(w["text"]) and _en_rango(w["x0"], limites["fecha"])
    ]
    if not anclas:
        return []

    anclas.sort(key=lambda w: w["top"])

    filas = []
    for ancla in anclas:
        filas.append({
            "top": ancla["top"],
            "fecha": ancla["text"],
            "descripcion_palabras": [],
            "id_palabras": [],
            "valor_palabras": [],
        })

    # Palabras de ID y Valor: deben estar en la misma linea (top muy cercano)
    # que la ancla de fecha correspondiente.
    for w in words:
        if PATRON_PAGINA.match(w["text"]):
            continue
        if _en_rango(w["x0"], limites["id"]):
            ancla_cercana = min(filas, key=lambda f: abs(f["top"] - w["top"]))
            if abs(ancla_cercana["top"] - w["top"]) < 3:
                ancla_cercana["id_palabras"].append(w)
        elif _en_rango(w["x0"], limites["valor"]):
            ancla_cercana = min(filas, key=lambda f: abs(f["top"] - w["top"]))
            if abs(ancla_cercana["top"] - w["top"]) < 3:
                ancla_cercana["valor_palabras"].append(w)

    # Palabras de Descripcion: pueden estar en lineas por encima o por debajo
    # de la fila de datos (el PDF centra el bloque de texto verticalmente).
    # Se asignan a la ancla de fecha mas cercana en la columna Descripcion.
    for w in words:
        if not _en_rango(w["x0"], limites["descripcion"]):
            continue
        if w["text"].startswith("Descrip"):
            continue  # encabezado de columna repetido en cada pagina
        ancla_cercana = min(filas, key=lambda f: abs(f["top"] - w["top"]))
        ancla_cercana["descripcion_palabras"].append(w)

    resultado = []
    for fila in filas:
        descripcion_palabras = _ordenar_por_lineas(fila["descripcion_palabras"])
        descripcion = " ".join(w["text"] for w in descripcion_palabras).strip()

        valor_palabras = sorted(fila["valor_palabras"], key=lambda w: w["x0"])
        valor_texto = "".join(w["text"] for w in valor_palabras if w["text"] != "$")
        importe = _limpiar_importe(valor_texto)

        if not descripcion or importe is None:
            continue

        resultado.append({
            "fecha": fila["fecha"],
            "descripcion": descripcion,
            "importe": importe,
        })

    return resultado


def extraer_movimientos_pdf(archivo):
    """Devuelve un DataFrame con columnas fecha (DD-MM-AAAA), descripcion,
    importe — listo para pasar por el mismo pipeline que un CSV/Excel."""

    import pdfplumber

    archivo.seek(0)
    filas = []
    with pdfplumber.open(archivo) as pdf:
        for page in pdf.pages:
            texto = page.extract_text() or ""
            if "TENENCIAS EN D" in texto.upper():
                # Seccion de tenencias (dolares/acciones): distinta tabla, no la procesamos
                continue
            filas.extend(_extraer_filas_pagina(page))

    if not filas:
        raise ValueError(
            "No pude encontrar movimientos en este PDF. ¿Es un resumen de cuenta de "
            "Mercado Pago en pesos?"
        )

    return pd.DataFrame(filas, columns=["fecha", "descripcion", "importe"])
