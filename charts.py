"""Gráficos Plotly, todos pensados para ser responsive (se usan siempre con
use_container_width=True en la app) y compartir la misma paleta de colores
que ya definimos para el dashboard.
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
    margin=dict(l=10, r=10, t=50, b=10),
    hoverlabel=dict(bgcolor="#1B2940", bordercolor=BORDE, font_size=13, font_color=BLANCO),
)


def _etiquetas_periodo(periodos):
    return [f"{MESES_ES[p.month][:3]} {p.year}" for p in periodos]


def grafico_evolucion(resumen):
    labels = _etiquetas_periodo(resumen.index)

    fig = go.Figure()
    for nombre, color, columna in [
        ("Ingresos", INGRESOS_COLOR, "Ingreso"),
        ("Gastos", GASTOS_COLOR, "Gasto"),
        ("Saldo", SALDO_COLOR, "Saldo"),
    ]:
        fig.add_trace(go.Scatter(
            x=labels, y=resumen[columna], mode="lines+markers", name=nombre,
            line=dict(color=color, width=2.5), marker=dict(size=7, color=color),
            hovertemplate=f"<b>{nombre}</b><br>%{{x}}<br><b>$%{{y:,.0f}}</b><extra></extra>",
        ))

    fig.update_layout(
        **LAYOUT_BASE,
        height=380,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(color=TEXTO)),
        xaxis=dict(showgrid=False, tickfont=dict(color=TEXTO)),
        yaxis=dict(gridcolor="rgba(148,163,184,0.10)", tickfont=dict(color=TEXTO_SECUNDARIO), tickformat=".2s"),
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
            hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percent:.1%}<extra></extra>",
        ))
        fig.add_annotation(
            text=f"<b>${total:,.0f}</b><br><span style='font-size:11px;color:{TEXTO_SECUNDARIO}'>Total gastado</span>",
            x=0.5, y=0.5, showarrow=False, font=dict(size=16, color=BLANCO),
        )
    else:
        fig.add_annotation(text="Sin gastos registrados", x=0.5, y=0.5, showarrow=False,
                            font=dict(size=13, color=TEXTO_SECUNDARIO))

    fig.update_layout(
        **LAYOUT_BASE,
        height=380,
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05, font=dict(color=TEXTO, size=11)),
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
        height=420,
        barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(color=TEXTO, size=11)),
        xaxis=dict(showgrid=False, tickfont=dict(color=TEXTO)),
        yaxis=dict(gridcolor="rgba(148,163,184,0.10)", tickfont=dict(color=TEXTO_SECUNDARIO), tickformat=".2s"),
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
        height=340,
        xaxis=dict(showgrid=False, tickfont=dict(color=TEXTO)),
        yaxis=dict(gridcolor="rgba(148,163,184,0.10)", tickfont=dict(color=TEXTO_SECUNDARIO), ticksuffix="%"),
    )
    return fig


def grafico_top_gastos(df_solo_gastos, periodo_seleccionado, top_n=8):
    df_periodo = df_solo_gastos[df_solo_gastos["periodo"] == periodo_seleccionado]
    top = df_periodo.nlargest(top_n, "importe")[["descripcion", "importe", "categoria"]]
    top = top.sort_values("importe")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=top["importe"], y=top["descripcion"], orientation="h",
        marker=dict(color=GASTOS_COLOR),
        hovertemplate="<b>%{y}</b><br>$%{x:,.0f}<extra></extra>",
    ))

    fig.update_layout(
        **LAYOUT_BASE,
        height=340,
        xaxis=dict(gridcolor="rgba(148,163,184,0.10)", tickfont=dict(color=TEXTO_SECUNDARIO), tickformat=".2s"),
        yaxis=dict(tickfont=dict(color=TEXTO, size=11)),
    )
    return fig
