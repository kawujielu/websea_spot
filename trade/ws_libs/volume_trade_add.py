import asyncio
import datetime
import random
import time
import traceback
from many_configs import global_variable, spot_currency_config
from libs import libs_config, decorator, libs_price_async, currency_feature
from libs.config_update_ser import update_trade_volume_percent, update_symbol_precision, update_swap_vol, \
    update_vol_coefficient, update_price_percent
from libs.heartbeat import i_live_transit_station
from libs.polaris import polaris_scale
from loguru import logger
from libs import recode_msg
from config import WS_FREQUENCY


async def get_amount(symbol, amount, price):
    currency = symbol.split("-")[0]
    market_value_percent = global_variable.G_TRADE_CURRENCY_CONFIG[currency].get("market_value_percent", 1)
    logger.info(f"get_amount, {symbol}, {amount}, {price}, {market_value_percent}")
    if spot_currency_config.OPEN_TIME.get(symbol, 0):
        start_time = datetime.datetime.strptime(spot_currency_config.OPEN_TIME[symbol], "%Y-%m-%d %H:%M:%S")
        time_now = datetime.datetime.now()
        diff_time = time_now - start_time
        day = diff_time.days
        seconds = diff_time.seconds
        if day == 0:
            if 0 < seconds < 30 * 60:
                amount = amount * spot_currency_config.amount_rate * 5 * market_value_percent
                print(f"进入0-30min 刷量 数量:{amount}")
            elif 30 * 60 < seconds < 90 * 60:
                amount = amount * spot_currency_config.amount_rate * 3 * market_value_percent
                print(f"进入30-90min 刷量 数量:{amount}")
            elif 90 * 60 < seconds < 120 * 60:
                amount = amount * spot_currency_config.amount_rate * 1.2 * market_value_percent
                print(f"进入90-120min 刷量 数量:{amount}")
            else:
                amount = amount * spot_currency_config.amount_rate * 1 / 3 * market_value_percent
                print(f"进人120min之后刷量 数量:{amount}")
            return amount

    scale = polaris_scale(symbol)
    scale = scale if scale > 1 else 1
    amount = amount / scale

    print("get_amount", symbol, amount, price, market_value_percent)
    amount = amount * market_value_percent

    refer = symbol.split("-")[0]
    base = symbol.split("-")[1]

    if not global_variable.SYMBOLS_ORDER_CONDITION.get(symbol):
        msg = f"error {symbol} 价格精度错误没有配置------------------->>>>>>>>>"
        logger.info(msg)
        await recode_msg.recode_error_msg(msg, "send_telegram_important_msg_url")
        return 0
    min_quantity = float(global_variable.SYMBOLS_ORDER_CONDITION.get(symbol, {}).get("minQuantity", 0))

    # 不同区进行倍数调节
    amount_avg = spot_currency_config.TRADE_AREA_AVG_MAPPINGS[base]
    amount = amount * amount_avg
    if symbol not in global_variable.SYMBOLS_SMALL_ORDER_TIMES:
        global_variable.SYMBOLS_SMALL_ORDER_TIMES[symbol] = 0
    if amount < min_quantity and global_variable.SYMBOLS_SMALL_ORDER_TIMES[symbol] <= 5:
        global_variable.SYMBOLS_SMALL_ORDER_TIMES[symbol] += 1
        return None
    global_variable.SYMBOLS_SMALL_ORDER_TIMES[symbol] = 0
    if amount < min_quantity:
        max_random = 3
        amount = max(amount, min_quantity / max_random) * max_random
    else:
        amount = amount
    # amount = max(amount, random.uniform(min_quantity * 1, min_quantity * 4))
    return amount


async def ask_bid_trade(price, symbol, ao):
    return
    ask_bid_distance = spot_currency_config.ASK_BID_DISTANCE.get(symbol)
    if not ask_bid_distance:
        return
    ask_bid_price = random.choice([price * (1 + ask_bid_distance), price * (1 - ask_bid_distance)])
    print(datetime.datetime.now().strftime('%H:%M:%S.%f'), "ask_bid_trade", symbol, price, ask_bid_distance,
          ask_bid_price)
    min_quantity = float(global_variable.SYMBOLS_ORDER_CONDITION.get(symbol, {}).get("minQuantity", 0))
    amount = random.uniform(min_quantity * 1, min_quantity * 20)

    # tasks = [asyncio.ensure_future(
    #     ao.add(symbol, "sell-limit", amount, ask_bid_price, )),
    #     asyncio.ensure_future(
    #         ao.add(symbol, "buy-limit", amount, ask_bid_price, ))
    # ]
    tasks = [asyncio.ensure_future(ao.spot_add_plus(symbol, amount, ask_bid_price, True)),]
    dones, pendings = await asyncio.wait(tasks)


async def risk_control(symbol):
    currency = symbol.split("-")[0]
    price_ask = global_variable.ABC_ASK_BID_PRICE_CONTAINER.get(symbol, {}).get("ask")
    price_bid = global_variable.ABC_ASK_BID_PRICE_CONTAINER.get(symbol, {}).get("bid")
    amount_ask = global_variable.ABC_ASK_BID_PRICE_CONTAINER.get(symbol, {}).get("ask_amount")
    amount_bid = global_variable.ABC_ASK_BID_PRICE_CONTAINER.get(symbol, {}).get("bid_amount")
    price_ts = global_variable.ABC_ASK_BID_PRICE_CONTAINER.get(symbol, {}).get("ts", 0)

    try:
        spec_price_flag = True if price_ask and price_bid and (price_ask / price_bid - 1) > 0.003 else False
    except Exception:
        logger.info(f"risk_control_spec_price_flag_error -{symbol} {traceback.format_exc()}")
        spec_price_flag = False
    price = await libs_price_async.get_weight_price(symbol)
    origin_price_2_u = await currency_feature.get_currency_price_u(symbol, price)
    origin_price = price
    # 买卖一可能有极端情况存在价格N秒不变动
    defense_amount = 0
    record_path_msg = "enter risk_control "

    if price_ask and price_bid and time.time() - price_ts < 300:
        ask_bid_price = (price_ask + price_bid) / 2
        print(f"into risk_control_amount ask-bid {symbol} price_ask:{price_ask} amount_ask:{amount_ask} "
              f"price_bid:{price_bid} amount_bid:{amount_bid} ask_bid_price:{ask_bid_price} price:{price}")
        price_precision = int(global_variable.SYMBOLS_ORDER_CONDITION.get(symbol, {}).get("price", 8))
        price_ask = round(price_ask, price_precision) if price_precision else round(price_ask)
        price_bid = round(price_bid, price_precision) if price_precision else round(price_bid)
        price_ask_bid_diff = round(price_ask - price_bid, price_precision) if price_precision else round(
            price_ask - price_bid)
        ask_bid_price = round(ask_bid_price, price_precision) if price_precision else round(ask_bid_price)
        percent = price / ask_bid_price - 1 if price > ask_bid_price else ask_bid_price / price - 1
        price = ask_bid_price

        if symbol in ["USDC-USDT", "HUSD-USDT", "BUSD-USDT", "BTC-USDT", "ETH-USDT"]:
            return price, 0, spec_price_flag

        last_symbols_ab_mappings = global_variable.LAST_SYMBOLS_AB_MAPPINGS
        p = 1 / 10 ** price_precision
        arbitrage_percent = spot_currency_config.ARBITRAGE_CURRENCY.get(symbol.split('-')[0],
                                                                        spot_currency_config.ARBITRAGE_DEFAULT)
        arbitrage_percent_1 = spot_currency_config.ARBITRAGE_CURRENCY.get(symbol.split('-')[0], 0.002)

        ask_bid_slippage = await update_price_percent(symbol)
        if price_ask_bid_diff < 4 * p and ask_bid_slippage > 0.003:
            defense_amount = max(2 / origin_price_2_u, float(
                global_variable.SYMBOLS_ORDER_CONDITION.get(symbol, {}).get("minQuantity", 0)))
            if ask_bid_price > origin_price and price_bid * (1 - arbitrage_percent_1) >= origin_price:
                price = price_bid
            elif ask_bid_price < origin_price and origin_price >= price_ask * (1 + arbitrage_percent_1):
                price = price_ask
            else:
                defense_amount = float(
                    global_variable.SYMBOLS_ORDER_CONDITION.get(symbol, {}).get("minQuantity", 0)) * random.uniform(1,
                                                                                                                    5)
            # if symbol in config.DANGEROUS_SYMBOLS:
            #     global_variable.ERROR_MESSAGES.append("套利预警1： {} 买一 {} 卖一 {}".format(symbol, price_bid, price_ask))
        elif price_ask / price_bid - 1 > 0.06:
            price = ask_bid_price
            defense_amount = float(global_variable.SYMBOLS_ORDER_CONDITION.get(symbol, {}).get("minQuantity", 0)) * random.uniform(
                    0.04, 1.5)

        elif price_bid * (1 - arbitrage_percent) >= origin_price or origin_price >= price_ask * (
                1 + arbitrage_percent):  # 如果买卖一全在外部成交价以上*1.002或者全在外部成交价/1.002以下
            defense_amount = max(2 / origin_price_2_u, float(
                global_variable.SYMBOLS_ORDER_CONDITION.get(symbol, {}).get("minQuantity", 0)))
            min_amount = 4 / origin_price_2_u
            if price_bid * (1 - arbitrage_percent) >= origin_price and amount_bid < min_amount:
                price = price_bid
            elif origin_price >= price_ask * (1 + arbitrage_percent) and amount_ask < min_amount:
                price = price_ask
            else:
                defense_amount = float(
                    global_variable.SYMBOLS_ORDER_CONDITION.get(symbol, {}).get("minQuantity", 0)) * random.uniform(1,
                                                                                                                    5)
            # if symbol in config.DANGEROUS_SYMBOLS:
            #     global_variable.ERROR_MESSAGES.append("套利预警2： {} 买一 {} 卖一 {}".format(symbol, price_bid, price_ask))
        elif ask_bid_slippage > 0.003:
            if symbol not in last_symbols_ab_mappings:
                last_symbols_ab_mappings[symbol] = {'ask1price': 0, 'bid1price': 0}
            lastask1price = last_symbols_ab_mappings[symbol]['ask1price']
            lastbid1price = last_symbols_ab_mappings[symbol]['bid1price']

            if lastask1price == price_ask and lastbid1price == price_bid:
                # 新获得的价格和上次获得的价格一样的情况
                p = 1 / 10 ** price_precision
                step = p * 3
                price = random.uniform(min(price_ask, price + step) - p, max(price_bid, price - step) + p)
                price = round(price, price_precision) if price_precision else round(price)
                if price in [price_ask, price_bid]:
                    await recode_msg.recode_error_msg(f"{symbol} {lastask1price} {lastbid1price} {price} 偏移价格出现逻辑错误",
                                                      'volume')

            last_symbols_ab_mappings[symbol]['ask1price'] = price_ask
            last_symbols_ab_mappings[symbol]['bid1price'] = price_bid
            print("risk_control_amount_percent", symbol, percent)
            if currency in []:
                pass
            elif percent >= 0.005 or (percent > 0.004 and currency in ["DAI", "FCL", "FEI"]):
                defense_amount = float(
                    global_variable.SYMBOLS_ORDER_CONDITION.get(symbol, {}).get("minQuantity", 0)) * random.uniform(
                    0.004, 2.05)
    else:
        print("risk_control_amount", symbol, global_variable.ABC_ASK_BID_PRICE_CONTAINER)
        if price_ts:
            await recode_msg.recode_error_msg(f"A {symbol}-{price_ask}-{price_bid} {time.time()} {price_ts} 买卖一价格获取异常",
                                              'volume')

    return price, defense_amount, spec_price_flag


async def add_trade_task(symbol, ao, currency_exchange, self_flag):
    currency, zone = symbol.split("-")
    exchange = currency_exchange.get(currency)
    symbols_trades = global_variable.SHARE_VOLUME_MAKER_SYMBOLS
    if not symbols_trades[symbol]:
        return
    try:
        source_amount = (symbols_trades[symbol] / spot_currency_config.amount_rate) * 1.8
        symbols_trades[f"{symbol}_update"] = time.time()
        # with global_variable.SHARE_VOLUME_MAKER_SYMBOLS.lock(timeout=0.001, block=True, sleep_time=0.000001):
        #     trades_dict[symbol] = []  # 内存共享clear不生效
    except IndexError as e:
        logger.info(f"add_trade_task-error {repr(e)}")
        return

    # price = float(trade["p"])
    # price = price if price else float(trade["p"])*(1 + price_distance)
    # price = float(trade["p"])*(1 - price_distance)
    price, defense_amount, spec_price_flag = await risk_control(symbol)
    if defense_amount:
        amount = defense_amount
    else:
        amount = await get_amount(symbol, source_amount, price)
        if amount is not None:
            symbols_trades[symbol] = 0
        else:
            # 合并下小单
            # logger.info(f"T{symbol} 合并下小单")
            return

    logger.info(f"add_trade_task-{symbol}, {exchange}, {price}, {spec_price_flag}, {amount}-{source_amount}")
    # tasks = [asyncio.create_task(
    #     ao.add(symbol, "sell-limit", amount, price, )),
    #     asyncio.create_task(
    #         ao.add(symbol, "buy-limit", amount, price, ))
    # ]
    tasks = [asyncio.create_task(ao.spot_add_plus(symbol, amount, price, spec_price_flag)),]

    if not global_variable.SYMBOLS_PRICE_5MIN.get(symbol, []):
        global_variable.SYMBOLS_PRICE_5MIN[symbol] = []
    global_variable.SYMBOLS_PRICE_5MIN[symbol].append(price)

    for task in tasks:
        res = await task
        if not self_flag:
            if res and res.get("heartbeat"):
                i_live_transit_station("item_instance", f"{symbol}", frequency=WS_FREQUENCY, heart_type=1)
            else:
                # 如果下单有问题，立即报警
                i_live_transit_station("item_instance", f"{symbol}", frequency=WS_FREQUENCY, last_update=0,
                                       heart_type=1)
        i_live_transit_station("main_instance", frequency=60)

    await ask_bid_trade(price, symbol, ao)


@decorator.monitor_handler
async def add_trade_chief(abc_accounts, zone_symbols, currency_exchange):
    try:
        # 初始化main服务心跳监控
        i_live_transit_station("main_instance", frequency=60)
        task = [asyncio.create_task(add_trade(abc_accounts, symbol, currency_exchange)) for symbol in
                zone_symbols]

        await asyncio.wait(task)
    except:
        logger.info(f"add_trade_chief {traceback.format_exc()}")


async def add_trade(abc_accounts, symbol, currency_exchange):
    # 初始化item分服务心跳监控
    i_live_transit_station("item_instance", item_sub_server=f"{symbol}", frequency=WS_FREQUENCY, heart_type=1)

    trade_area = symbol.split('-')[1]
    rank = 0
    base_loop_time = spot_currency_config.special_base_sleep_time.get(symbol, spot_currency_config.base_sleep_time)
    sleep_ratio = spot_currency_config.sleep_ratio
    loop_time = spot_currency_config.SYMBOL_SLEEP_TIME.get(symbol, base_loop_time * sleep_ratio)
    substitute_time = spot_currency_config.SUBSTITUTE_TIME.get(symbol, 60)
    add_last_update = time.time()
    price_num = int(5 * 60 / loop_time)
    while True:
        try:
            if rank > 50000:
                rank = 0
            rank += base_loop_time

            await update_trade_volume_percent()
            await update_symbol_precision()
            await update_vol_coefficient()

            # print(f"测试环境运行中 {symbol}" if libs_config.DEBUG else "线上环境运行中")
            currency, zone = symbol.split("-")
            exchange = currency_exchange.get(currency)
            symbol_trades = global_variable.SHARE_VOLUME_MAKER_SYMBOLS
            if symbol_trades[symbol]:
                add_last_update = time.time()
                self_flag = False
            else:
                # 如果长时间没有对标刷量，程序自动补单
                if time.time() - add_last_update > substitute_time:
                    min_quantity = float(global_variable.SYMBOLS_ORDER_CONDITION.get(symbol, {}).get("minQuantity", 0))
                    symbol_trades[symbol] = min_quantity * random.uniform(2, 15)
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
            for ao in abc_accounts:
                await add_trade_task(symbol, ao, currency_exchange, self_flag)

            during_time = time.time() - start_time
            if symbol in ["BTC-USDT"]:
                min_rand, max_rand = 0.85, 1.15
            else:
                min_rand, max_rand = spot_currency_config.SLEEP_RAND_WEIGHT_MAPPINGS[trade_area]
            if during_time < base_loop_time:
                need_sleep_time = (base_loop_time - during_time) * random.uniform(min_rand, max_rand)
                # logger.info(f"T{symbol} {base_loop_time=} {during_time=} {need_sleep_time=}")
                await asyncio.sleep(need_sleep_time)

        except BaseException as e:
            logger.info(f"add_trade - {traceback.format_exc()}")
            await asyncio.sleep(2)


async def add_trade_self_fixed_task(symbol, ao, heart_beat_time):
    price, _, spec_price_flag = await risk_control(symbol)
    amount = float(global_variable.SYMBOLS_ORDER_CONDITION.get(symbol, {}).get("minQuantity", 0))
    logger.info(f"add_trade_self_fixed_task, {symbol}, {price}, {spec_price_flag}, {amount}")
    # tasks = [asyncio.create_task(
    #     ao.add(symbol, "sell-limit", amount, price, )),
    #     asyncio.create_task(
    #         ao.add(symbol, "buy-limit", amount, price, ))
    # ]
    tasks = [asyncio.create_task(ao.spot_add_plus(symbol, amount, price, spec_price_flag)),]

    for task in tasks:
        res = await task
        if res and res.get("heartbeat"):
            i_live_transit_station("item_instance", f"{symbol}_fixed", frequency=heart_beat_time, heart_type=1)
        else:
            i_live_transit_station("item_instance", f"{symbol}_fixed", frequency=heart_beat_time, last_update=0, heart_type=1)


async def add_trade_self_task(symbol, ao, heart_beat_time):
    currency, zone = symbol.split("-")
    price, defense_amount, spec_price_flag = await risk_control(symbol)
    min_quantity = float(global_variable.SYMBOLS_ORDER_CONDITION.get(symbol, {}).get("minQuantity", 0))
    if defense_amount:
        amount = defense_amount
    else:
        currency_config = global_variable.G_TRADE_CURRENCY_CONFIG[currency]
        # 是否为主力刷量 还是 防止对标刷量服务出现问题而设置的自刷量
        if currency_config["self"] == 1:
            _market_price = await currency_feature.update_currency_market_value(currency)
            custom_amount = currency_config["self_market_value"] / _market_price
            amount = random.uniform(custom_amount * 0.2, custom_amount * 3)
            amount = await get_amount(symbol, amount, price)
        else:
            # if symbol in ["USDR-USDT", "USDQ-USDT", "EURR-USDT", "EURQ-USDT"]:
            #     numbers = [0.1, 0.2, 0.3, 0.4, 0.5, 1, 1.1, 1.2, 2, 2.2, 2.5, 3, 4, 5]
            #     select_n = random.choice(numbers)
            #     amount = min_quantity * select_n * random.uniform(1, 1.2)
                # amount = await get_amount(symbol, amount, price)
            # else:
            amount = random.uniform(min_quantity * 1, min_quantity * 4)
        # amount = await get_amount(symbol, amount, price)
    logger.info(f"add_trade_self_task, {symbol}, {price}, {spec_price_flag}, {amount}")
    # tasks = [asyncio.create_task(
    #     ao.add(symbol, "sell-limit", amount, price, )),
    #     asyncio.create_task(
    #         ao.add(symbol, "buy-limit", amount, price, ))
    # ]
    tasks = [asyncio.create_task(ao.spot_add_plus(symbol, amount, price, spec_price_flag)),]

    for task in tasks:
        res = await task
        if res and res.get("heartbeat"):
            i_live_transit_station("item_instance", f"{symbol}", frequency=heart_beat_time, heart_type=1)
        else:
            i_live_transit_station("item_instance", f"{symbol}", frequency=heart_beat_time, last_update=0, heart_type=1)
        i_live_transit_station("main_instance", frequency=60)


@decorator.monitor_handler
async def add_trade_self_chief(abc_accounts, self_symbols):
    try:
        i_live_transit_station("main_instance", frequency=60)
        [i_live_transit_station("item_instance", f"{symbol}", frequency=WS_FREQUENCY, heart_type=1) for symbol in
         self_symbols]
        task = [asyncio.create_task(add_trade_self(abc_accounts, symbol)) for symbol in self_symbols]
        for i in self_symbols:
            currency, quote = i.split("-")
            level = currency_feature.currency_dangerous_level(currency)
            if level <= 3 and quote == "USDT":
                i_live_transit_station("item_instance", f"{i}_fixed", frequency=60, heart_type=1)
                task.append(asyncio.create_task(add_trade_fixed_self(abc_accounts, i)))

        await asyncio.wait(task)
    except Exception as e:
        logger.info(f"add_trade_self_chief {e} {traceback.format_exc()}")


async def add_trade_fixed_self(abc_accounts, symbol):
    # print("测试环境运行中" if libs_config.DEBUG else "线上环境运行中")
    order_account = abc_accounts[0]
    flag_start, flag_end = True, True
    start_fixed, end_fixed = 1, 59
    interval = 1
    while True:
        try:
            now_time = datetime.datetime.now()
            if now_time.minute % interval in [0, interval-1]:
                if now_time.minute % interval == interval-1 and now_time.second >= end_fixed and flag_end:
                    await add_trade_self_fixed_task(symbol, order_account, interval * 60 + 10)
                    flag_end = False
                elif now_time.minute % interval == 0 and now_time.second <= start_fixed and flag_start:
                    await add_trade_self_fixed_task(symbol, order_account, interval * 60 + 10)
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


async def add_trade_self(abc_accounts, symbol):
    # print("测试环境运行中" if libs_config.DEBUG else "线上环境运行中")
    rank = 0
    trade_area = 'SELF_TRADE'

    base_loop_time = spot_currency_config.self_base_sleep_time
    loop_time = spot_currency_config.SELF_SYMBOL_SLEEP_TIME.get(symbol, base_loop_time)
    heart_beat_time = loop_time + base_loop_time * spot_currency_config.SLEEP_RAND_WEIGHT_MAPPINGS[trade_area][1] * 2
    i_live_transit_station("item_instance", f"{symbol}", frequency=heart_beat_time, heart_type=1)

    while True:
        try:
            if rank > 50000:
                rank = 0
            rank += base_loop_time

            await update_swap_vol()
            await update_trade_volume_percent()
            await update_symbol_precision()

            order_account = abc_accounts[0]
            if rank % loop_time != 0:
                await asyncio.sleep(base_loop_time)
                continue

            start_time = time.time()
            await add_trade_self_task(symbol, order_account, heart_beat_time)
            during_time = time.time() - start_time
            logger.info(f"add_trade_self-{symbol} time, {during_time=}")
            min_rand, max_rand = spot_currency_config.SLEEP_RAND_WEIGHT_MAPPINGS[trade_area]
            if during_time < base_loop_time:
                await asyncio.sleep((base_loop_time - during_time) * random.uniform(min_rand, max_rand))
        except Exception as e:
            print(datetime.datetime.now().strftime('%H:%M:%S.%f'), traceback.format_exc())
            await asyncio.sleep(2)


# 撤单服务
async def getorderid(symbol, ao):
    orderids = []
    # re = await ao.current_list(symbol)
    result = await ao.current_all(symbol, 1000)
    for i in result:
        if i['status'] != 4:
            orderid = i['order_sn']
            ctime = i['ctime']
            timeArray = time.strptime(ctime, "%Y-%m-%d %H:%M:%S")
            timeStamp = int(time.mktime(timeArray))
            current_time = int(time.time())
            if timeStamp < current_time - 2:
                orderids.append(orderid)
    return orderids


async def cancel_order_task(symbol, cancel_account):
    while True:

        try:
            res = await cancel_account.cancel(symbol=symbol)
            # cancel_orders = await getorderid(symbol, cancel_account)
            # order_list = []
            # for i in cancel_orders:
            #     order_list.append(str(i))
            # cancel_orders = order_list
            # logger.info(f"cancel_orders, {symbol}, {len(order_list)}")
            # if order_list:
            #     await cancel_account.cancel(cancel_orders)
            i_live_transit_station("main_instance", frequency=sleep_time(spot_currency_config.base_sleep_time) * 2)
            if res.get("errno") != -1:
                i_live_transit_station("item_instance", f"{symbol}",
                                       frequency=sleep_time(spot_currency_config.base_sleep_time) * 2, heart_type=2)
        except Exception as e:
            logger.error(f"cancel_order_task-spot, {symbol} {traceback.format_exc()}")
        finally:
            await asyncio.sleep(sleep_time(spot_currency_config.special_base_sleep_time.get(symbol, spot_currency_config.base_sleep_time)))


@decorator.monitor_handler
async def cancel_order(abc_accounts, symbols):
    try:
        i_live_transit_station("main_instance", frequency=sleep_time(spot_currency_config.base_sleep_time) * 2)
        [i_live_transit_station("item_instance", f"{symbol}",
                                frequency=sleep_time(spot_currency_config.base_sleep_time) * 2, heart_type=2) for symbol
         in symbols]

        tasks = []
        for ao in abc_accounts:
            for symbol in symbols:
                tasks.append(asyncio.create_task(
                    cancel_order_task(symbol, ao)))

        await asyncio.wait(tasks)
    except Exception as e:
        print(datetime.datetime.now().strftime('%H:%M:%S.%f'), traceback.format_exc())
        await asyncio.sleep(sleep_time(spot_currency_config.base_sleep_time))


def sleep_time(t):
    if 0 <= datetime.datetime.now().hour <= 7:
        t = t * 1.5
    return t


if __name__ == "__main__":
    while True:
        pass
