""""
根据用户持仓调整策略
"""
# -- 不能注释，此导入为初始化
import initialization
# ---
import urllib3
from pprint import pprint
from datetime import datetime, timedelta
from config import GET_OFFSET_FREQUENCY, MAX_OFFSET, MAX_LONG_SHORT_DIFF
from many_configs.abc_config import all_contract_accounts
from many_configs.contract_currency_config import contract_close_time
from many_configs import global_variable
from libs import libs_price, libs_config, decorator
from libs.heartbeat import i_live_transit_station, heart_monitor
from libs.senddd import send_telegram
from libs import libs_config
import threading
from traceback import format_exc
import time
from urllib3.exceptions import InsecureRequestWarning

urllib3.disable_warnings(InsecureRequestWarning)


def get_close_dt():
    close_dt = []
    for t in contract_close_time:
        dt = datetime.strptime(t, '%H:%M:%S')
        close_dt.append(dt)
    return close_dt


def compare_dt(nowdt, closedt):
    for dt in closedt:
        if timedelta(minutes=0) < dt - nowdt < timedelta(minutes=3):
            print(datetime.now(), dt, nowdt, dt - nowdt, )
            return True
    return False


"""
1、多仓 > 空仓
为了提高开多仓的成本，应提高卖一（ask）价
2、空仓 > 多仓
为了提高开空仓的成本，应降低买一（bid）价
"""


def get_ask1_bid1_offset(spread):
    if abs(spread) >= MAX_OFFSET:
        if spread > 0:  # 多仓 > 空仓 > 最大阈值
            ask1 = MAX_OFFSET
            bid1 = ask1 / 2
        else:
            bid1 = MAX_OFFSET * (-1)
            ask1 = bid1 / 2
    else:
        if spread > 0:
            ask1 = spread
            bid1 = ask1 / 2
        else:
            bid1 = spread
            ask1 = bid1 / 2
    return ask1, bid1


def get_price_offset(spread):
    if abs(spread) < libs_config.CONTRACT_MIN_OFFSET_PERCENT:
        spread = 0
    elif abs(spread) > libs_config.CONTRACT_MAX_OFFSET_PERCENT:
        spread = libs_config.CONTRACT_MAX_OFFSET_PERCENT * -1 if spread < 0 else libs_config.CONTRACT_MAX_OFFSET_PERCENT
    return spread


def get_spread_amount():
    info = {}
    for acc in all_contract_accounts:
        res = acc.contract_position()["result"]
        print(res)
        if not res:
            continue
        for i in res:
            contract_type = i.get("type", 0)
            symbol = i["symbol"]
            amount = int(i["amount"])
            if contract_type == 1:
                if symbol in info:
                    info[symbol]["amount_long"] += amount
                else:
                    info[symbol] = {
                        "amount_long": amount,
                        "amount_short": 0
                    }
            elif contract_type == 2:
                if symbol in info:
                    info[symbol]["amount_short"] += amount
                else:
                    info[symbol] = {
                        "amount_short": amount,
                        "amount_long": 0
                    }
    # nowtime = datetime.strptime(time.strftime("%H:%M:%S"), "%H:%M:%S")
    # print(info)
    send_data = []
    for symbol, amount in info.items():
        spread = (amount["amount_short"] - amount["amount_long"]) / (MAX_LONG_SHORT_DIFF / MAX_OFFSET)
        ask_offset, bid_offset = get_ask1_bid1_offset(spread)
        print(datetime.now(), symbol, "ask: ", ask_offset, "bid: ", bid_offset)
        # contract_spread = get_price_offset(spread)
        # print(symbol, contract_spread)
        # libs_price.update_contract_offset(symbol, contract_spread)
        send_data.append({"symbol": symbol, "ask_offset": ask_offset, "bid_offset": bid_offset})
    libs_price.update_contract_askbid_offset(send_data)


@decorator.monitor_handler
def main():
    i_live_transit_station("main_instance", frequency=GET_OFFSET_FREQUENCY + 5)
    close_dt = get_close_dt()
    while True:
        try:
            get_spread_amount()
            i_live_transit_station("main_instance", frequency=GET_OFFSET_FREQUENCY + 5)
        except BaseException as e:
            error_msg = "offset" + format_exc()
            print(datetime.now(), error_msg)
            send_telegram(f"{e}\n{error_msg}", "contract_offset", libs_config.DEBUG)
            # send_telegram(f"{e}\n{error_msg}", "contract_offset", False)

        time.sleep(GET_OFFSET_FREQUENCY)


if __name__ == '__main__':
    t = threading.Thread(target=heart_monitor, args=())
    t.start()
    main(monitor="合约价格偏移量_根据持仓|")
    t.join()

