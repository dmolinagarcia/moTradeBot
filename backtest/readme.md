# replay.py

Backtest con los datos que registra el propio bot (`MT_strategystate`): reproduce
la lógica de `Strategy.operation()` ciclo a ciclo sobre una copia de la BD. Sólo
necesita Python 3, sin dependencias.

    python3 backtest/replay.py --db db.sqlite3 --validate   # ¿reproduce las operaciones reales?
    python3 backtest/replay.py --db db.sqlite3 --detail     # compara las variantes de VARIANTS
    python3 backtest/replay.py --db db.sqlite3 --only-running --detail
    python3 backtest/replay.py --db db.sqlite3 --grid --detail

Para probar un cambio de lógica: añadir el parámetro a `Params`, implementarlo en
`simulate()` y registrar la variante en `VARIANTS`. `--cache DIR` evita releer la
BD en cada ejecución.

# research.py

Investigación de estrategias con histórico largo (velas y funding de los perpetuos
de Binance desde 2019, que `marketdata.py` descarga en `backtest/data/`). Motor de
cartera con costes, funding real, liquidaciones y límite de exposición. Los
parámetros se eligen con 2020-2023 y se evalúan con 2024 en adelante.

    python3 backtest/marketdata.py --extended --hourly   # descarga / actualiza
    python3 backtest/research.py                         # todas las familias
    python3 backtest/research.py --neighborhood          # parámetros vecinos
    python3 backtest/research.py --robust "xsmom 21d top4 L btc200"
    python3 backtest/research.py --bot-hourly --robust "xsmom 21d top4 L btc200"

`--bot-hourly` reconstruye el bot actual hora a hora (indicadores sobre la vela
diaria en curso, como TradingView) y lo simula con `replay.simulate`, con y sin el
filtro de régimen de BTC. `indicators.py` replica los indicadores de TradingView
(DI/ADX, ATR, Recommend.MA), también con la vela en curso.

# sltp.py

Rejilla de stop loss / take profit del bot sobre BTC, ETH y SOL (con el filtro de
régimen de BTC): niveles de SL y TP en múltiplos del R actual y TP condicionado a
checkRecommend(), forzado por el bot u orden TP en el exchange. Un ciclo por vela
de 15 min, que es lo que veía el bot con la caché de precios de ~20 min (su ATR
coincide con el registrado en `MT_strategystate`). Selección con 2020-2022 y
validación con 2023 en adelante, comparando también a igual volatilidad.

    python3 backtest/marketdata.py --m15 BTC,ETH,SOL,XRP,DOGE,BNB,ADA
    python3 backtest/sltp.py                              # BTC, ETH y SOL
    python3 backtest/sltp.py --symbols XRP,DOGE,BNB,ADA   # contraste con otros símbolos
    python3 backtest/sltp.py --slippage 0.002             # sensibilidad a costes
    python3 backtest/sltp.py --every 4                    # el bot decide cada 60 min

# ablation.py

Qué regla de `Strategy.operation()` aporta y cuál resta: cambia una cada vez
(stops, salida por DI, filtros de entrada, límites DI, régimen, cartera) y la
compara con el bot actual, con el simulador de `replay.py` sobre la reconstrucción
horaria del bot (23 símbolos y las 7 activas). Selección hasta 2023, evaluación
desde 2024. `--combo` acumula las reglas elegidas en selección (la propuesta) y
`--neighbors` comprueba que no dependen de un valor exacto.

    python3 backtest/marketdata.py --extended --hourly
    python3 backtest/ablation.py                             # una regla cada vez
    python3 backtest/ablation.py --group trailing
    python3 backtest/ablation.py --combo                     # propuesta, regla a regla
    python3 backtest/ablation.py --neighbors
    python3 backtest/ablation.py --combo --universe extended # monedas no usadas al elegir
    python3 backtest/ablation.py --combo --m15               # 7 activas, ciclos de 15 min

Sin `db.sqlite3` usa los límites DI y el apalancamiento de `db.sqlite3.source`.

# marketdata.py --vision

La API de Binance responde 451 desde algunas regiones (servidores en EE. UU.).
`--vision` descarga los mismos datos de su archivo público, data.binance.vision:

    python3 backtest/marketdata.py --vision --extended --hourly
    python3 backtest/marketdata.py --vision --m15 BTC,ETH,SOL,XRP,DOGE,BNB,ADA

# backtest.py / notebook

windows
install python with pip

linux
sudo apt install python3 python3-pip

python.exe -m pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --upgrade pip
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org pandas
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org notebook
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org ta
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org dtale
    

jupyter notebook



