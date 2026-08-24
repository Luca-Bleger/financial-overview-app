"""Persistencia en Supabase: autenticación y guardado/lectura de
movimientos entre sesiones, para que cada mes que subas se acumule en vez
de reemplazar lo anterior.

IMPORTANTE: el cliente de Supabase NO se cachea de forma global (nada de
st.cache_resource acá) — cada sesión de navegador tiene su propio cliente
guardado en st.session_state. Si se compartiera un solo cliente entre todas
las sesiones de la app, la sesión autenticada de una persona podría
filtrarse a otra que esté usando la app al mismo tiempo. El aislamiento
real de los datos lo hacen las políticas de RLS en Supabase (ver
supabase_schema.sql) — este módulo es la segunda barrera, no la única.
"""

import pandas as pd
import streamlit as st
from supabase import create_client

from data import finalizar_movimientos


def _nuevo_cliente():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


def obtener_cliente():
    if "supabase_client" not in st.session_state:
        try:
            st.session_state.supabase_client = _nuevo_cliente()
        except Exception:
            st.error(
                "No se pudo conectar con la base de datos. Si estás desplegando esta app, "
                "revisá que SUPABASE_URL y SUPABASE_KEY estén cargados en los secrets de "
                "Streamlit (Manage app → Settings → Secrets)."
            )
            st.stop()
    return st.session_state.supabase_client


def registrarse(email, password):
    return obtener_cliente().auth.sign_up({"email": email, "password": password})


def iniciar_sesion(email, password):
    return obtener_cliente().auth.sign_in_with_password({"email": email, "password": password})


def cerrar_sesion():
    obtener_cliente().auth.sign_out()
    if "supabase_client" in st.session_state:
        del st.session_state["supabase_client"]


def guardar_movimientos(user_id, df_movimientos, fuente):
    """Inserta los movimientos nuevos en la base. Los que ya existían
    (mismo user_id+fecha+descripcion+importe) se ignoran gracias al unique
    constraint de la tabla — subir el mismo archivo dos veces no duplica
    nada. Devuelve cuántas filas se mandaron a insertar (no cuántas eran
    realmente nuevas, eso Supabase lo resuelve solo)."""
    filas = [
        {
            "user_id": user_id,
            "fecha": fila["fecha"].strftime("%Y-%m-%d"),
            "descripcion": fila["descripcion"],
            "importe": float(fila["importe"]),
            "categoria": fila["categoria"],
            "fuente": fuente,
        }
        for _, fila in df_movimientos.iterrows()
    ]
    if not filas:
        return 0
    obtener_cliente().table("movimientos").upsert(
        filas, on_conflict="user_id,fecha,descripcion,importe", ignore_duplicates=True,
    ).execute()
    return len(filas)


def cargar_movimientos(user_id):
    """Trae todo el historial acumulado de este usuario, con las mismas
    columnas derivadas (tipo/mes/año/periodo) que usa el resto de la app.
    Incluye "id" (el id real de la fila en la base), que se usa para
    corregir la categoría de un movimiento puntual de forma permanente."""
    resultado = (
        obtener_cliente().table("movimientos")
        .select("id, fecha, descripcion, importe, categoria")
        .eq("user_id", user_id)
        .execute()
    )
    filas = resultado.data
    columnas = ["id", "fecha", "descripcion", "importe", "categoria", "tipo", "mes", "año", "periodo"]
    if not filas:
        return pd.DataFrame(columns=columnas)

    df = pd.DataFrame(filas)
    df["fecha"] = pd.to_datetime(df["fecha"])
    return finalizar_movimientos(df)


def actualizar_categoria(user_id, movimiento_id, categoria):
    (
        obtener_cliente().table("movimientos")
        .update({"categoria": categoria})
        .eq("id", movimiento_id)
        .eq("user_id", user_id)
        .execute()
    )
