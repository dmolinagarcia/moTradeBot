#!/usr/bin/env python
# Obsolete IQOption API
# No longer supported

from iqoptionapi.stable_api import IQ_Option
import time
import logging
import sys
import signal
import threading
from json2html import *

IQ=IQ_Option("USERNAME","PASSWORD")

IQ.connect()
IQ.change_balance("REAL")

################################################################################### API 
from flask import Flask, json, request

app = Flask(__name__)

@app.route("/get_position", methods=['POST'])
def get_position():
    while not IQ.check_connect() :
        IQ.connect()
        IQ.change_balance("REAL")
    order_id=request.json['order_id'] 
    return json.dumps(IQ.get_position(order_id))

@app.route("/buy_order", methods=['POST'])
def buy_order():
    while not IQ.check_connect() :
        IQ.connect()
        IQ.change_balance("REAL")
    
    instrument_type=request.json['instrument_type'] 
    instrument_id=request.json['instrument_id'] 
    side=request.json['side']
    amount=request.json['amount']
    leverage=request.json['leverage']
    type=request.json['type']
    limit_price=request.json['limit_price']
    stop_lose_kind=request.json['stop_lose_kind']
    stop_lose_value=request.json['stop_lose_value']
    stop_lose_value=1.5 
    use_trail_stop=request.json['use_trail_stop']
    if stop_lose_kind=="percent" :
        take_profit_kind = "percent"
        take_profit_value = stop_lose_value*2
        take_profit_value = 2.5
    else:
        take_profit_kind = None
        take_profit_value = None


    return json.dumps(IQ.buy_order(
        instrument_type=instrument_type,
        instrument_id=instrument_id,
        side=side,
        amount=amount,
        leverage=leverage,
        type=type,
        limit_price=limit_price,
        stop_lose_kind=stop_lose_kind,
        stop_lose_value=stop_lose_value,
        take_profit_kind=take_profit_kind,
        take_profit_value=take_profit_value,
        use_trail_stop=use_trail_stop
    ))

@app.route("/close_position", methods=['POST'])
def close_position():
    while not IQ.check_connect() :
        IQ.connect()
        IQ.change_balance("REAL")

    order_id=request.json['order_id']
    return json.dumps(IQ.close_position(order_id))

@app.route("/cancel_order", methods=['POST'])
def cancel_order ():
    while not IQ.check_connect() :
        IQ.connect()
        IQ.change_balance("REAL")

    order_id=request.json['order_id']
    return json.dumps(IQ.cancel_order(order_id))

@app.route("/get_balance", methods=['GET','POST'])
def get_balance ():
    while not IQ.check_connect() :
        IQ.connect()
        IQ.change_balance("REAL")

    return json.dumps(IQ.get_balance())             

@app.route("/get_candle", methods=['POST'])
def get_candle ():
    while not IQ.check_connect() :
        IQ.connect()
        IQ.change_balance("REAL")
    
    operSymbol=request.json['operSymbol']
    candles=IQ.get_candles(operSymbol,14400,3,time.time())

    resultado=0
    if candles[0]['open'] < candles[0]['close'] :
        resultado=resultado+0.5
    else :
        resultado=resultado-0.5

    if candles[1]['open'] < candles[1]['close'] :
        resultado=resultado+0.5
    else :
        resultado=resultado-0.5

    print (resultado)

    return json.dumps(resultado)

############################################################################### FIN API

app.run(port=5000)
