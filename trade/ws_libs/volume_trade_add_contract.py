"""
合约刷量对应现货

"""
import datetime
import asyncio
import random
import loguru
import time
import traceback
from libs import libs_config, decorator, libs_price_async
from many_configs import global_variable, contract_currency_config, spot_currency_config
from many_configs.abc_config import contract_ask, contract_bid
from libs.config_update_ser import update_contract_trade_volume_percent
import config
from libs.heartbeat import i_live_transit_station
from libs.polaris import polaris_scale
from libs import recode_msg, currency_feature
from config import WS_FREQUENCY


async def get_contract_amount(symbol, source_amount, price):
    currency = symbol.split("-")[0]
    scale = polaris_scale(symbol)
    scale = scale if scale > 1 else 1
    amount = source_amount / scale
    market_value_percent = global_variable.G_CONTRACT_TRADE_CURRENCY_CONFIG[currency].get("market_value_percent", 1)
    amount = amount * market_value_percent

    if not global_variable.SYMBOLS_CONTRACT_CONDITION.get(symbol):
        print("get_contract_amount {} 价格精度错误没有配置------------------->>>>>>>>>".format(symbol, ))
        return 0
    min_quantity = float(global_variable.SYMBOLS_CONTRACT_CONDITION[symbol]["minQuantity"]) * float(global_variable.SYMBOLS_CONTRACT_CONDITION[symbol]["faceValue"])
    max_quantity = float(global_variable.SYMBOLS_CONTRACT_CONDITION[symbol]["maxQuantity"]) * float(global_variable.SYMBOLS_CONTRACT_CONDITION[symbol]["faceValue"])

    if symbol not in global_variable.SYMBOLS_SMALL_ORDER_TIMES["contract"]:
        global_variable.SYMBOLS_SMALL_ORDER_TIMES["contract"][symbol] = 0
    if amount < min_quantity and global_variable.SYMBOLS_SMALL_ORDER_TIMES["contract"][symbol] <= 10:
        global_variable.SYMBOLS_SMALL_ORDER_TIMES["contract"][symbol] += 1
        return None
    global_variable.SYMBOLS_SMALL_ORDER_TIMES["contract"][symbol] = 0

    # 保证最小下单量
    if amount < min_quantity:
        max_random = 3
        amount = max(amount, min_quantity / max_random) * max_random
    else:
        amount = amount

    amount = min(amount, max_quantity * random.uniform(0.7, 0.9))

    return amount


async def ask_bid_trade(price, symbol):
    return


async def risk_control(symbol):
    price = await libs_price_async.get_contract_weight_price(symbol)
    # 买卖一可能有极端情况存在价格N秒不变动
    defense_amount = 0
    # return price, defense_amount
    price_ask = global_variable.ABC_CONTRACT_ASK_BID_PRICE_CONTAINER.get(symbol, {}).get("ask")
    price_bid = global_variable.ABC_CONTRACT_ASK_BID_PRICE_CONTAINER.get(symbol, {}).get("bid")
    price_ts = global_variable.ABC_CONTRACT_ASK_BID_PRICE_CONTAINER.get(symbol, {}).get("ts", 0)

    try:
        spec_price_flag = True if price_ask and price_bid and (price_ask / price_bid - 1) > 0.0025 else False
    except Exception:
        loguru.logger.info(f"risk_control_spec_price_flag_error_contract -{symbol} {traceback.format_exc()}")
        spec_price_flag = False

    if price_ask and price_bid and time.time() - price_ts < 8:
        ask_bid_price = (price_ask + price_bid) / 2

        price_precision = int(global_variable.SYMBOLS_CONTRACT_CONDITION[symbol].get("price", 8))

        price_ask = round(price_ask, price_precision) if price_precision else round(price_ask)
        price_bid = round(price_bid, price_precision) if price_precision else round(price_bid)
        ask_bid_price = round(ask_bid_price, price_precision) if price_precision else round(ask_bid_price)

        percent = price / ask_bid_price - 1 if price > ask_bid_price else ask_bid_price / price - 1
        price = ask_bid_price
        min_order_amount = float(global_variable.SYMBOLS_CONTRACT_CONDITION.get(symbol, {}).get("minQuantity", 0)) * float(
            global_variable.SYMBOLS_CONTRACT_CONDITION[symbol]["faceValue"])
        if ask_bid_price in [price_ask, price_bid]:
            defense_amount = min_order_amount * random.uniform(0.004, 1.05)
        elif percent > 0.002:
            defense_amount = min_order_amount * random.uniform(0.004, 2.05)
    elif price_ts:
        await recode_msg.recode_error_msg(f"{symbol}-{price_ask}-{price_bid} 合约买卖一价格超时{time.time() - price_ts}s", 'volume')

    return price, defense_amount, spec_price_flag


async def contract_order(symbol, amount, price, self_flag=False, f="trade", heart_beat_time=WS_FREQUENCY, spec_price_flag=False):
    positions_amount_list = []
    close_order_status = []
    #
    # try:
    #     res = await contract_ask.contract_position(symbol=symbol)
    #     positions = res.get("result", [])
    # except BaseException as e:
    #     positions = []
    #     loguru.logger.info(f"contract_position fetch {traceback.format_exc()} {e}")
    # positions = []
    #
    # for position in positions:
    #     position_amount = int(position["avail_amount"]) * float(global_variable.SYMBOLS_CONTRACT_CONDITION[symbol]["faceValue"])
    #     positions_amount_list.append(position_amount)
    # if len(positions_amount_list) == 2 and min(positions_amount_list) >= amount:
    #     close_tasks = [asyncio.create_task(
    #         contract_ask.contract_add(symbol, "sell-limit", amount, price, contract_type="close")),
    #         asyncio.create_task(
    #             contract_bid.contract_add(symbol, "buy-limit", amount, price, contract_type="close"))
    #     ]
    #     for close_task in close_tasks:
    #         resp = await close_task
    #         if resp and resp.get("heartbeat"):
    #             i_live_transit_station("item_instance", f"{symbol}", frequency=heart_beat_time, heart_type=1)
    #             close_order_status.append(True)
    #         else:
    #             i_live_transit_station("item_instance", f"{symbol}", frequency=heart_beat_time, last_update=0, heart_type=1)
    #             close_order_status.append(False)
    # close_order_ok = True if close_order_status and all(close_order_status) else False
    # loguru.logger.info(f"add_contract_task-{symbol}, {price=}, {amount=}, {close_order_ok=}, {f}")
    loguru.logger.info(f"add_contract_task-{symbol}, {price=}, {amount=}, {f}")


    # tasks = [asyncio.create_task(
    #     contract_ask.contract_add(symbol, "sell-limit", amount, price, )),
    #     asyncio.create_task(
    #         contract_bid.contract_add(symbol, "buy-limit", amount, price, ))
    # ]
    tasks = [asyncio.create_task(
        contract_ask.contract_add_plus(symbol, amount, price, spec_price_flag)),
    ]

    f_symbol = f"{symbol}_fixed" if f == "fixed" else symbol
    heart_beat_time = WS_FREQUENCY * 2.1 if f == "fixed" else WS_FREQUENCY
    for task in tasks:
        resp = await task
        if not self_flag:
            if resp and resp.get("heartbeat"):
                i_live_transit_station("item_instance", f"{f_symbol}", frequency=heart_beat_time, heart_type=1)
            else:
                i_live_transit_station("item_instance", f"{f_symbol}", frequency=heart_beat_time, last_update=0, heart_type=1)
    i_live_transit_station("main_instance", frequency=60 * 30)


@decorator.monitor_handler
async def add_contract_trade_chief(zone_contract_symbols, currency_exchange):
    try:
        i_live_transit_station("main_instance", frequency=60)
        task = [asyncio.create_task(add_contract_trade(symbol, currency_exchange)) for symbol in
                zone_contract_symbols]

        await asyncio.wait(task)
    except:
        loguru.logger.info(f"add_contract_trade_chief {traceback.format_exc()}")


async def add_contract_trade(symbol, currency_exchange):
    i_live_transit_station("item_instance", f"{symbol}", frequency=WS_FREQUENCY, heart_type=1)
    # print("测试环境运行中" if libs_config.DEBUG else "线上环境运行中")
    currency, zone = symbol.split("-")
    exchange = currency_exchange.get(currency)
    add_last_update = time.time()
    rank = 0
    base_loop_time = contract_currency_config.special_base_sleep_time.get(symbol, contract_currency_config.base_sleep_time)
    sleep_ratio = contract_currency_config.sleep_ratio
    loop_time = contract_currency_config.SYMBOL_SLEEP_TIME.get(symbol, base_loop_time * sleep_ratio)
    substitute_time = contract_currency_config.SUBSTITUTE_TIME.get(symbol, 60)
    price_num = int(5 * 60 / loop_time)
    while True:
        try:
            if rank > 50000:
                rank = 0

            rank += base_loop_time
            await update_contract_trade_volume_percent()

            contract_c_symbol = f"c_{symbol}"

            contract_trades = global_variable.SHARE_VOLUME_MAKER_SYMBOLS
            if contract_trades[contract_c_symbol]:
                add_last_update = time.time()
                self_flag = False
            else:
                if time.time() - add_last_update > substitute_time:
                    symbol_amount = float(
                        global_variable.SYMBOLS_CONTRACT_CONDITION.get(symbol, {}).get("minQuantity", 1)) * \
                                    float(global_variable.SYMBOLS_CONTRACT_CONDITION[symbol]["faceValue"])
                    symbol_amount = symbol_amount * random.uniform(1, 8)
                    contract_trades[contract_c_symbol] = symbol_amount
                    add_last_update = time.time()
                    self_flag = True
                else:
                    self_flag = False

            new_loop_time = loop_time
            if global_variable.SYMBOLS_PRICE_5MIN.get(symbol):
                global_variable.SYMBOLS_PRICE_5MIN[symbol] = global_variable.SYMBOLS_PRICE_5MIN[symbol][-price_num:]
                symbol_price_list = global_variable.SYMBOLS_PRICE_5MIN[symbol]
                spread = max(symbol_price_list) / min(symbol_price_list)
                if spread >= 0.01:
                    new_loop_time = max(loop_time / base_loop_time // 2, 1) * base_loop_time

            if rank % new_loop_time != 0:
                await asyncio.sleep(base_loop_time)
                continue
            start_time = time.time()
            await add_contract_task(symbol, currency_exchange, self_flag)
            end_time = time.time()
            during_time = end_time - start_time
            # loguru.logger.info(f"{symbol} add_contract_{exchange} time, {during_time}")
            if during_time < base_loop_time:
                await asyncio.sleep(base_loop_time - during_time)
        except BaseException as e:
            await asyncio.sleep(2)
            loguru.logger.info(f"add_contract_trade - {traceback.format_exc()}")


async def add_contract_task(symbol, currency_exchange, self_flag):
    currency = symbol.split("-")[0]
    exchange = currency_exchange.get(currency)
    try:
        contract_c_symbol = f"c_{symbol}"

        contract_trades = global_variable.SHARE_VOLUME_MAKER_SYMBOLS
        if not contract_trades[contract_c_symbol]:
            return
        trade = contract_trades[contract_c_symbol]
        contract_trades[f"{contract_c_symbol}_update"] = time.time()

        # trade = trade_data.pop(0)
        # with global_variable.SHARE_VOLUME_MAKER_SYMBOLS.lock(timeout=0.001, block=True, sleep_time=0.000001):
        #     contract_trades[contract_c_symbol] = trade_data[-5:]
    except BaseException as e:
        loguru.logger.info(f"add_contract_{exchange}_task error {repr(e)}")
        return

    price, defense_amount, spec_price_flag = await risk_control(symbol)
    if defense_amount:
        amount = defense_amount
    else:
        amount = (float(trade) / contract_currency_config.amount_rate) * 5
        amount = await get_contract_amount(symbol, amount, price)
        if amount is not None:
            contract_trades[contract_c_symbol] = 0
        else:
            # 合并下小单
            return
    await contract_order(symbol, amount, price, self_flag, spec_price_flag=spec_price_flag)

    if not global_variable.SYMBOLS_PRICE_5MIN.get(symbol, []):
        global_variable.SYMBOLS_PRICE_5MIN[symbol] = []
    global_variable.SYMBOLS_PRICE_5MIN[symbol].append(price)

    await ask_bid_trade(price, symbol)


async def add_contract_self_task(symbol, heart_beat_time, f="self"):
    # price = await libs_price_async.get_contract_weight_price(symbol)
    # amount = float(trades_dict_self[symbol]["amount"])
    # # amount = await get_contract_amount(symbol, amount, price)

    price, defense_amount, spec_price_flag = await risk_control(symbol)
    symbol_amount = float(global_variable.SYMBOLS_CONTRACT_CONDITION.get(symbol, {}).get("minQuantity", 1)) * float(global_variable.SYMBOLS_CONTRACT_CONDITION[symbol]["faceValue"])
    symbol_amount = symbol_amount * random.uniform(1, 6)
    if defense_amount:
        amount = defense_amount
    else:
        amount = symbol_amount

    await contract_order(symbol, amount, price, f=f, heart_beat_time=heart_beat_time, spec_price_flag=spec_price_flag)


@decorator.monitor_handler
async def add_contract_self_chief(self_symbols):
    # 由计划自刷量修改为对标现货刷量
    try:
        i_live_transit_station("main_instance", frequency=60)
        [i_live_transit_station("item_instance", f"{symbol}", frequency=WS_FREQUENCY, heart_type=1) for symbol in
         self_symbols]

        tasks = []
        for symbol in self_symbols:
            tasks.append(asyncio.create_task(add_contract_self(symbol)))
            currency, quote = symbol.split("-")
            level = currency_feature.currency_dangerous_level(currency)
            if level <= 2 and quote == "USDT":
                i_live_transit_station("item_instance", f"{symbol}_fixed", frequency=60, heart_type=1)
                tasks.append(asyncio.create_task(add_contract_fixed_self(symbol)))

        await asyncio.wait(tasks)
    except Exception as e:
        loguru.logger.info(f"add_trade_self_chief {e} {traceback.format_exc()}")


async def add_contract_fixed_self(symbol):
    flag_start, flag_end = True, True
    start_fixed, end_fixed = 1, 59
    interval = 1
    while True:
        try:
            now_time = datetime.datetime.now()
            if now_time.minute % interval in [0, interval-1]:
                if now_time.minute % interval == interval-1 and now_time.second >= end_fixed and flag_end:
                    await add_contract_self_task(symbol, interval * 60 + 10, f="fixed")
                    flag_end = False
                elif now_time.minute % interval == 0 and now_time.second <= start_fixed and flag_start:
                    await add_contract_self_task(symbol, interval * 60 + 10, f="fixed")
                    flag_start = False
                else:
                    if now_time.second < end_fixed:
                        flag_end = True
                    elif now_time.second > start_fixed:
                        flag_start = True
                    await asyncio.sleep(0.3)
            else:
                await asyncio.sleep(30)
        except Exception as e:
            print(datetime.datetime.now().strftime('%H:%M:%S.%f'), traceback.format_exc())
            await asyncio.sleep(2)


async def add_contract_self(symbol):
    # 由计划自刷量修改为对标现货刷量
    # print("测试环境运行中" if libs_config.DEBUG else "线上环境运行中")
    rank = 0
    base_loop_time = contract_currency_config.self_base_sleep_time
    loop_time = contract_currency_config.SELF_SYMBOL_SLEEP_TIME.get(symbol, base_loop_time)
    heart_beat_time = loop_time + base_loop_time * 2

    i_live_transit_station("item_instance", f"{symbol}", frequency=heart_beat_time, heart_type=1)

    while True:
        try:
            if rank > 50000:
                rank = 0

            rank += base_loop_time

            if rank % loop_time != 0:
                await asyncio.sleep(base_loop_time)
                continue

            start_time = time.time()
            await add_contract_self_task(symbol, heart_beat_time)
            during_time = time.time() - start_time
            # loguru.logger.info(f"add_trade_self time, {during_time}")
            if during_time < base_loop_time:
                await asyncio.sleep(base_loop_time - during_time)
        except Exception as e:
            loguru.logger.info(f"add_contract_self {traceback.format_exc()}")
            await asyncio.sleep(2)


# 撤单服务
async def getorderid(symbol, ao):
    orderids = []
    result = await ao.contract_current_all(symbol, 1000)
    for i in result:
        if i['status'] != 4:
            orderid = i['order_id']
            ctime = i['entrust_time']
            current_time = int(time.time())
            if ctime < current_time - 2:
                orderids.append(orderid)
    return orderids


async def cancel_order_task(symbol, ao):
    while True:
        try:
            res = await ao.contract_cancel(symbol=symbol)
            # cancel_orders = await getorderid(symbol, ao)
            # order_list = []
            # for i in cancel_orders:
            #     order_list.append(str(i))
            # cancel_orders = order_list
            # # loguru.logger.info(f"cancel_orders, {symbol}, {len(order_list)}")
            # if order_list:
            #     await ao.contract_cancel(cancel_orders)
            i_live_transit_station("main_instance", frequency=5)
            if res.get("errno") != -1:
                i_live_transit_station("item_instance", f"{symbol}", frequency=5, heart_type=2)

        except Exception as e:
            loguru.logger.info(f"cancel_order_task-contract {traceback.format_exc()}")
        finally:
            await asyncio.sleep(2)


@decorator.monitor_handler
async def cancel_contract_order(symbols):
    try:
        i_live_transit_station("main_instance", frequency=5)
        [i_live_transit_station("item_instance", f"{symbol}", frequency=5, heart_type=2) for symbol in symbols]

        tasks = []
        for ao in [contract_ask, ]:
            for symbol in symbols:
                tasks.append(asyncio.create_task(
                    cancel_order_task(symbol, ao)))

        await asyncio.wait(tasks)
    except Exception as e:
        loguru.logger.info(f"{traceback.format_exc()}")
        await asyncio.sleep(1)


@decorator.monitor_handler
async def async_contract_price_restful():
    i_live_transit_station("main_instance", frequency=6)
    while True:
        print("async_contract_price_restful", global_variable.monitor.get())

        try:
            res = await contract_ask.async_contract_index()
            for r in res["result"]:
                symbol = r["symbol"]
                weight_price = r["markPrice"]
                ts = float(r.get("ts", 0))

                update_symbol = symbol.replace("/", "-")
                if update_symbol not in contract_currency_config.CONTRACT_SUPPORT_SYMBOLS:
                    continue
                if float(weight_price) > 0 and time.time() - ts / 1000 < 3:
                    loguru.logger.info(f"async_contract_price_restful, {update_symbol}, {weight_price}")
                    # await libs_price_async.update_contract_price({update_symbol : weight_price})
                    i_live_transit_station("main_instance", frequency=15)
        except (Exception,BaseException) as e:
            error_msg = f"async_contract_price_restful {repr(e)}"
            loguru.logger.info(f"{error_msg} {traceback.format_exc()}")
            await recode_msg.recode_error_msg(error_msg, "abc_contract_price")
        await asyncio.sleep(10)

def sleep_time(t):
    if 0 <= datetime.datetime.now().hour <= 7:
        t = t * 1.5
    return t


if __name__ == "__main__":
    res = contract_ask.contract_index()
    # print(res)
