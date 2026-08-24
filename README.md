# Financial Overview — App de Streamlit

App real de análisis financiero personal: portada, carga flexible de CSV (funciona con extractos de distintos bancos, no asume una estructura fija), varios gráficos, consejos automáticos y clasificación de gastos editable. Responsive: se usa igual en compu o en el celular.

## Estructura del proyecto

- `app.py` — interfaz (portada, mapeo de columnas, pestañas, gráficos).
- `data.py` — ingesta flexible de CSV, categorización automática, agregaciones.
- `charts.py` — todos los gráficos de Plotly.
- `insights.py` — motor de consejos basado en reglas (sin IA externa, sin costo).
- `movimientos_ejemplo.csv` — archivo de prueba.
- `.streamlit/config.toml` — tema visual de la app.

## Cómo probarla en tu computadora

```bash
pip install -r requirements.txt
streamlit run app.py
```

Se abre en `http://localhost:8501`. Subí `movimientos_ejemplo.csv` para probarla, o tu propio archivo.

## Cómo probarla en tu celular AHORA MISMO (sin publicar nada)

Mientras la app está corriendo en tu computadora (`streamlit run app.py`), la terminal muestra algo como:

```
Local URL: http://localhost:8501
Network URL: http://192.168.0.XXX:8501
```

Con tu celular conectado a la **misma red WiFi** que tu computadora, abrí esa "Network URL" en el navegador del celular. Vas a ver la app funcionando ahí, con el mismo diseño adaptado a pantalla chica (las tarjetas y gráficos se acomodan solos).

## Cómo tener una URL pública real (para usarla desde cualquier lado, no solo tu WiFi)

1. Subí esta carpeta a un repositorio de GitHub.
2. Entrá a [share.streamlit.io](https://share.streamlit.io) con tu cuenta de GitHub.
3. "New app" → elegís el repositorio → archivo principal `app.py` → Deploy.
4. En un par de minutos tenés una URL pública (tipo `tu-usuario-financial-overview.streamlit.app`) que funciona desde el celular, la compu, o donde sea, sin depender de tu WiFi.

## Por qué el mapeo de columnas

Los extractos bancarios no vienen todos con la misma estructura: cambian los nombres de columna, algunos separan Débito/Crédito en vez de un importe con signo, y el formato de número puede ser `1234.56` o `1.234,56`. Por eso la app no asume nada fijo — vos le indicás qué columna es cada cosa la primera vez que subís un archivo de un banco nuevo. Para archivos ya conocidos (como el de ejemplo), la app sugiere automáticamente el mapeo más probable.

## Qué incluye cada pestaña

- **Resumen**: evolución financiera, gastos por categoría del mes, mayores gastos individuales.
- **Categorías**: evolución de cada categoría de gasto mes a mes, y tasa de ahorro histórica.
- **Consejos**: alertas y observaciones generadas automáticamente (aumentos/disminuciones, categorías nuevas, concentración de gasto, tasa de ahorro, movimientos sin clasificar) — reglas fijas, sin IA externa ni costo.
- **Movimientos**: tabla editable del mes seleccionado — corregís la categoría de cualquier movimiento a mano y descargás el CSV actualizado.

## Qué se reutilizó del notebook original (sin reescribir nada)

- `REGLAS_CATEGORIAS` y `categorizar()`: misma lógica de clasificación por palabras clave.
- El cálculo de KPIs, variación mes a mes, y gastos por categoría: la misma lógica de `generar_dashboard()` del notebook.
- La paleta de colores y el estilo visual oscuro.
