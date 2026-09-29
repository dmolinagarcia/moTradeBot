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



