"""Panel de preguntas estilo chat — igual que los "Consejos", son reglas que
leen los datos ya calculados, NO un modelo de IA real. Sin costo, sin API
key, sin límite de uso aunque la app la use mucha gente.

Esta lista de preguntas es un primer borrador para ir ajustando junto con el
usuario: agregar/sacar preguntas es simplemente sumar una entrada a
PREGUNTAS_SUGERIDAS y su función correspondiente en REGLAS_PREGUNTAS.
"""

import unicodedata

from data import MESES_ES, periodo_anterior_de


def _normalizar(s):
    s = str(s).strip().lower()
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _cuanto_gaste(ctx):
    return f"Este mes gastaste **${ctx['gastos_actual']:,.0f}**."


def _categoria_top(ctx):
    if ctx["gastos_cat"].empty:
        return "Todavía no tenés gastos categorizados este mes."
    cat = ctx["gastos_cat"].idxmax()
    monto = ctx["gastos_cat"].max()
    return f"La categoría en la que más gastás este mes es **{cat}**, con ${monto:,.0f}."


def _mes_mas_ahorro(ctx):
    resumen = ctx["resumen"]
    if resumen.empty:
        return "Todavía no hay datos suficientes para esto."
    periodo = resumen["Saldo"].idxmax()
    monto = resumen["Saldo"].max()
    return f"Tu mes con más ahorro fue **{MESES_ES[periodo.month]} {periodo.year}**, con ${monto:,.0f} de saldo."


def _gasto_mas_grande(ctx):
    df = ctx["df_solo_gastos"]
    df_periodo = df[df["periodo"] == ctx["periodo_seleccionado"]]
    if df_periodo.empty:
        return "No tenés gastos registrados este mes."
    fila = df_periodo.loc[df_periodo["importe"].idxmax()]
    return f"Tu gasto más grande este mes fue **{fila['descripcion']}**, por ${fila['importe']:,.0f}."


def _tasa_ahorro_comparada(ctx):
    resumen = ctx["resumen"]
    periodo = ctx["periodo_seleccionado"]
    periodos_disponibles = sorted(ctx["df_movimientos"]["periodo"].unique())
    anterior = periodo_anterior_de(periodos_disponibles, periodo)

    ingreso_actual = resumen.loc[periodo, "Ingreso"]
    tasa_actual = (resumen.loc[periodo, "Saldo"] / ingreso_actual * 100) if ingreso_actual else 0

    if anterior is None:
        return f"Tu tasa de ahorro este mes es de **{tasa_actual:.1f}%**. Todavía no hay un mes anterior para comparar."

    ingreso_anterior = resumen.loc[anterior, "Ingreso"]
    tasa_anterior = (resumen.loc[anterior, "Saldo"] / ingreso_anterior * 100) if ingreso_anterior else 0
    diferencia = tasa_actual - tasa_anterior
    tendencia = "mejoró" if diferencia > 0 else "empeoró" if diferencia < 0 else "se mantuvo igual"
    return f"Tu tasa de ahorro **{tendencia}**: {tasa_anterior:.1f}% → {tasa_actual:.1f}% ({diferencia:+.1f} puntos)."


def _sin_clasificar(ctx):
    df = ctx["df_movimientos"]
    pendientes = df[(df["periodo"] == ctx["periodo_seleccionado"]) & (df["categoria"] == "Sin clasificar")]
    if pendientes.empty:
        return "No — todos tus movimientos de este mes ya están categorizados. 👍"
    return (
        f"Sí, tenés **{len(pendientes)}** movimiento(s) sin clasificar este mes. "
        "Podés asignarles categoría en la pestaña Movimientos."
    )


PREGUNTAS_SUGERIDAS = [
    "¿Cuánto gasté este mes?",
    "¿En qué categoría gasto más?",
    "¿Cuál fue mi mes con más ahorro?",
    "¿Cuál fue mi gasto más grande este mes?",
    "¿Cómo viene mi tasa de ahorro respecto al mes anterior?",
    "¿Tengo movimientos sin clasificar?",
]

REGLAS_PREGUNTAS = [
    (["cuanto gaste", "gasto total", "total gaste", "cuanto gastamos"], _cuanto_gaste),
    (["categoria gasto mas", "categoria en la que mas gasto", "en que categoria gasto mas", "categoria con mas gasto"], _categoria_top),
    (["mes con mas ahorro", "mejor mes de ahorro", "mes en el que mas ahorre"], _mes_mas_ahorro),
    (["gasto mas grande", "mayor gasto", "gasto mas alto", "compra mas grande"], _gasto_mas_grande),
    (["tasa de ahorro"], _tasa_ahorro_comparada),
    (["sin clasificar", "sin categoria", "movimientos pendientes"], _sin_clasificar),
]

RESPUESTA_SIN_MATCH = (
    "No tengo una respuesta armada para esa pregunta todavía. Probá con alguna de las "
    "sugeridas de arriba."
)


def responder(pregunta, ctx):
    p = _normalizar(pregunta)
    for palabras_clave, handler in REGLAS_PREGUNTAS:
        if any(_normalizar(k) in p for k in palabras_clave):
            return handler(ctx)
    return RESPUESTA_SIN_MATCH
