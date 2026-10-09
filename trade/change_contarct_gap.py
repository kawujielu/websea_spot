from libs import libs_price
from many_configs.contract_currency_config import CONTRACT_SUPPORT_SYMBOLS

SMALLER_GAP = {
    "BTC-USDT": 0.00001,
    "ETH-USDT": 0.000025,
}

BIGGER_GAP = {
    "BTC-USDT": 0.006,
    "ETH-USDT": 0.008,
}


def set_to_bigger():
    for s in CONTRACT_SUPPORT_SYMBOLS:
        v = BIGGER_GAP.get(s, 0.015)
        res = libs_price.redis_db_control.hset("contract_price_percent", s, v)
        print(f"{s} set to {v} , {res=}")


def set_to_smaller():
    for s in CONTRACT_SUPPORT_SYMBOLS:
        v = SMALLER_GAP.get(s, 0.002)
        res = libs_price.redis_db_control.hset("contract_price_percent", s, v)
        print(f"{s} set to {v} , {res=}")


if __name__ == "__main__":
    set_to_bigger()
