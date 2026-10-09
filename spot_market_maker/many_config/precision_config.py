import ujson
import requests
from libs import libs_price
import traceback


# 获取交易对价格精度
def get_spot_precision(host):
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
