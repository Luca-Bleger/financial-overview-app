"""Motor de consejos basado en reglas — sin IA externa, sin costo, sin API key.

Reutiliza los mismos cálculos que ya existían en el notebook (comparación
mes a mes, categoría de mayor aumento/disminución, categorías nuevas) y les
suma un par de reglas nuevas (tasa de ahorro, concentración de gasto,
movimientos sin clasificar), presentado como una lista de consejos.

Cada insight es un dict: {"tipo": "positivo"|"alerta"|"info", "mensaje": str,
"detalle": str}. "mensaje" es el resumen de una línea; "detalle" es el texto
que se muestra al desplegar ese consejo, con más contexto o una sugerencia
concreta de qué hacer al respecto.
"""

from data import periodo_anterior_de, gastos_categoria_por_mes


def generar_insights(df_movimientos, df_solo_gastos, resumen, periodo_seleccionado):
    insights = []

    periodos_disponibles = sorted(df_movimientos["periodo"].unique())
    periodo_anterior = periodo_anterior_de(periodos_disponibles, periodo_seleccionado)

    gastos_actual = resumen.loc[periodo_seleccionado, "Gasto"]
    ingresos_actual = resumen.loc[periodo_seleccionado, "Ingreso"]
    saldo_actual = resumen.loc[periodo_seleccionado, "Saldo"]

    # --- Comparación de gastos totales ---
    if periodo_anterior is not None:
        gastos_anterior = resumen.loc[periodo_anterior, "Gasto"]

        if gastos_anterior > 0:
            variacion = ((gastos_actual - gastos_anterior) / gastos_anterior) * 100

            if variacion > 15:
                insights.append({
                    "tipo": "alerta",
                    "mensaje": f"Tus gastos subieron un {variacion:.1f}% respecto al mes anterior "
                               f"(\\${gastos_anterior:,.0f} → \\${gastos_actual:,.0f}).",
                    "detalle": "Entrá a la pestaña **Categorías** → \"Evolución de gastos por categoría\" "
                               "para ver cuál categoría específica empujó el aumento, o mirá el consejo "
                               "de \"categoría que más aumentó\" más abajo si aparece.",
                })
            elif variacion < -15:
                insights.append({
                    "tipo": "positivo",
                    "mensaje": f"Tus gastos bajaron un {abs(variacion):.1f}% respecto al mes anterior "
                               f"(\\${gastos_anterior:,.0f} → \\${gastos_actual:,.0f}). ¡Bien ahí!",
                    "detalle": "Si sabés qué cambiaste este mes (menos delivery, menos salidas, etc.), "
                               "vale la pena sostenerlo — es la forma más simple de mejorar tu tasa de "
                               "ahorro sin tener que ganar más.",
                })
            else:
                insights.append({
                    "tipo": "info",
                    "mensaje": f"Tus gastos se mantuvieron estables respecto al mes anterior "
                               f"({variacion:+.1f}%).",
                    "detalle": "Ni suba ni baja fuerte — tu gasto mensual está siendo predecible, lo cual "
                               "ayuda a planificar con la pestaña **Proyección**.",
                })

        # --- Categoría con mayor aumento / disminución ---
        cat_mes = gastos_categoria_por_mes(df_solo_gastos)
        if periodo_seleccionado in cat_mes.columns and periodo_anterior in cat_mes.columns:
            diferencia = cat_mes[periodo_seleccionado] - cat_mes[periodo_anterior]

            if not diferencia.empty:
                cat_mayor_aumento = diferencia.idxmax()
                mayor_aumento = diferencia.loc[cat_mayor_aumento]
                if mayor_aumento > 0:
                    insights.append({
                        "tipo": "alerta",
                        "mensaje": f"La categoría que más aumentó fue **{cat_mayor_aumento}**, "
                                   f"con +\\${mayor_aumento:,.0f}.",
                        "detalle": f"Filtrá la pestaña **Movimientos** por \"{cat_mayor_aumento}\" para ver "
                                   "exactamente qué movimientos la explican, y si fue algo puntual (un "
                                   "gasto único) o algo que se va a repetir todos los meses.",
                    })

                cat_mayor_disminucion = diferencia.idxmin()
                mayor_disminucion = diferencia.loc[cat_mayor_disminucion]
                if mayor_disminucion < 0:
                    insights.append({
                        "tipo": "positivo",
                        "mensaje": f"La categoría que más bajó fue **{cat_mayor_disminucion}**, "
                                   f"con -\\${abs(mayor_disminucion):,.0f}.",
                        "detalle": f"Bajaste **{cat_mayor_disminucion}** respecto al mes anterior — si fue "
                                   "algo que decidiste a propósito, es un buen hábito para mantener.",
                    })

            # --- Categorías nuevas ---
            nuevas = cat_mes[(cat_mes[periodo_anterior] == 0) & (cat_mes[periodo_seleccionado] > 0)]
            for categoria in nuevas.index:
                monto = nuevas.loc[categoria, periodo_seleccionado]
                insights.append({
                    "tipo": "info",
                    "mensaje": f"Apareció un gasto nuevo en **{categoria}** este mes: \\${monto:,.0f}.",
                    "detalle": "Si es un gasto que se va a repetir todos los meses (una suscripción, una "
                               "cuota nueva), convendría tenerlo en cuenta al planificar el próximo mes en "
                               "la pestaña **Proyección**.",
                })
    else:
        insights.append({
            "tipo": "info",
            "mensaje": "Este es el primer mes con datos — todavía no hay mes anterior para comparar.",
            "detalle": "A partir del segundo mes que cargues vas a empezar a ver comparaciones acá.",
        })

    # --- Tasa de ahorro ---
    if ingresos_actual > 0:
        tasa_ahorro = (saldo_actual / ingresos_actual) * 100

        if tasa_ahorro < 0:
            insights.append({
                "tipo": "alerta",
                "mensaje": f"Este mes gastaste más de lo que ingresaste (saldo: \\${saldo_actual:,.0f}).",
                "detalle": "Mirá \"Mayores gastos individuales del mes\" en la pestaña **Resumen** para "
                           "identificar qué gasto puntual explica la diferencia, y si fue algo excepcional "
                           "o si se va a repetir.",
            })
        elif tasa_ahorro < 10:
            insights.append({
                "tipo": "alerta",
                "mensaje": f"Tu tasa de ahorro es de {tasa_ahorro:.1f}% — bastante ajustada. "
                           f"Podría valer la pena revisar tus categorías de mayor gasto.",
                "detalle": "Probá la pestaña **Proyección**: te muestra cuánto necesitarías ahorrar por mes "
                           "para una meta puntual, y podés comparar contra tu ritmo actual.",
            })
        elif tasa_ahorro > 40:
            insights.append({
                "tipo": "positivo",
                "mensaje": f"Estás ahorrando el {tasa_ahorro:.1f}% de tus ingresos este mes. ¡Muy bien!",
                "detalle": "Con este ritmo, la pestaña **Proyección** te puede decir en cuántos meses "
                           "llegás a una meta de ahorro que tengas en mente.",
            })

    # --- Concentración de gasto en una sola categoría ---
    gastos_cat_actual = (
        df_solo_gastos[df_solo_gastos["periodo"] == periodo_seleccionado]
        .groupby("categoria")["importe"].sum()
    )
    if gastos_actual > 0 and not gastos_cat_actual.empty:
        categoria_dominante = gastos_cat_actual.idxmax()
        porcentaje_dominante = (gastos_cat_actual.max() / gastos_actual) * 100
        if porcentaje_dominante > 50:
            insights.append({
                "tipo": "alerta",
                "mensaje": f"**{categoria_dominante}** representa el {porcentaje_dominante:.0f}% "
                           f"de tus gastos del mes — está bastante concentrado en una sola categoría.",
                "detalle": "No necesariamente es un problema (por ejemplo, si es alquiler o una cuota "
                           "grande, es esperable) — pero si te sorprende, vale la pena revisarla en el "
                           "gráfico \"Gastos por categoría\" de la pestaña **Resumen**.",
            })

    # --- Movimientos sin clasificar ---
    sin_clasificar = df_movimientos[
        (df_movimientos["periodo"] == periodo_seleccionado)
        & (df_movimientos["categoria"] == "Sin clasificar")
    ]
    if len(sin_clasificar) > 0:
        insights.append({
            "tipo": "info",
            "mensaje": f"Tenés {len(sin_clasificar)} movimiento(s) sin clasificar este mes. "
                       f"Podés asignarles categoría en la pestaña **Movimientos**.",
            "detalle": "Si alguna descripción se repite varias veces, la sección \"Sin clasificar, y se "
                       "repiten\" (al final de la pestaña **Movimientos**) te deja clasificarla una sola "
                       "vez y aplica el cambio a todas sus apariciones de golpe.",
        })

    if not insights:
        insights.append({
            "tipo": "info",
            "mensaje": "No hay novedades particulares este mes — todo dentro de lo esperado.",
            "detalle": "Ningún indicador (gasto total, tasa de ahorro, concentración por categoría) se "
                       "salió de lo normal respecto al mes anterior.",
        })

    return insights
