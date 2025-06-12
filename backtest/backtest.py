#!/bin/python
# En primer lugar vamos a cargar las librerias necesarias.

import requests
import pandas as pd
import ta  # Biblioteca para calcular indicadores técnicos
import time
import json
import os

os.chdir('/home/moTrade/backtest')

bot_token = '7552649307:AAHEVtopJMeeTHCT1YgYpYR8-FKMbtV9bYI'
chat_id = '5350366399'
status_file = "operation_status.json"  # Archivo para almacenar el estado

## Memoria persistente

def send_telegram_message(message):
    """Envía un mensaje a Telegram."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message}
    response = requests.post(url, data=payload)
    if response.status_code == 200:
        print("Mensaje enviado a Telegram")
    else:
        print(f"Error al enviar mensaje: {response.text}")

def load_last_status():
    """Carga el estado de la última operación desde un archivo."""
    try:
        with open(status_file, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {"operation_open": False}
    except JSONDecodeError:
        return {"operation_open": False}

def save_last_status(status):
    """Guarda el estado de la última operación en un archivo."""
    with open(status_file, "w") as file:
        json.dump(status, file)


# Cargar y preprocesar los datos

# URL del archivo CSV
url = "https://www.cryptodatadownload.com/cdd/Binance_BTCUSDT_1h.csv"

# Cargar el CSV en un DataFrame
df = pd.read_csv(url, skiprows=1)
#df = pd.read_csv('Binance_BTCUSDT_1h.csv', skiprows=1)

# Ahora, convertimos el timestamp de UNIX a datetime y filtramos los ultimos 4 años (aproximado por 4*365)
# Asegúrate de que el DataFrame tiene las columnas necesarias
# El dataset contiene: Unix,Date,Symbol,Open,High,Low,Close,Volume BTC,Volume USDT,tradecount
# Convertir 'Unix' a timestamp para usarlo como índice

# Asegurarse de que 'Unix' es numérico
df['Unix'] = pd.to_numeric(df['Unix'], errors='coerce')

# Filtrar solo entradas con Unix válido (13 dígitos como máximo)
df = df[df['Unix'] <= 9999999999999]

df['timestamp'] = pd.to_datetime(df['Unix'], unit='ms')
df.set_index('timestamp', inplace=True)

# Y ordenarlo cronológicamente de mas antiguo a mas moderno
df.sort_index(inplace=True)

# Filtrar los últimos 4 años para el backtest
end_time = df.index.max() -pd.Timedelta(days=0)
start_time = end_time - pd.Timedelta(days=2*365+60)  # Aproximación de 4 años + 60 dias, para obtener bien los indicadores
df = df[(df.index >= start_time) & (df.index <= end_time)]

# Resample a 4h
df4= df.resample('1d').agg({
    'Open': 'first',
    'High': 'max',
    'Low': 'min',
    'Close': 'last',
    'Volume BTC': 'sum',  
    'Volume USDT': 'sum',  
    'tradecount': 'sum',  
})

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

# EMA50
df['ema50'] = ta.trend.ema_indicator(close=df['Close'], window=50)

# Y procedemos a filtrar los datos anteriores a la ventana deseada
end_time = df.index.max()
start_time = end_time - pd.Timedelta(days=2*365)  # Aproximación de 4 años
df = df[(df.index >= start_time) & (df.index <= end_time)]

# Generar señales (usando la estrategia anterior)
def generate_signals(df):
    # Crear columnas de señales inicializadas a 0
    df['long_entry'] = 0
    df['long_exit'] = 0
    df['short_entry'] = 0
    df['short_exit'] = 0

    last_feedback_time = time.time()
    for i in range(1, len(df)):
        # Mostrar progreso cada 5 segundos
        if time.time() - last_feedback_time >= 5:
            print(f"Generando señales: {i}/{len(df)} registros procesados...")
            last_feedback_time = time.time()

        # Condiciones para entrada en largo:
        # - RSI < 35 (ligera sobreventa) O precio <= banda de Bollinger inferior
        # - MACD > signal (momentum alcista)
        # - El precio actual > EMA50 (tendencia global alcista)
        if ((df['rsi'].iloc[i] < 35 or (df['Close'].iloc[i])*0.997 <= df['bollinger_lower'].iloc[i]) and
            df['Close'].iloc[i] > df['ema50'].iloc[i]):
            df.iloc[i, df.columns.get_loc('long_entry')] = 1

        # Salida de largo:
        # - RSI > 65 (algo sobrecomprado) O MACD < signal (pérdida de momentum) o si se rompe la banda superior
        if (df['rsi'].iloc[i] > 85 and (df['macd'].iloc[i] < df['signal'].iloc[i] or df['Close'].iloc[i] >= (df['bollinger_upper'].iloc[i])*1.005 )) :
            df.iloc[i, df.columns.get_loc('long_exit')] = 1

        # Entrada en corto:
        # - RSI > 65 (ligera sobrecompra) O precio >= banda de Bollinger superior
        # - MACD < signal (momentum bajista)
        # - El precio actual < EMA50 (tendencia global bajista)
        if ((df['rsi'].iloc[i] > 80 or df['Close'].iloc[i] >= df['bollinger_upper'].iloc[i]) and
            df['Close'].iloc[i] < df['ema50'].iloc[i]):
            df.iloc[i, df.columns.get_loc('short_entry')] = 0
               ## NUNCA

        # Salida de corto:
        # - RSI < 35 (vuelve a zona baja), MACD > signal (cambio a momentum alcista) o si se rompe la banda inferior
        # Aquí podrías usar un "o" para salir en cualquiera de las dos condiciones,
        # pero usar "y" puede asegurar que realmente hay un cambio de momentum.
        # Ajustar según preferencias.
        if (df['rsi'].iloc[i] < 30 and (df['macd'].iloc[i] > df['signal'].iloc[i] or df['Close'].iloc[i] <= df['bollinger_lower'].iloc[i])):
            df.iloc[i, df.columns.get_loc('short_exit')] = 1

    return df

# Aplicar la generación de señales
df = generate_signals(df)

# Backtesting con métricas

def backtest_with_details(df):
    balance = 10000  # Capital inicial
    position_bet=balance*0.80    # Cada posicion, un 5% del balance
    position = 0     # 0 = sin posición, 1 = largo, -1 = corto
    entry_price = 0
    trade_count = 0
    win_count = 0
    loss_count = 0
    profit_loss = []
    max_drawdown = 0
    peak_balance = balance

    # Detalles de todas las operaciones
    operations = []

    # Métricas separadas para operaciones long y short
    long_trade_count = 0
    long_win_count = 0
    long_loss_count = 0
    long_profit_loss = []

    short_trade_count = 0
    short_win_count = 0
    short_loss_count = 0
    short_profit_loss = []

    df['status']="WAIT"
    df['operation_open_price']=0.0
    df['operation_max_price']=0.0

    for i in range(len(df)):
        current_date = df.index[i]

        # StopLoss

        if position == 1 and df['Close'].iloc[i] < df['operation_max_price'].iloc[i-1] * 0.975:
            df.iloc[i, df.columns.get_loc('long_exit')] = 1

        if position == -1 and df['Close'].iloc[i] > df['operation_max_price'].iloc[i-1] * 1.04:
            df.iloc[i, df.columns.get_loc('short_exit')] = 1

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
                "profit": None,
                "profit_pct": None,
            })
            trade_count += 1
            long_trade_count += 1
            df.iloc[i, df.columns.get_loc('status')] = "LONG"
            df.iloc[i, df.columns.get_loc('operation_open_price')] = entry_price
            df.iloc[i, df.columns.get_loc('operation_max_price')] = entry_price

        # Cerrar posición larga
        elif df['long_exit'].iloc[i] == 1 and position == 1:
            exit_price = df['Close'].iloc[i]
            trade_profit = (exit_price - entry_price) * position
            trade_profit_pct = trade_profit / entry_price
            trade_profit = position_bet*trade_profit_pct*10
            balance = balance + trade_profit    # Capital inicial
            position_bet=balance*0.80                            # Cada posicion, un 80% del balance            profit_loss.append(trade_profit)
            operations[-1].update({
                "exit_date": current_date,
                "exit_price": exit_price,
                "profit": trade_profit,
                "profit_pct": trade_profit_pct,
                "balance": balance,
            })
            df.iloc[i, df.columns.get_loc('status')] = "CLOSE"
            df.iloc[i, df.columns.get_loc('operation_open_price')] = df['operation_open_price'].iloc[i-1]
            df.iloc[i, df.columns.get_loc('operation_max_price')] = max(df['operation_max_price'].iloc[i-1], df['High'].iloc[i])

            # Actualizar métricas globales
            if trade_profit > 0:
                win_count += 1
                long_win_count += 1
            else:
                loss_count += 1
                long_loss_count += 1
            long_profit_loss.append(trade_profit)
            position = 0



        # Mantener posicion larga
        elif position == 1:
            df.iloc[i, df.columns.get_loc('status')] = "LONG"
            df.iloc[i, df.columns.get_loc('operation_open_price')] = df['operation_open_price'].iloc[i-1]
            df.iloc[i, df.columns.get_loc('operation_max_price')] = max(df['operation_max_price'].iloc[i-1], df['High'].iloc[i])

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
                "profit": None,
                "profit_pct": None,
                "balance": None
          })
            trade_count += 1
            short_trade_count += 1
            df.iloc[i, df.columns.get_loc('status')] = "SHORT"
            df.iloc[i, df.columns.get_loc('operation_open_price')] = entry_price
            df.iloc[i, df.columns.get_loc('operation_max_price')] = entry_price          

        # Cerrar posición corta
        elif df['short_exit'].iloc[i] == 1 and position == -1:
            exit_price = df['Close'].iloc[i]
            trade_profit = (entry_price - exit_price) * abs(position)
            trade_profit_pct = trade_profit / exit_price
            trade_profit = position_bet*trade_profit_pct*10
            balance = balance + trade_profit    # Capital inicial
            position_bet=balance*0.80                           # Cada posicion, un 80% del balance            profit_loss.append(trade_profit)
            operations[-1].update({
                "exit_date": current_date,
                "exit_price": exit_price,
                "profit": trade_profit,
                "profit_pct": trade_profit_pct,                
                "balance": balance,
            })
            df.iloc[i, df.columns.get_loc('status')] = "CLOSE"
            df.iloc[i, df.columns.get_loc('operation_open_price')] = df['operation_open_price'].iloc[i-1]
            df.iloc[i, df.columns.get_loc('operation_max_price')] = min(df['operation_max_price'].iloc[i-1], df['Low'].iloc[i])

            # Actualizar métricas globales
            if trade_profit > 0:
                win_count += 1
                short_win_count += 1
            else:
                loss_count += 1
                short_loss_count += 1
            short_profit_loss.append(trade_profit)
            position = 0



        # Mantener posicion larga
        elif position == -1:
            df.iloc[i, df.columns.get_loc('status')] = "SHORT"
            df.iloc[i, df.columns.get_loc('operation_open_price')] = df['operation_open_price'].iloc[i-1]
            df.iloc[i, df.columns.get_loc('operation_max_price')] = min(df['operation_max_price'].iloc[i-1], df['Low'].iloc[i])

        # Calcular drawdown
        peak_balance = max(peak_balance, balance)
        drawdown = peak_balance - balance
        max_drawdown = max(max_drawdown, drawdown)

    # Métricas globales
    win_rate = win_count / trade_count if trade_count > 0 else 0
    avg_profit_loss = sum(profit_loss) / len(profit_loss) if profit_loss else 0

    # Métricas para operaciones long
    long_win_rate = long_win_count / long_trade_count if long_trade_count > 0 else 0
    long_avg_profit_loss = sum(long_profit_loss) / len(long_profit_loss) if long_profit_loss else 0

    # Métricas para operaciones short
    short_win_rate = short_win_count / short_trade_count if short_trade_count > 0 else 0
    short_avg_profit_loss = sum(short_profit_loss) / len(short_profit_loss) if short_profit_loss else 0

    return {
        "final_balance": balance,
        "trade_count": trade_count,
        "win_rate": win_rate,
        "average_profit_loss": avg_profit_loss,
        "max_drawdown": max_drawdown,
        "operations": operations,
        "long_trade_count": long_trade_count,
        "long_win_rate": long_win_rate,
        "long_average_profit_loss": long_avg_profit_loss,
        "short_trade_count": short_trade_count,
        "short_win_rate": short_win_rate,
        "short_average_profit_loss": short_avg_profit_loss,
        "df": df
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
print("-- Operaciones LONG")
print(f"Total operaciones: {results['long_trade_count']:.2f}")
print(f"Tasa de éxito: {results['long_win_rate']:.2%}")
print(f"Ganancia/pérdida promedio: {results['long_average_profit_loss']:.2f}")
print("-- Operaciones SHORT")
print(f"Total operaciones: {results['short_trade_count']:.2f}")
print(f"Tasa de éxito: {results['short_win_rate']:.2%}")
print(f"Ganancia/pérdida promedio: {results['short_average_profit_loss']:.2f}")

# Mostrar detalles de las operaciones
print("\nDetalles de las operaciones:")
for op in results['operations']:

    exit_date = op['exit_date'] if op['exit_date'] is not None else ''
    exit_price = f"{op['exit_price']:.2f}" if op['exit_price'] is not None else ''
    profit = f"{op['profit']:.2f}" if op['profit'] is not None else ''
    profit_pct = f"{op['profit_pct']:.2f}" if op['profit_pct'] is not None else ''
    balance = f"{op['balance']:.2f}" if 'balance' in op and op['balance'] is not None else ''

    print(f"Tipo: {op['type']} | Fecha entrada: {op['entry_date']} | Precio entrada: {op['entry_price']:.2f} | "
          f"Fecha salida: {exit_date} | "
          f"Precio salida: {exit_price} | "
          f"Ganancia: {profit} | "
          f"PCT: {profit_pct} | "
          f"Balance: {balance} "
          )


last_operation = results['operations'][-1]  # Obtiene la última operación

last_status = load_last_status()

if last_operation['exit_date'] is None:  # Operación no cerrada
    if not last_status.get("operation_open", False):  # Sólo enviar si no se envió antes
        message = (
            f"ALERTA: Operación abierta.\n"
            f"Tipo: {last_operation['type']}\n"
            f"Entrada: {last_operation['entry_price']}\n"
            f"Fecha entrada: {last_operation['entry_date']}"
        )
        send_telegram_message(message)
        # Actualizar estado
        save_last_status({"operation_open": True})
else:  # Operación cerrada
    if last_status.get("operation_open", False):  # Sólo enviar si estaba abierta antes
        message = (
            f"ALERTA: Operación cerrada.\n"
            f"Tipo: {last_operation['type']}\n"
            f"Entrada: {last_operation['entry_price']}\n"
            f"Salida: {last_operation['exit_price']}\n"
            f"Ganancia: {last_operation['profit']}\n"
            f"Fecha entrada: {last_operation['entry_date']}\n"
            f"Fecha salida: {last_operation['exit_date']}"
        )
        send_telegram_message(message)
        # Actualizar estado
        save_last_status({"operation_open": False})