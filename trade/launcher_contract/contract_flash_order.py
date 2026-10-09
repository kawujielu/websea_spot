
# -- 不能注释，此导入为初始化
import initialization
# ---
import asyncio
import datetime
import random
import time
import traceback
import setproctitle
import async_timeout
import urllib3
import config
from many_configs import global_variable
from traceback import format_exc
from multiprocessing import Process
from threading import Thread
from many_configs.abc_config import (contract_volume_flash1, contract_volume_flash2)
from libs import (heartbeat,
                  senddd,
                  libs_config)
from libs.heartbeat import i_live_transit_station
from ws_libs.ws_abc_contract_depth import async_abc_contract_ask_bid_price_ws
from urllib3.exceptions import InsecureRequestWarning

urllib3.disable_warnings(InsecureRequestWarning)
abc_accounts = [contract_volume_flash1, contract_volume_flash2]
CUR_MAIN_SERVER = "闪单服务"

def myprint(*args, **kwargs):
    print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), *args, **kwargs)


FLASH_SYMBOLS = {
    # "设定值"= 近盘口大致张数 * 价格* 面值 | 近盘口大致多少U
    "BTC-USDT": {"normal": 3000, "quality": 8000},
    "ETH-USDT": {"normal": 3000, "quality": 8000},
    "DOGE-USDT": {"normal": 3000, "quality": 8000},
    "LINK-USDT": {"normal": 500, "quality": 2000},
    "XRP-USDT": {"normal": 400, "quality": 1600},
    "UNISWAP-USDT": {"normal": 200, "quality": 800},
    "LTC-USDT": {"normal": 800, "quality": 3200},
    "EOS-USDT": {"normal": 500, "quality": 2000},
    "BSV-USDT": {"normal": 1000, "quality": 4000},
    "ADA-USDT": {"normal": 150, "quality": 600},
    "TRX-USDT": {"normal": 250, "quality": 1000},
    "ETC-USDT": {"normal": 300, "quality": 1200},
    "ALGO-USDT": {"normal": 1000, "quality": 4000},
    "ATOM-USDT": {"normal": 150, "quality": 600},
    "DOT-USDT": {"normal": 100, "quality": 400},
    "ONT-USDT": {"normal": 200, "quality": 800},
    "YFI-USDT": {"normal": 50, "quality": 200},
    "YFII-USDT": {"normal": 200, "quality": 800},
    "SUSHI-USDT": {"normal": 100, "quality": 400},
    "COMP-USDT": {"normal": 100, "quality": 400},
    "AVAX-USDT": {"normal": 127, "quality": 508},
    "FIL-USDT": {"normal": 160, "quality": 640},
    "NEAR-USDT": {"normal": 264, "quality": 1056},
    "STORJ-USDT": {"normal": 141, "quality": 564},
    "ZEC-USDT": {"normal": 750, "quality": 3000},
    "BCH-USDT": {"normal": 1500, "quality": 6000},
    "ZIL-USDT": {"normal": 330, "quality": 1320},
    "GRT-USDT": {"normal": 250, "quality": 1050},
    "AXS-USDT": {"normal": 468, "quality": 1872},
    "SOL-USDT": {"normal": 800, "quality": 1200},
    "MATIC-USDT": {"normal": 1100, "quality": 4400},
    "ICP-USDT": {"normal": 450, "quality": 1250},
    "LUNA-USDT": {"normal": 1320, "quality": 5280},
    "AAVE-USDT": {"normal": 408.6, "quality": 1634.47},
    "THETA-USDT": {"normal": 1318, "quality": 5273},
    "YGG-USDT": {"normal": 200, "quality": 400},

    "AGLD-USDT": {"normal": 200, "quality": 300, "lazy": True},
    "FTM-USDT": {"normal": 1318, "quality": 2500, "lazy": True},
    'SHIB-USDT': {"normal": 3400, "quality": 7871, "lazy": True},
    "DYDX-USDT": {"normal": 349, "quality": 700, "lazy": True},

    "MDX-USDT": {"normal": 349, "quality": 571, "lazy": True},
    "MASK-USDT": {"normal": 350, "quality": 530, "lazy": True},
    "CSPR-USDT": {"normal": 600, "quality": 1000, "lazy": True},
    "AR-USDT": {"normal": 798, "quality": 1129, "lazy": True},
    "SRM-USDT": {"normal": 798, "quality": 1540, "lazy": True},

    "QTUM-USDT": {"normal": 900, "quality": 1500, "lazy": True},
    "DASH-USDT": {"normal": 798, "quality": 1129, "lazy": True},
    "1INCH-USDT": {"normal": 800, "quality": 1240, "lazy": True},
}


async def inner(order_tuple: tuple, ao):
    start_time = time.time()
    # ao.contract_add(symbol, "sell-limit", amount, cur_ask, )),
    res = await ao.contract_add(*order_tuple)
    end_time = time.time()
    spend_time = end_time - start_time
    if ao == contract_volume_flash1:  # 量化账号
        # destination_spend_time = 0.05
        destination_spend_time = 0.2 * random.uniform(0.5, 1.5)
        # destination_spend_time = 0
    else:
        destination_spend_time = 0.4 * random.uniform(0.5, 1.5)

    if spend_time < destination_spend_time:
        sleep_time = destination_spend_time - spend_time
    else:
        sleep_time = 0
    await asyncio.sleep(sleep_time)
    if not res:
        myprint('order-error', res)

    if res.get('errno') == 0:
        order_id = res['result']
        res = await ao.contract_cancel(order_id)
        if res.get("result"):
            if order_id in res['result']["failList"]:
                cancel_res = res
            else:
                cancel_res = 'success'
        else:
            cancel_res = 'cancel errno != 0 failed'

        if ao == contract_volume_flash2:  # 普通 账户
            key_acccount = 'normal_account'
        else:
            key_acccount = 'quanlity_account'

        myprint(key_acccount, order_tuple, order_id, "cancel_res", cancel_res)


async def create_cancel_order(order_tuple: tuple, ao):
    """
    每个闪单，相隔0.5 秒后给撤销掉
    {'errno': 0, 'errmsg': 'success', 'result': {'order_sn': 'SL995231616986127580OH6PP3'}}
    :param order_tuple:
    :param ao:
    :return:
    """
    try:
        async with async_timeout.timeout(6) as cm:
            await inner(order_tuple, ao)
    except BaseException as e:
        myprint(order_tuple, "任务超时", repr(e))


async def handel_older_orders_loop(symbol, ao):
    while True:
        try:
            time_start = time.time()
            fetch_current_list = await ao.contract_current_all(symbol, 1000)
            myprint(symbol, '当前委托耗时', datetime.datetime.now(), time.time() - time_start, "s")
            fetch_current_list = [x['order_id'] for x in fetch_current_list if time.time() - x['entrust_time'] > 10]
            i = 0
            while True:
                start, end = (i) * 200, (i + 1) * 200
                cut_list = fetch_current_list[start:end]
                if not cut_list:
                    break
                else:
                    try:
                        currentids = cut_list
                        t1 = time.time()
                        res = await ao.contract_cancel(currentids)
                        myprint(symbol, '撤销耗时', datetime.datetime.now(), time.time() - t1, "s")
                        if res.get('errno') == 0:
                            if res['result']['successList']:
                                myprint(datetime.datetime.now(), symbol, "撤销成功", res['result']['success'])
                            if res['result']['failList']:
                                myprint(datetime.datetime.now(), symbol, "撤销失败", res['result']['failed'])
                        else:
                            myprint(datetime.datetime.now(), symbol, "接口返回撤销失败", res)
                    except (Exception, BaseException) as e:
                        myprint(symbol, '-----撤销接口问题----')
                        pass
                i += 1
            time_dur = time.time() - time_start
            myprint(symbol, '全局耗时', datetime.datetime.now(), "撤单总共计时", time_dur,"当前委托超过10秒未成交笔数",len(fetch_current_list),)
        except BaseException as e:
            myprint('撤销当前委托错误', e, traceback.format_exc())
        finally:
            await asyncio.sleep(10)


async def distribute(symbol, ao):
    """
    每个交易对每隔0.05秒下一次闪单
    :param symbol:
    :param ao:
    :return:
    """
    asyncio.ensure_future(handel_older_orders_loop(symbol, ao))
    # d_msg=[]
    # def myprint(*args, **kwargs):
    #     my_msg=(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), args, kwargs)
    #     d_msg.append(my_msg)
    while True:
        start_time = time.time()
        price_ask = global_variable.ABC_CONTRACT_ASK_BID_PRICE_CONTAINER.get(symbol, {}).get("ask")
        price_bid = global_variable.ABC_CONTRACT_ASK_BID_PRICE_CONTAINER.get(symbol, {}).get("bid")
        if not price_ask or not price_bid:
            await asyncio.sleep(0.1)
            continue
        price_ts = global_variable.ABC_CONTRACT_ASK_BID_PRICE_CONTAINER.get(symbol, {}).get("ts", 0)

        price_precisons = float(global_variable.SYMBOLS_CONTRACT_CONDITION.get(symbol, {}).get("price", 0))

        # if price_ask and price_bid and time.time() - price_ts < 20:
        #     pass
        # else:
        #     price = await libs_price_async.get_contract_weight_price(symbol)
        #     price_ask = price * (1 + 0.00005)
        #     price_bid = price * (1 - 0.00005)
        # p = await libs_price_async.get_contract_weight_price(symbol)

        # cur_ask=p+2.5
        # cur_bid=p-2.5
        one_precisons_price = 0.1 ** price_precisons
        if symbol in ["SLP-USDT"]:
            account_1_deviation = 2
            account_2_deviation = 3
        elif symbol == "BTC-USDT":
            account_1_deviation = 6
            account_2_deviation = 10
        elif symbol == "ETH-USDT":
            account_1_deviation = 25
            account_2_deviation = 35
        else:
            account_1_deviation = 6
            account_2_deviation = 10
        account_1_cur_ask = price_ask + one_precisons_price * account_1_deviation
        account_1_cur_bid = price_bid - one_precisons_price * account_1_deviation

        account_2_cur_ask = price_ask + one_precisons_price * account_2_deviation
        account_2_cur_bid = price_bid - one_precisons_price * account_2_deviation
        # myprint('量化账号', "卖一", account_1_cur_ask, "买一", account_1_cur_bid, "price_ask", price_ask, "price_bid",
        #         price_bid)
        # myprint('普通账号', "卖一", account_2_cur_ask, "买一", account_2_cur_bid, "price_ask", price_ask, "price_bid",
        #         price_bid)

        tasks = []
        order_num = 2

        indexes = list(range(order_num))

        random.shuffle(indexes)
        price = (price_ask + price_bid) / 2
        for i in indexes:
            if ao == contract_volume_flash1:  # 量化账号
                weight = 2
                try:
                    amount = FLASH_SYMBOLS[symbol]["quality"]
                except:
                    amount = 8000
                    myprint(f"{symbol}没获取到数量配置使用默认值：{amount}")
                amount = random.uniform(amount, amount * 2 / 3)

                cur_ask = account_1_cur_ask + weight * (i * one_precisons_price * 3)
                cur_bid = account_1_cur_bid - weight * (i * one_precisons_price * 3)

            else:  # 普通账号
                weight = 2
                try:
                    amount = FLASH_SYMBOLS[symbol]["normal"]
                except:
                    amount = 3000
                    myprint(f"{symbol}没获取到数量配置使用默认值：{amount}")
                amount = random.uniform(amount, amount * 5 / 3)
                # amount=amount/cur_ask

                cur_ask = account_2_cur_ask + weight * (i * one_precisons_price * 2)
                cur_bid = account_2_cur_bid - weight * (i * one_precisons_price * 2)

            # amount = amount / price / float(global_variable.SYMBOLS_CONTRACT_CONDITION[symbol]["faceValue"])

            task = asyncio.ensure_future(create_cancel_order((symbol, "sell-limit", amount / price, cur_ask,), ao))
            tasks.append(task)
            task = asyncio.ensure_future(create_cancel_order((symbol, "buy-limit", amount / price, cur_bid,), ao))
            tasks.append(task)
            week_time = 0.1
            if FLASH_SYMBOLS[symbol].get('lazy'):
                week_time *= 2
            await asyncio.sleep(random.uniform(week_time, week_time*2))
        dones, pendings = await asyncio.wait(tasks)
        myprint("all tasks count:", len(asyncio.Task.all_tasks()), 'active tasks count:',
                len([task for task in asyncio.Task.all_tasks() if not task.done()]))
        end_time = time.time()
        spend_time = end_time - start_time
        destination_spend_time = 0.4 if ao == contract_volume_flash1 else 0.8
        if FLASH_SYMBOLS[symbol].get('lazy'):
            destination_spend_time *= 2
        if spend_time < destination_spend_time:
            sleep_time = destination_spend_time - spend_time
        else:
            sleep_time = 0
        await asyncio.sleep(sleep_time)


def create_add_cancel_tasks(symbols):
    """
    按照交易对不同，创建不同的闪单策略
    :param symbols:
    :return:
    """
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    loop = asyncio.get_event_loop()
    tasks = []
    for ao in abc_accounts:
        for symbol in symbols:
            tasks.append(asyncio.ensure_future(
                distribute(symbol, ao)))
    loop.run_until_complete(asyncio.wait(tasks))


def order_moniter(task_symbols):
    i_live_transit_station("main_instance", frequency=15)
    [i_live_transit_station("item_instance", f"{ts}", frequency=15) for ts in task_symbols]
    while True:
        try:
            symbols = []
            msg = '【交易对未下单检测】\n'
            now_time = time.time()
            if global_variable.LAST_ORDER_TIME_MAPPING.get("symbols"):
                server_name = f"合约闪单下单检测服务"
                for symbol, last_send_time in global_variable.LAST_ORDER_TIME_MAPPING["symbols"].items():
                    if symbol not in task_symbols:
                        continue
                    wait_time = 10
                    if now_time - last_send_time > wait_time:
                        symbols.append(symbol)
                        msg += f"交易对{symbol}上次交易时间{last_send_time},距离当前时间大于{wait_time}秒未下单\n"
                        print(f"合约闪单交易对未下单检测服务: {msg}")
                    else:
                        i_live_transit_station("item_instance", f"{symbol}", frequency=15)
                        i_live_transit_station("main_instance", frequency=15)

                # myprint(f"交易对未下单检测,mark_flag:{mark_flag},LAST_ORDER_TIME_MAPPING:{global_variable.LAST_ORDER_TIME_MAPPING}")
        except:
            myprint(f"合约闪单交易对未下单检测服务 服务出错, {format_exc()}")
            senddd.send_telegram("合约闪单交易对未下单检测服务 服务出错", "monitor", debug=libs_config.DEBUG)
        finally:
            time.sleep(10)


def thread_main(symbols):
    trade_thread_list = []
    trade_thread_list.append(Thread(target=asyncio.run, args=(async_abc_contract_ask_bid_price_ws(symbols, monitor=f"{CUR_MAIN_SERVER}_ws订阅abc买卖一|合约"),),))
    trade_thread_list.append(Thread(target=create_add_cancel_tasks, args=(symbols,)))
    trade_thread_list.append(Thread(target=order_moniter, args=(symbols,), kwargs={"monitor": f"{CUR_MAIN_SERVER}_下单检测服务|合约"}))
    trade_thread_list.append(Thread(target=heartbeat.heart_monitor, args=()))

    for t in trade_thread_list:
        t.start()
    for t in trade_thread_list:
        t.join()


if __name__ == '__main__':

    symbols = sorted(FLASH_SYMBOLS)
    spread = 8
    i = 0
    tasks = []
    while True:
        start, end = i * spread, (i + 1) * spread
        task_symbols = symbols[start:end]
        if end > len(symbols):
            end = len(symbols)
        if not task_symbols:
            break
        p1 = Process(target=thread_main, args=(task_symbols,))
        setproctitle.setproctitle(f"python3.6 contract_flash_order symbols【{start}:{end}】")
        p1.start()
        tasks.append(p1)
        i += 1
    setproctitle.setproctitle(f"python3.6 contract_flash_order symbols main")
    for p in tasks:
        p.join()
