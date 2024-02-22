## API to exchange docs
## This is what moTrade expects from API
## This DOC should assist in creating a new API for a different exchange
## Work In Progress

### GET POSITION

curl -X POST http://127.0.0.1:5001/get_position

when the order is still open
{"code":0,"msg":"","data":{"order":{"symbol":"BTC-USDT","orderId":1735556416452698112,"side":"BUY","positionSide":"LONG","type":"MARKET","origQty":"0.0023","price":"42599.1","executedQty":"0.0023","avgPrice":"42599.2","cumQuote":"98","stopPrice":"","profit":"0.0000","commission":"-0.048989","status":"FILLED","time":1702623869418,"updateTime":1702623869486,"clientOrderId":"","leverage":"20X","takeProfit":{"type":"","quantity":0,"stopPrice":0,"price":0,"workingType":""},"stopLoss":{"type":"","quantity":0,"stopPrice":0,"price":0,"workingType":""},"advanceAttr":0,"positionID":0,"takeProfitEntrustPrice":0,"stopLossEntrustPrice":0,"orderType":"","workingType":"MARK_PRICE"}}}

when the order is closed
{"code":0,"msg":"","data":{"order":{"symbol":"BTC-USDT","orderId":1735556416452698112,"side":"BUY","positionSide":"LONG","type":"MARKET","origQty":"0.0023","price":"42599.1","executedQty":"0.0023","avgPrice":"42599.2","cumQuote":"98","stopPrice":"","profit":"0.0000","commission":"-0.048989","status":"FILLED","time":1702623869418,"updateTime":1702623869486,"clientOrderId":"","leverage":"20X","takeProfit":{"type":"","quantity":0,"stopPrice":0,"price":0,"workingType":""},"stopLoss":{"type":"","quantity":0,"stopPrice":0,"price":0,"workingType":""},"advanceAttr":0,"positionID":0,"takeProfitEntrustPrice":0,"stopLossEntrustPrice":0,"orderType":"","workingType":"MARK_PRICE"}}}


@app.route("/get_position", methods=['POST'])

    def get_position(self, position_id) :
        data='{"order_id": '+str(position_id)+' }'
        headers = {'Content-Type': 'application/json',}
        response = requests.post(
            'http://127.0.0.1:5000/get_position', 
            headers=headers, 
            data=data)
        return response.json()[0], response.json()[1]
                true o false         la position
                                    orders: [
                                              { 
                                                "side": "sell" o "buy"                      buy or sell. auto explicatorio
                                              }
                                    ]
                                    position { "buy_amount": nnn.nnnn,                      dinero de compra (con leverage)
                                               "sell_amount": nnn.nnnn,                     dinero de venta (con leverage)
                                               "close_at": nnnnnnnnnnn,                     timestamp de hora de cierre
                                            }                         

curl -H 'Content-Type: application/json' -d '{ "order_id":"3205243162"}' -X POST http://127.0.0.1:5000/get_position       


### GET BALANCE
test


curl -X POST http://127.0.0.1:5000/get_balance
curl -X POST http://127.0.0.1:5001/get_balance

@app.route("/get_balance", methods=['GET','POST'])

### CLOSE POSITION
@app.route("/close_position", methods=['POST'])

### BUY ORDER

test

curl -H 'Content-Type: application/json' -d '{"instrument_type" : "crypto", "instrument_id" : "BTCUSD", "instrument_id_bingx" : "BTC-USDT", "side" : "buy", "amount" : "100", "leverage" : "2", "type" : "marxket", "limit_price" : "", "stop_lose_kind" : "", "stop_lose_value" : "", "use_trail_stop" : ""}' -X POST http://127.0.0.1:5001/buy_order       


call to api

    def buy_order(self, instrument_type, instrument_id, side, 
        amount, leverage, type, limit_price=None, stop_lose_kind=None, 
        stop_lose_value=None, use_trail_stop=None) :
        data= {
             }
        headers = {'Content-Type': 'application/json',}
        response = requests.post(
            'http://127.0.0.1:5000/buy_order', 
            headers=headers, 
            data=json.dumps(data))
        return response.json()[0], response.json()[1]

calls to proc

        if self.protectedTrade :
             check,order_id=self.buy_order(
                instrument_type="crypto",
                instrument_id=self.operSymbol,
                side="buy",
                amount=self.amount,
                leverage=2,
                #type="limit", limit_price=self.ema,
                type="market",
                stop_lose_kind="percent", stop_lose_value=self.stopLoss,
                use_trail_stop=True)
             self.placedPrice=self.ema
        else :
            check,order_id=self.buy_order(
                instrument_type="crypto",
                instrument_id=self.operSymbol,
                side="buy",
                amount=self.amount,
                leverage=2,
                type="market")


        if self.protectedTrade :
             check,order_id=self.buy_order(
                instrument_type="crypto",
                instrument_id=self.operSymbol,
                side="sell",
                amount=self.amount,
                leverage=2,
                #type="limit", limit_price=self.ema,
                type="market",
                stop_lose_kind="percent", stop_lose_value=self.stopLoss,
                use_trail_stop=True)
             self.placedPrice=self.ema
        else :
            check,order_id=self.buy_order(
                instrument_type="crypto",
                instrument_id=self.operSymbol,
                side="sell",
                amount=self.amount,
                leverage=2,
                type="market")

## Estas son para el protected trade y no son imprescindibles.


@app.route("/cancel_order", methods=['POST'])

@app.route("/get_candle", methods=['POST'])