import pandas as pd
import ta  # Biblioteca para calcular indicadores técnicos
import time

# Cargar datos históricos
# URL del archivo CSV
url = "https://www.cryptodatadownload.com/cdd/Binance_BTCUSDT_1h.csv"

# Cargar el CSV en un DataFrame
df = pd.read_csv(url)

# Mostrar las primeras filas del DataFrame
df.head()

# Asegúrate de que el DataFrame tiene las columnas necesarias
# El dataset contiene: Unix,Date,Symbol,Open,High,Low,Close,Volume BTC,Volume USDT,tradecount
# Convertir 'Unix' a timestamp para usarlo como índice

df['timestamp'] = pd.to_datetime(df['Unix'], unit='ms')
df.set_index('timestamp', inplace=True)

# Filtrar los últimos 4 años para el backtest
end_time = df.index.max()
start_time = end_time - pd.Timedelta(days=60)  # Aproximación de 4 años
df = df[(df.index >= start_time) & (df.index <= end_time)]

# Calcular indicadores técnicos
# RSI
df['rsi'] = ta.momentum.RSIIndicator(close=df['Close'], window=14).rsi()

# MACD
macd = ta.trend.MACD(close=df['Close'])
df['macd'] = macd.macd()
df['signal'] = macd.macd_signal()

# Bollinger Bands
bollinger = ta.volatility.BollingerBands(close=df['Close'], window=20)
df['bollinger_upper'] = bollinger.bollinger_hband()
df['bollinger_lower'] = bollinger.bollinger_lband()

# Generar señales (usando la estrategia anterior)
def generate_signals(df):
    df['long_entry'] = 0
    df['long_exit'] = 0
    df['short_entry'] = 0
    df['short_exit'] = 0

    last_feedback_time = time.time()
    for i in range(1, len(df)):
        if time.time() - last_feedback_time >= 5:
            print(f"Generando señales: {i}/{len(df)} registros procesados...")
            last_feedback_time = time.time()

        if df['rsi'].iloc[i] < 30 and df['Close'].iloc[i] <= df['bollinger_lower'].iloc[i]:
            df.at[i, 'long_entry'] = 1

        if df['rsi'].iloc[i] > 70 or df['macd'].iloc[i] < df['signal'].iloc[i]:
            df.at[i, 'long_exit'] = 1

        if df['rsi'].iloc[i] > 70 and df['Close'].iloc[i] >= df['bollinger_upper'].iloc[i]:
            df.at[i, 'short_entry'] = 1

        if df['rsi'].iloc[i] < 30 or df['macd'].iloc[i] > df['signal'].iloc[i]:
            df.at[i, 'short_exit'] = 1

    return df

# Aplicar la generación de señales
df = generate_signals(df)

# Backtesting con métricas

def backtest_with_details(df):
    balance = 10000  # Capital inicial
    position = 0  # No tenemos posiciones abiertas
    entry_price = 0
    trade_count = 0
    win_count = 0
    loss_count = 0
    profit_loss = []
    max_drawdown = 0
    peak_balance = balance

    # Lista para almacenar detalles de las operaciones
    operations = []

    for i in range(len(df)):
        current_date = df.index[i]
        print (current_date)

        # Abrir posición larga
        if df['long_entry'].iloc[i] == 1 and position == 0:
            position = 1
            entry_price = df['Close'].iloc[i]
            operations.append({
                "entry_date": current_date,
                "entry_price": entry_price,
                "type": "long",
                "exit_date": None,
                "exit_price": None,
                "profit": None
            })
            trade_count += 1

        # Cerrar posición larga
        elif df['long_exit'].iloc[i] == 1 and position == 1:
            exit_price = df['Close'].iloc[i]
            trade_profit = (exit_price - entry_price) * position
            balance += trade_profit
            profit_loss.append(trade_profit)
            operations[-1].update({
                "exit_date": current_date,
                "exit_price": exit_price,
                "profit": trade_profit
            })
            if trade_profit > 0:
                win_count += 1
            else:
                loss_count += 1
            position = 0

        # Abrir posición corta
        if df['short_entry'].iloc[i] == 1 and position == 0:
            position = -1
            entry_price = df['Close'].iloc[i]
            operations.append({
                "entry_date": current_date,
                "entry_price": entry_price,
                "type": "short",
                "exit_date": None,
                "exit_price": None,
                "profit": None
            })
            trade_count += 1

        # Cerrar posición corta
        elif df['short_exit'].iloc[i] == 1 and position == -1:
            exit_price = df['Close'].iloc[i]
            trade_profit = (entry_price - exit_price) * abs(position)
            balance += trade_profit
            profit_loss.append(trade_profit)
            operations[-1].update({
                "exit_date": current_date,
                "exit_price": exit_price,
                "profit": trade_profit
            })
            if trade_profit > 0:
                win_count += 1
            else:
                loss_count += 1
            position = 0

        # Calcular drawdown
        peak_balance = max(peak_balance, balance)
        drawdown = peak_balance - balance
        max_drawdown = max(max_drawdown, drawdown)

    win_rate = win_count / trade_count if trade_count > 0 else 0
    avg_profit_loss = sum(profit_loss) / len(profit_loss) if profit_loss else 0

    return {
        "final_balance": balance,
        "trade_count": trade_count,
        "win_rate": win_rate,
        "average_profit_loss": avg_profit_loss,
        "max_drawdown": max_drawdown,
        "operations": operations
    }

# Ejecutar el backtest
results = backtest_with_details(df)

# Mostrar resultados
print("Resultados del backtesting:")
print(f"Balance final: {results['final_balance']:.2f}")
print(f"Número de operaciones: {results['trade_count']}")
print(f"Tasa de éxito: {results['win_rate']:.2%}")
print(f"Ganancia/pérdida promedio: {results['average_profit_loss']:.2f}")
print(f"Máximo drawdown: {results['max_drawdown']:.2f}")

# Mostrar detalles de las operaciones
print("\nDetalles de las operaciones:")
for op in results['operations']:
    print(f"Tipo: {op['type']} | Fecha entrada: {op['entry_date']} | Precio entrada: {op['entry_price']:.2f} | "
          f"Fecha salida: {op['exit_date']} | Precio salida: {op['exit_price']:.2f} | "
          f"Ganancia: {op['profit']:.2f}")
