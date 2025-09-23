# -*- coding: utf-8 -*-

import json
import requests
import logging

logger = logging.getLogger("MT.models")

def get_position(position_id, order_id_close, instrument_id_bingx):
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

    try:
        salida = response.json()
    except Exception:
        logger.error( str(self.rateSymbol) + ": Error en get_position al leer el response.json()")
        return None, None

    return salida[0], salida[1]