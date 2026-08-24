"""Gráficos Plotly, pensados para ser responsive de verdad (celular y compu):
se usan siempre con width="stretch" en la app, y ninguna leyenda se ubica
fuera del área 0-1 de "paper" (eso es lo que rompía la leyenda del donut en
pantallas angostas — quedaba dibujada afuera del ancho visible). Todas las
leyendas van centradas debajo del gráfico, donde Plotly las envuelve en
varias líneas si no entran en una sola.
"""

import numpy as np
import plotly.graph_objects as go

from data import MESES_ES

FONDO = "#0B1220"
PANEL = "#152033"
BORDE = "#263752"
BLANCO = "#F8FAFC"
TEXTO = "#CBD5E1"
TEXTO_SECUNDARIO = "#8FA1BC"
INGRESOS_COLOR = "#8B95F6"
GASTOS_COLOR = "#FF8194"
SALDO_COLOR = "#67D2D0"
COLORES_CATEGORIA = [
    "#818CF8", "#FF654A", "#4FD1C5", "#8B5DD7", "#FFAB5C",
    "#38BDF8", "#F472B6", "#A3E635", "#FB923C", "#22D3EE",
]

LAYOUT_BASE = dict(
    paper_bgcolor=PANEL,
    plot_bgcolor=PANEL,
    font=dict(family="Arial, sans-serif", color=BLANCO),
    autosize=True,
    # dragmode=False evita que un swipe para hacer scroll de la página en el
    # celular quede "atrapado" por el gráfico como un arrastre de zoom (eso
    # dejaba el gráfico de evolución trabado en un rango minúsculo y vacío).
    # El pellizco de dos dedos y los botones de zoom de la barra de
    # herramientas siguen funcionando igual — esto solo afecta el gesto de
    # un solo dedo, que ahora pasa de largo como scroll normal de la página.
    dragmode=False,
    hoverlabel=dict(bgcolor="#1B2940", bordercolor=BORDE, font_size=14, font_color=BLANCO),
)

LEYENDA_ABAJO = dict(
    orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5,
    font=dict(color=TEXTO, size=12),
)


def _etiquetas_periodo(periodos):
    return [f"{MESES_ES[p.month][:3]} {p.year}" for p in periodos]


NOMBRE_GRANULARIDAD = {"dia": "día", "semana": "semana", "mes": "mes", "año": "año"}


def _etiquetas_granularidad(indices, granularidad="mes"):
    if granularidad == "dia":
        return [p.strftime("%d/%m") for p in indices]
    if granularidad == "semana":
        return [f"Sem {p.start_time.strftime('%d/%m')}" for p in indices]
    if granularidad == "año":
        return [str(p.year) for p in indices]
    return _etiquetas_periodo(indices)


def _con_opacidad(color_hex, alpha):
    color_hex = color_hex.lstrip("#")
    r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def grafico_evolucion(resumen, granularidad="mes"):
    # Una línea necesita al menos 2 puntos para dibujarse: con un solo
    # período de datos en la granularidad elegida, "lines+markers" solo
    # puede mostrar un punto suelto flotando (eso es lo que se veía antes
    # con un solo mes cargado). En ese caso no tiene sentido mostrar una
    # "evolución" — se muestra en cambio una comparación en barras de ese
    # único período, con los montos como etiqueta.
    if len(resumen) < 2:
        return _grafico_evolucion_snapshot(resumen, granularidad)

    labels = _etiquetas_granularidad(resumen.index, granularidad)

    fig = go.Figure()
    for nombre, color, columna, relleno in [
        ("Ingresos", INGRESOS_COLOR, "Ingreso", None),
        ("Gastos", GASTOS_COLOR, "Gasto", None),
        ("Saldo", SALDO_COLOR, "Saldo", "tozeroy"),
    ]:
        fig.add_trace(go.Scatter(
            x=labels, y=resumen[columna], mode="lines+markers", name=nombre,
            line=dict(color=color, width=2.5), marker=dict(size=8, color=color),
            fill=relleno, fillcolor=_con_opacidad(color, 0.08) if relleno else None,
            hovertemplate=f"<b>{nombre}</b><br>%{{x}}<br><b>$%{{y:,.0f}}</b><extra></extra>",
        ))

    fig.update_layout(
        **LAYOUT_BASE,
        height=360,
        margin=dict(l=10, r=10, t=20, b=70),
        hovermode="closest",
        legend=LEYENDA_ABAJO,
        xaxis=dict(showgrid=False, tickfont=dict(color=TEXTO, size=13)),
        yaxis=dict(gridcolor="rgba(148,163,184,0.10)", tickfont=dict(color=TEXTO_SECUNDARIO, size=12), tickformat=".2s"),
    )
    return fig


def _grafico_evolucion_snapshot(resumen, granularidad="mes"):
    """Comparación en barras para cuando solo hay un período de datos en la
    granularidad elegida (por ejemplo, un solo mes cargado)."""
    fila = resumen.iloc[0]
    etiqueta = _etiquetas_granularidad(resumen.index, granularidad)[0]
    nombre_gran = NOMBRE_GRANULARIDAD.get(granularidad, "período")
    nombres = ["Ingresos", "Gastos", "Saldo"]
    colores = [INGRESOS_COLOR, GASTOS_COLOR, SALDO_COLOR]
    valores = [fila["Ingreso"], fila["Gasto"], fila["Saldo"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=nombres, y=valores, marker=dict(color=colores),
        text=[f"${v:,.0f}" for v in valores], textposition="outside",
        textfont=dict(color=BLANCO, size=13),
        hovertemplate="<b>%{x}</b><br>$%{y:,.0f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_color=BORDE, line_width=1)

    fig.update_layout(
        **LAYOUT_BASE,
        height=320,
        margin=dict(l=10, r=10, t=44, b=30),
        title=dict(
            text=f"Solo hay un(a) {nombre_gran} con datos ({etiqueta}) — probá otra granularidad o subí más datos",
            font=dict(color=TEXTO_SECUNDARIO, size=12), x=0.5, xanchor="center",
        ),
        showlegend=False,
        xaxis=dict(showgrid=False, tickfont=dict(color=TEXTO, size=13)),
        yaxis=dict(gridcolor="rgba(148,163,184,0.10)", tickfont=dict(color=TEXTO_SECUNDARIO, size=12), tickformat=".2s"),
    )
    return fig


def grafico_donut(gastos_categoria):
    categorias = gastos_categoria.index.tolist()
    valores = gastos_categoria.values.tolist()
    total = sum(valores)

    fig = go.Figure()

    if categorias:
        fig.add_trace(go.Pie(
            labels=categorias, values=valores, hole=0.62,
            sort=False, textinfo="percent", textfont=dict(color=BLANCO, size=12),
            marker=dict(colors=COLORES_CATEGORIA[:len(categorias)], line=dict(color=PANEL, width=3)),
            domain=dict(x=[0.1, 0.9], y=[0.28, 1]),
            hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percent:.1%}<extra></extra>",
        ))
        fig.add_annotation(
            text=f"<b>${total:,.0f}</b><br><span style='font-size:11px;color:{TEXTO_SECUNDARIO}'>Total gastado</span>",
            x=0.5, y=0.64, showarrow=False, font=dict(size=16, color=BLANCO),
        )
    else:
        fig.add_annotation(text="Sin gastos registrados", x=0.5, y=0.5, showarrow=False,
                            font=dict(size=13, color=TEXTO_SECUNDARIO))

    fig.update_layout(
        **LAYOUT_BASE,
        height=460,
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=True,
        legend=dict(orientation="v", yanchor="top", y=0.24, xanchor="center", x=0.5, font=dict(color=TEXTO, size=12)),
    )
    return fig


def grafico_categorias_tiempo(cat_mes):
    """Barras apiladas: cuánto se gastó en cada categoría, mes a mes."""
    labels = _etiquetas_periodo(cat_mes.columns)

    fig = go.Figure()
    for i, categoria in enumerate(cat_mes.index):
        color = COLORES_CATEGORIA[i % len(COLORES_CATEGORIA)]
        fig.add_trace(go.Bar(
            x=labels, y=cat_mes.loc[categoria], name=categoria,
            marker=dict(color=color),
            hovertemplate=f"<b>{categoria}</b><br>%{{x}}<br><b>$%{{y:,.0f}}</b><extra></extra>",
        ))

    fig.update_layout(
        **LAYOUT_BASE,
        height=460,
        margin=dict(l=10, r=10, t=20, b=120),
        barmode="stack",
        legend=LEYENDA_ABAJO,
        xaxis=dict(showgrid=False, tickfont=dict(color=TEXTO, size=13)),
        yaxis=dict(gridcolor="rgba(148,163,184,0.10)", tickfont=dict(color=TEXTO_SECUNDARIO, size=12), tickformat=".2s"),
    )
    return fig


def grafico_tasa_ahorro(resumen):
    labels = _etiquetas_periodo(resumen.index)
    tasa = (resumen["Saldo"] / resumen["Ingreso"].replace(0, np.nan)) * 100

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels, y=tasa, marker=dict(color=SALDO_COLOR),
        hovertemplate="<b>%{x}</b><br>Tasa de ahorro: <b>%{y:.1f}%</b><extra></extra>",
    ))
    fig.add_hline(y=0, line_color=BORDE, line_width=1)

    fig.update_layout(
        **LAYOUT_BASE,
        height=320,
        margin=dict(l=10, r=10, t=20, b=40),
        xaxis=dict(showgrid=False, tickfont=dict(color=TEXTO, size=13)),
        yaxis=dict(gridcolor="rgba(148,163,184,0.10)", tickfont=dict(color=TEXTO_SECUNDARIO, size=12), ticksuffix="%"),
    )
    return fig


def grafico_top_gastos(df_solo_gastos, periodo_seleccionado, top_n=8):
    df_periodo = df_solo_gastos[df_solo_gastos["periodo"] == periodo_seleccionado]
    top = df_periodo.nlargest(top_n, "importe")[["descripcion", "importe", "categoria"]]
    top = top.sort_values("importe")
    etiquetas = [d if len(d) <= 22 else d[:20] + "…" for d in top["descripcion"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=top["importe"], y=etiquetas, orientation="h",
        marker=dict(color=GASTOS_COLOR),
        customdata=top["descripcion"],
        hovertemplate="<b>%{customdata}</b><br>$%{x:,.0f}<extra></extra>",
    ))

    fig.update_layout(
        **LAYOUT_BASE,
        height=max(340, 60 + len(top) * 42),
        margin=dict(l=10, r=20, t=20, b=30),
        xaxis=dict(gridcolor="rgba(148,163,184,0.10)", tickfont=dict(color=TEXTO_SECUNDARIO, size=12), tickformat=".2s"),
        # automargin=True: sin esto, las descripciones del eje Y (texto, no
        # números) quedaban recortadas porque el margen izquierdo era fijo
        # y muy chico para hacerles lugar.
        yaxis=dict(tickfont=dict(color=TEXTO, size=12), automargin=True),
    )
    return fig
