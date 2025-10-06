# -*- coding: utf-8 -*-

import json
import requests
import logging

logger = logging.getLogger("MT.models")

## No exception handling here. All exceptions are handled in the strategy.

# ── GETS ──────────────────────────────────────────────────────────────────────────────────────────
def get_position(position_id, order_id_close, instrument_id_bingx):
    """Gets the current position from the local API"""
    if order_id_close is None:
        order_id_close = 0

    data = {
        "order_id": position_id,
        "order_id_close": order_id_close,
        "instrument_id_bingx": instrument_id_bingx,
    }

    headers = {"Content-Type": "application/json"}
    response = requests.post(
        "http://127.0.0.1:5000/get_position", headers=headers, data=json.dumps(data)
    )

    salida = response.json()

    return salida[0], salida[1]

def get_indicator(tick_symbol, crypto_timeframe_di, crypto_timeframe_adx):
    """Gets indicators from Trading View"""

    cryptoDataraw = (
        '{"symbols":{"tickers":["'
        + tick_symbol
        + '"],"query":{"types":[]}},"columns":['
        + '"ADX'                 + str(crypto_timeframe_adx or "") + '",'
        + '"ADX+DI'              + str(crypto_timeframe_di  or "") + '",'
        + '"ADX-DI'              + str(crypto_timeframe_di  or "") + '",'
        + '"EMA10'               + str(crypto_timeframe_adx or "") + '",'
        + '"EMA20'               + str(crypto_timeframe_adx or "") + '",'
        + '"EMA100'              + str(crypto_timeframe_adx or "") + '",'
        + '"Recommend.MA'        + str(crypto_timeframe_adx or "") + '",'
        + '"Recommend.MA|240"'
        + "]}"
    )

    headers = {
        "authority": "scanner.tradingview.com",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36"
        ),
        "content-type": "application/x-www-form-urlencoded",
        "accept": "*/*",
        "origin": "https://www.tradingview.com",
        "sec-fetch-site": "same-site",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "referer": "https://www.tradingview.com/",
        "accept-language": "en,es;q=0.9",
        "cookie": (
            "_ga=GA1.2.526459883.1610099096; __gads=ID=8f36aef99159e559:"
            "T=1610100101:S=ALNI_Mars83GB1m6Wd227WWiChIcow2RpQ; "
            "sessionid=8pzntqn1e9y9p347mq5y54mo5yvb8zqq; "
            "tv_ecuid=41f8c020-6882-40d1-a729-c638b361d4b3; "
            "_sp_id.cf1a=18259830-0041-4e5d-bbec-2f481ebd9b76.1610099095.44."
            "1613162553.1612699115.1f98354c-1841-47fc-ab5d-d7113cfa5090; "
            "_sp_ses.cf1a=*; _gid=GA1.2.1715043600.1613162554; "
            "_gat_gtag_UA_24278967_1=1"
        ),
    }

    response = requests.post(
        "https://scanner.tradingview.com/crypto/scan",
        headers=headers,
        data=cryptoDataraw,
    )

    payload = response.json()

    total_count = payload["totalCount"]
    first_d = payload["data"][0]["d"]

    return total_count, first_d

# ── ORDERS ────────────────────────────────────────────────────────────────────────────────────────
def buy_order(
    instrument_type,
    instrument_id,
    instrument_id_bingx,
    side,
    amount,
    leverage,
    type,
    limit_price=None,
    stop_lose_kind=None,
    stop_lose_value=None,
    use_trail_stop=None,
):
    data = {
        "instrument_type": instrument_type,
        "instrument_id": instrument_id,
        "instrument_id_bingx": instrument_id_bingx,
        "side": side,
        "amount": amount,
        "leverage": leverage,
        "type": type,
        "limit_price": limit_price,
        "stop_lose_kind": stop_lose_kind,
        "stop_lose_value": stop_lose_value,
        "use_trail_stop": use_trail_stop,
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(
        "http://127.0.0.1:5000/buy_order", headers=headers, data=json.dumps(data)
    )
    return response.json()[0], response.json()[1]
