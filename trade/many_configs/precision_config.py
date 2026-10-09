import ujson
import requests
from many_configs.abc_config import host, contract_host
from many_configs.contract_currency_config import contract_symbols
from libs import libs_price
import traceback


# 价格精度
def spot_price_precision():
    condition_url = host + "/openApi/market/precision/"

    try:
        res = requests.get(condition_url, timeout=5, verify=False)
        if res.status_code == 200:
            symbols_condition = ujson.loads(res.text)["result"]
            return symbols_condition
        else:
            print("获取失败，spot precision 将使用默认值", res)
    except BaseException as e:
        print("现货精度获取失败! spot precision 将使用默认值: precision error", e, traceback.format_exc())
    try:
        symbols_condition = libs_price.get_precision_config(name='redis_precision')
    except BaseException as e:
        print("现货精度从redis获取失败！precision error", e, traceback.format_exc())
        symbols_condition = {}

    return symbols_condition


def contract_price_precision():
    condition_url = contract_host + "/qapi-v1/symbol/precision"

    try:
        res = requests.get(condition_url, timeout=2, verify=False)
        if res.status_code == 200:
            symbols_contract_condition = ujson.loads(res.text)["result"]
            return symbols_contract_condition
        else:
            print("获取失败，contract precision 将使用默认值", res)
    except BaseException as e:
        print("合约精度获取失败! contract precision 将使用默认值: precision error", e, traceback.format_exc())
    try:
        default_contract_precision = libs_price.get_precision_config(name='contract_redis_precision')
        symbols_contract_condition = default_contract_precision
    except BaseException as e:
        print("合约精度从redis获取失败！precision error", e, traceback.format_exc())
        symbols_contract_condition = {}

    return symbols_contract_condition


# 获取交易所支持的合约交易对
def contract_support_symbols():
    contract_symbols_url = contract_host + "/openApi/contract/symbols"
    default_contract_symbols = contract_symbols
    try:
        res = requests.get(contract_symbols_url, timeout=2, verify=False)
        if res.status_code == 200:
            res = ujson.loads(res.text).get("result", default_contract_symbols)
            r = [r["symbol"] for r in res]
        else:
            print(res)
            print("获取失败，合约支持的交易对将使用默认值", res)
            r = default_contract_symbols
    except BaseException as e:
        print("获取失败，合约支持的交易对将使用默认值", e)
        r = default_contract_symbols

    return r
