# !/usr/bin/env python

import time
import logging
import sys
import signal
import threading
import requests
import hmac
from hashlib import sha256
from json2html import *

### VARIABLES
from BINGXCFG import APIURL, SECRETKEY, APIKEY

################################################################################### API 
from flask import Flask, json, request
app = Flask(__name__)

pricesData = None
pricesTS = 0


@app.route("/get_price", methods=['POST'])
def get_price():
    # Llamada al API de BINGX para obtener el current price

    global pricesTS
    global pricesData

    # If pricesTS is older than 10 minuts, refresh pricesData
    if time.time() > pricesTS + 1200 :
        app.logger.error("Updating pricesData at " + (str)(time.time()))
        pricesTS = time.time()
 
        # Updating prices
        payload = {}
        path = '/openApi/swap/v2/server/time'
        method = "GET"
        paramsMap = { }
        paramsStr = parseParam(paramsMap)
        currentTS=json.loads(send_request(method, path, paramsStr, payload))['data']['serverTime']

        payload = {}
        path = '/openApi/swap/v1/ticker/price'
        method = "GET"
        paramsMap = { "timestamp": currentTS }
        paramsStr = parseParam(paramsMap)
        pricesData=json.loads(send_request(method, path, paramsStr, payload))['data']

    # get Price from pricesData
    for price in pricesData :
        if price['symbol'] == request.json['instrument_id_bingx'] :
            app.logger.error ('Return from cache will is ' + (str)(price))
            return price

    # If we are here, price is not in pricesData, so we ask for it

    payload = {}
    path = '/openApi/swap/v2/quote/price'
    method = "GET"
    paramsMap = { "symbol": request.json['instrument_id_bingx'] }
    paramsStr = parseParam(paramsMap)
    response = send_request(method, path, paramsStr, payload)

    try :
        price=(json.loads(response)['data']['price'])
        app.logger.error ('Return will from BINGX will is ' + (str)(json.loads(response)['data'] ))
        return json.loads(response)['data']    
    except :
        return '{"symbol":"xxx-xxxx","price":"-1","time":0}'
    


@app.route("/buy_order", methods=['POST'])
def buy_order():
 
    # First we get the price to calculate the amount to buy
    # moTrade passes how mucho money to buy, but bingx expects amount of crypto coins
    # tener en cuenta el leverage. no es cuanto compro, si no cuanto obtengo con leverage
    # la logica me dice que tengo que multiplicar el amount por el leverage antes de abrir la operacion
    # de esta forma, gastare x de mi balance, comprando al leverage que indique
    # por lo que el bet lo puedo seguir calculando a partir del balance (availableMargin en realidad)

    payload = {}
    path = '/openApi/swap/v2/quote/price'
    method = "GET"
    paramsMap = { "symbol": request.json['instrument_id_bingx'] }
    paramsStr = parseParam(paramsMap)
    response = send_request(method, path, paramsStr, payload)
    price=((float)(json.loads(response)['data']['price']))
    amount=(float)(request.json['amount'])*(float)(request.json['leverage'])/price

    # Calculate positionSide based on side
    if request.json['side'] == 'buy' :
        positionSide = "LONG"
    else :
        positionSide = "SHORT"

    # Set LEVERAGE
    payload = {}
    path = '/openApi/swap/v2/trade/leverage'
    method = "POST"
    paramsMap = {
        "symbol": request.json['instrument_id_bingx'],
        "side": positionSide,
        "leverage": request.json['leverage'] 
    }
    paramsStr = parseParam(paramsMap)
    send_request(method, path, paramsStr, payload)

    # Place order
    # query order id?
    
    payload = {}
    path = '/openApi/swap/v2/trade/order'
    method = "POST"
    paramsMap = {
        "symbol"         : request.json['instrument_id_bingx']         ,
        "type"           : (request.json['type']).upper()              ,
        "side"           : (request.json['side']).upper()              , 
        "positionSide"   : positionSide                                ,
        "quantity"       : (str)(amount) 
    }
    paramsStr = parseParam(paramsMap)

    #Hay que ajustar el return para que sea lo que motrade espera (status, orderid)
    retorno=json.loads(send_request(method, path, paramsStr, payload))
    app.logger.error(retorno)
    if retorno['code'] == 0 :
        check = "true"
        orderId = (str) (retorno ['data']['order']['orderId'])
    else :
        check = "false"
        orderId = "-1"

    app.logger.error("["+check+","+orderId+"]")
    return "["+check+","+orderId+"]"

@app.route("/close_position", methods=['POST'])
def close_position():
#close/sell LONG: side=SELL & positionSide=LONG
#close/buy SHORT: side=BUY & positionSide=SHORT
    
# how to close a full position? can it be done?
# si no, con el order_id, obtener el total de units compradas    
# en IQ solo devuelve true or false
# en BINGX debemos devolver el nuevo ORDERID    
# hay que modificar el  model para que guardae el closeorderid
# ademas el beneficio... el model lo obtiene con un get position si el cierre es OK
# no se como hacerlo en bingx            

    # Primero, query order. necesitamos el market, el side, el amount...

    payload = {}
    path = '/openApi/swap/v2/trade/order'
    method = "GET"
    paramsMap = {
        "symbol"            : request.json['instrument_id_bingx']         ,
        "orderId"           : request.json['order_id']                    ,
        "recvWindow": 0
    }
    paramsStr = parseParam(paramsMap)
    response=send_request(method, path, paramsStr, payload)
    side=json.loads(response)['data']['order']['side']
    type=json.loads(response)['data']['order']['type']
    executedQty=json.loads(response)['data']['order']['executedQty']
    # Calculate positionSide based on side
    if side == 'SELL' :
        side = "BUY"
        positionSide = "SHORT"
    else :
        side = "SELL"
        positionSide = "LONG" 

    # Close Order
    payload = {}
    path = '/openApi/swap/v2/trade/order'
    method = "POST"
    paramsMap = {
        "symbol"         : request.json['instrument_id_bingx']         ,
        "type"           : type                                        ,
        "side"           : side                                        ,
        "positionSide"   : positionSide                                ,
        "quantity"       : executedQty
    }
    paramsStr = parseParam(paramsMap)

    #Hay que ajustar el return para que sea lo que motrade espera (status, orderid)
    retorno=json.loads(send_request(method, path, paramsStr, payload))
    if retorno['code'] == 0 :
        check = "true"
        orderId = (str) (retorno ['data']['order']['orderId'])
    else :
        check = "false"
        orderId = "-1"
    return "["+check+","+orderId+"]"
 


@app.route("/get_balance", methods=['GET','POST'])
def get_balance ():
    payload = {}
    path = '/openApi/swap/v2/user/balance'
    method = "GET"
    paramsMap = {
        "recvWindow": 0
    }
    paramsStr = parseParam(paramsMap)
    retorno = json.loads(send_request(method, path, paramsStr, payload))
    return retorno['data']['balance']['availableMargin']

@app.route("/get_account", methods=['GET'])
def get_account ():
    payload = {}
    path = '/openApi/swap/v2/user/balance'
    method = "GET"
    paramsMap = {
        "recvWindow": 0
    }
    paramsStr = parseParam(paramsMap)
    retorno = json.loads(send_request(method, path, paramsStr, payload))
    return retorno

@app.route("/get_markets", methods=['GET'])
def get_markets():
    payload = {}
    path = '/openApi/swap/v2/quote/contracts'
    method = "GET"
    paramsMap = {}
    paramsStr = parseParam(paramsMap)
    return send_request(method, path, paramsStr, payload)


@app.route("/get_position", methods=['POST'])
def get_position():

# GET Server Time to form valid requests

    payload = {}
    path = '/openApi/swap/v2/server/time'
    method = "GET"
    paramsMap = { }
    paramsStr = parseParam(paramsMap)
    currentTS=json.loads(send_request(method, path, paramsStr, payload))['data']['serverTime']

# GET open positions for requested SYMBOS
    payload = {}
    path = '/openApi/swap/v2/user/positions'
    method = "GET"
    paramsMap = {
        "timestamp": currentTS ,
        'symbol' : request.json['instrument_id_bingx']
    }
    paramsStr = parseParam(paramsMap)
    response=send_request(method, path, paramsStr, payload)
    currentProfit=0

# EVALUATE returned position
    try:
        dataLen=len(json.loads(response)['data'])
        dataCheck=json.loads(response)['code']
        if dataLen == 0 and dataCheck == 0 :
        # Valid response, but empty data
        # Means no open position
            currentProfit=-9999
            if (int)(request.json['order_id_close']) == 0 :
                # Aqui entramos si la orden esta cerrada, pero moTrade no lo sabe
                # Es decir, lo esperado es un cierre por liquidacion / stopLoss
                # Si el cierre es por moTrade, tenemos order_id_close y no entramos en este trozo de log
                # Si realmente es un notOpen, lo veremos en BINGX por que la orden seguirá existiendo
                # Si no es un notOpen... investigaremos.
                # en real trade. Si pido las ordenes, la ultima sera la de cierre!

                app.logger.error(request.json['instrument_id_bingx'] )
                app.logger.error(request.json)
                app.logger.error("En ocasiones me entrado por aqui cuando no estaba cerrada")
                app.logger.error("Asi que hay algo mas..... Meto este debug para ver que hay en la psicion")
                app.logger.error(response)
                app.logger.error("Fin del debug para el notOpen invalido")
        elif dataCheck == 0 :
        # Valid response with data
        # Means position is open
        # Calculate real profit and continue
            unrealizedProfit=(float)(json.loads(response)['data'][0]['unrealizedProfit'])
            initialMargin=(float)(json.loads(response)['data'][0]['initialMargin'])
            realisedProfit=(float)(json.loads(response)['data'][0]['realisedProfit'])
            currentProfit=(unrealizedProfit + 2 * realisedProfit)
        else :
            app.logger.error ("Error al obtener la posicion : " + (str)(dataCheck) + " " + json.loads(response)['code'])
            return '[false,{}]'
    except:
        app.logger.error ( "Error calculando el beneficio actual para "+request.json['instrument_id_bingx'] )
        app.logger.error ( response )
        app.logger.error ( "Sospecho que esto pasa si la respuesta es erronea ")
        return '[false,{}]'

        
    
    close_at="0"
    buy_amount=0
    sell_amount=0
                        
    payload = {}
    path = '/openApi/swap/v2/trade/order'
    method = "GET"
    paramsMap = {
        "symbol"            : request.json['instrument_id_bingx']         ,
        "orderId"           : request.json['order_id']                    ,
        "recvWindow": 0
    }
    paramsStr = parseParam(paramsMap)
    retorno1 = json.loads(send_request(method, path, paramsStr, payload))
    check1   = retorno1['code']
    try :
        order1   = retorno1['data']['order']
        payload = {}
        paramsMap = {
            "symbol"            : request.json['instrument_id_bingx']         ,
            "orderId"           : request.json['order_id_close']              ,
            "recvWindow": 0
        }

        check2=-1

        if (int)(request.json['order_id_close']) > 0 :
            paramsStr = parseParam(paramsMap)
            retorno2 = json.loads(send_request(method, path, paramsStr, payload))
            check2   = retorno2['code']
            order2   = retorno2['data']['order']
    
        if check1 == 0 :
            check="true"
            side=order1['side'].lower()
            if side == "buy" :
                buy_amount=(float)(order1['executedQty'])*(float)(order1['avgPrice'])-(float)(order1['commission'])
            else :
                sell_amount=(float)(order1['executedQty'])*(float)(order1['avgPrice'])+(float)(order1['commission'])
        else :
            check="false"

        if request.json['order_id_close'] is not None and check2 == 0 :
            close_at=(str)(order2['time'])
            if side == "buy" :
                sell_amount=(float)(order2['executedQty'])*(float)(order2['avgPrice'])+(float)(order2['commission'])
            else :
                buy_amount=(float)(order2['executedQty'])*(float)(order2['avgPrice'])-(float)(order2['commission'])

        ## All data is ready, except for closed position
        if currentProfit == -9999 :
	## Position is closed
        ## Get last Order and return it
            payload = {}
            path = '/openApi/swap/v2/trade/allOrders'
            method = "GET"
            paramsMap = {
                "limit": "500",
                "symbol": request.json['instrument_id_bingx'] ,
                "timestamp": currentTS
            }
            paramsStr = parseParam(paramsMap)
            orderHistory=json.loads(send_request(method, path, paramsStr, payload))['data']['orders']
            lastOrder=len(orderHistory)-1
            orderIDclose=orderHistory[lastOrder]['orderId']
            data = '['+check+',{"orders":[{"side":"'+side+'"}],"position":{"buy_amount":'+(str)(buy_amount)+', "close_at": '+(str)(close_at)+',"sell_amount":'+(str)(sell_amount)+',"currentProfit":'+(str)(currentProfit)+',"isPositionOpen":"false","orderIDClose":'+(str)(orderIDclose)+'}}]'
        else :
        ## Position is not closed
            data = '['+check+',{"orders":[{"side":"'+side+'"}],"position":{"buy_amount":'+(str)(buy_amount)+', "close_at": '+(str)(close_at)+',"sell_amount":'+(str)(sell_amount)+',"currentProfit":'+(str)(currentProfit)+',"isPositionOpen":"true","orderIDClose":"-1"}}]'
    except:
        data = '[false,{}]'

        app.logger.exception (data)

    return (data)

############################################################################### FIN API

############################################################################### SUPPORT FUNCTIONS

def get_sign(api_secret, payload):
    signature = hmac.new(api_secret.encode("utf-8"), payload.encode("utf-8"), digestmod=sha256).hexdigest()
    # print("sign=" + signature)
    return signature

def send_request(method, path, urlpa, payload):
    url = "%s%s?%s&signature=%s" % (APIURL, path, urlpa, get_sign(SECRETKEY, urlpa))
    # print(url)
    headers = {
        'X-BX-APIKEY': APIKEY,
    }
    response = requests.request(method, url, headers=headers, data=payload)
    return response.text

def parseParam(paramsMap):
    sortedKeys = sorted(paramsMap)
    paramsStr = "&".join(["%s=%s" % (x, paramsMap[x]) for x in sortedKeys])
    return paramsStr+"&timestamp="+str(int(time.time() * 1000))

############################################################################### END FUNCTIONS

## Start Server
app.run(port=5000) 
