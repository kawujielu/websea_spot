import traceback
import time
import random
import asyncio
import sys
from strategy.strategy_base_settings import (ASK_BID_PERCENT, max_adj_percent, adj_active, adj_support_list,
                                             min_adj_value, ASK_BID_PERCENT_SPEC)
from config import (CancelWarningTime, SYMBOLS_USE_ASK1_BID1, ask1_bid1_add_percent)
from libs.heartbeat import i_live_well, SEND_MIN_TIME
from libs.config_update_ser import update_price_percent, update_volume_percent, update_price_percent_to_max, \
    update_price_percent_via_hedge, update_config_precisions, update_volume_via_price
from libs.adj_component import update_adj_args
from strategy.near_strategy.near_settings import sleepTime as one_minute_sleep_time
import config
from libs import recode_msg, libs_price_async


class BaseStrategyHub(object):
    def __init__(self, symbol, abc, ss, logger=None):
        self.ss = ss
        self.symbol = symbol
        self.currency, self.quote = symbol.split("-")
        self.abc = abc
        self.logger = logger
        self.errors = []
        self.price_polaris = {}
        self.price_polaris_update = 0
        self.latest_update_price = None
        self.no_order_times = 0
        self.near_20_prices = []
        self.avg_price_to_adj_shock = []
        self.avg_price_to_adj_shock_groups = 4  # 检查4组数据
        self.adj_shock_one_group_minutes = 2  # 每组2分钟的数据
        self.delay_time = 60 * 60 * 0.3
        self.adj_prices = {}
        self.one_minute_cal_times = int(60 // one_minute_sleep_time)  # 0 < one_minute_sleep_time <= 60
        self.shock_all_group_counts = self.avg_price_to_adj_shock_groups * self.one_minute_cal_times * self.adj_shock_one_group_minutes
        self.shock_one_group_counts = self.adj_shock_one_group_minutes * self.one_minute_cal_times
        self.spread_price_weight = 1
        self.spread_amount_weight = 1
        self.spread_defense_amount_weight = 1
        self.to_change = ""
        self.ask_rate = 1
        self.bid_rate = 1
        self.rate = 0
        self.flash_orders = []
        self.buy_orders = []
        self.sell_orders = []
        self.order_data = {}
        self.order_list = []
        self.request_time = 0
        self.order_error = False

    async def get_price(self, symbol):
        currency = symbol.split("-")[0]
        if currency not in self.adj_prices:
            self.adj_prices[currency] = {}
        try:
            with self.logger.catch(reraise=True):
                avg_price, ask_bid_percent = None, None
                dangerous_level = config.SPOT_CURRENCY_CONFIG[currency]["dangerous_level"]
                ask_bid_percent = 0.008 if dangerous_level > 4 else ASK_BID_PERCENT
                ask_bid_percent = ASK_BID_PERCENT_SPEC.get(currency, ask_bid_percent)
                ask_bid_percent = ASK_BID_PERCENT_SPEC.get(self.symbol, ask_bid_percent)
                ask_bid_percent /= 2

                if currency in SYMBOLS_USE_ASK1_BID1:
                    ask1_init, bid1_init = await libs_price_async.get_weight_aks_bid(symbol)
                    if ask1_init and bid1_init:
                        avg_price = (ask1_init + bid1_init) / 2
                        percent = (ask1_init - bid1_init) / (ask1_init + bid1_init)
                        percent = percent if percent * ask1_bid1_add_percent > 1 else percent * ask1_bid1_add_percent
                        ask_bid_percent = max(ask_bid_percent, percent)
                if currency not in SYMBOLS_USE_ASK1_BID1 or avg_price is None:
                    avg_price = await libs_price_async.get_weight_price(symbol)

        except (Exception, BaseException) as e:
            message = f"{self.symbol}-{self.ss.NAME} get price from redis failed. "
            self.logger.info(f"{message} - {traceback.format_exc()}")
            await recode_msg.recode_error_msg(f"{message} {sys.exc_info()}", 'send_telegram_important_msg_url')
            raise e

        # 如果近盘口多次因为价格波动小没有更新则更新，波动小不更新
        self.no_order_times += 1
        adj_args = update_adj_args(symbol)
        if self.ss.NAME == "NEAR":
            self.near_20_prices.append(avg_price)
            self.near_20_prices = self.near_20_prices[-self.one_minute_cal_times:]
            self.avg_price_to_adj_shock.append(avg_price)
            self.avg_price_to_adj_shock = self.avg_price_to_adj_shock[-self.shock_all_group_counts:]
            max_near_20_prices, min_near_20_prices = max(self.near_20_prices), min(self.near_20_prices)
            price_change_percent = (max_near_20_prices - min_near_20_prices) / min_near_20_prices
            if price_change_percent > 0.5:  # 价格波动剧烈
                ask_bid_percent = max(0.04, ask_bid_percent)  # 价差调整
                self.adj_prices[currency]["adj_1"] = {}
                self.adj_prices[currency]["adj_1"]["ask_bid_percent"] = ask_bid_percent
                self.adj_prices[currency]["adj_1"]["expired_time_s"] = time.time() + self.delay_time * 0.5
                # await update_price_percent_to_max(currency, ask_bid_percent)  #  更新redis和配置文件
                msg = f"{symbol}价格剧烈波动,price_change_percent:{price_change_percent}"
                self.logger.error(msg)
                await recode_msg.recode_error_msg(msg, 'send_telegram_important_msg_url')
            if len(self.avg_price_to_adj_shock) == self.shock_all_group_counts:
                avg_price_group = [
                    self.avg_price_to_adj_shock[self.shock_one_group_counts * i:self.shock_one_group_counts * (i + 1)]
                    for i in range(0, self.avg_price_to_adj_shock_groups)]  # 按组切割
                avg_price_group_max_min = [[max(i), min(i)] for i in avg_price_group]  # 取出每组的最大、最小值
                t = 0.03 if currency in ["GROK"] else 0.02
                big_shock = all((i[0] - i[1]) / i[1] > t for i in avg_price_group_max_min)  # 每组的波动都需大于阈值
                avgs = [(i[0] + i[1]) / 2 for i in avg_price_group_max_min]
                if big_shock and (max(avgs) - min(avgs)) / min(avgs) < 0.01:
                    # 计算avg_price
                    ask_bid_percent = ask_bid_percent if ask_bid_percent > 0.06 else max(2 * ask_bid_percent, 0.06)
                    self.adj_prices[currency]["adj_2"] = {}
                    self.adj_prices[currency]["adj_2"]["ask_bid_percent"] = ask_bid_percent
                    self.adj_prices[currency]["adj_2"]["expired_time_s"] = time.time() + self.delay_time
                    msg = f"[P0]{symbol}异常震荡!!!!!!!!!!"
                    # await recode_msg.recode_error_msg(msg, 'send_telegram_important_msg_url')
                    self.logger.error(f"{msg},调整价差至{ask_bid_percent},avg_price_group:{avg_price_group}")
            expired_info = self.adj_prices[currency]
            self.logger.info(f"{symbol}, expired_info:{expired_info}")
            if expired_info.get("adj_1") or expired_info.get("adj_2"):
                datetime_now = time.time()
                expired_info_adj1 = expired_info.get("adj_1", {})
                expired_info_adj2 = expired_info.get("adj_2", {})
                expired_time_adj1 = expired_info_adj1.get("expired_time_s", 0)
                expired_time_adj2 = expired_info_adj2.get("expired_time_s", 0)
                if datetime_now < max(expired_time_adj1, expired_time_adj2):
                    if datetime_now < expired_time_adj1:
                        self.logger.error(f"{symbol}波动价差未过期")
                        ask_bid_percent = max(expired_info_adj1["ask_bid_percent"], ask_bid_percent)
                    if datetime_now < expired_time_adj2:
                        self.logger.error(f"{symbol}震荡价差未过期")
                        ask_bid_percent = max(expired_info_adj2["ask_bid_percent"], ask_bid_percent)
                else:
                    self.logger.error(
                        f"{symbol}价差已过期{datetime_now - max(expired_time_adj1, expired_time_adj2)}秒,恢复价差至{ask_bid_percent}")
        elif self.ss.NAME == "DEPTH":
            # 防止重启的时候服务器压力 所以第一次不更新这个策略
            if not self.latest_update_price:
                self.latest_update_price = avg_price

        if self.latest_update_price:
            price_rate = abs(avg_price - self.latest_update_price) / self.latest_update_price
            if self.no_order_times < adj_args[f"{self.ss.NAME.lower()}_price_amount"] and \
                price_rate < adj_args[f"{self.ss.NAME.lower()}_price_percent"]:
                return None, None

        self.latest_update_price = avg_price
        self.no_order_times = 0

        if adj_active and self.ss.NAME in ["NEAR", "DEFENSE"] and currency in adj_support_list:
            if int(time.time()) - self.price_polaris_update > 6:
                try:
                    with self.logger.catch(reraise=True):
                        val = await libs_price_async.redis_db_adj.async_connection.get(f"polaris-{currency}")
                        self.price_polaris[symbol] = float(val) if val else 1
                except (Exception, BaseException) as e:
                    self.price_polaris[symbol] = 1
                self.price_polaris_update = int(time.time())

            adj_percent = min(float(self.price_polaris.get(symbol, 1)), max_adj_percent)
        else:
            adj_percent = 1

        await update_price_percent()
        await update_volume_percent()
        await update_config_precisions()  # 修正 后台的最新精度

        price_precision = int(config.SYMBOLS_ORDER_CONDITION[self.symbol].get("price", 8))
        avg_price = round(avg_price, price_precision) if price_precision else round(avg_price)

        ask_bid_price = ASK_BID_PERCENT_SPEC.get(f"{self.symbol}_PRICE")  # 固定价格的价差
        if ask_bid_price and ask_bid_price > 0:
            ask_bid_price = ask_bid_price * adj_percent
            ask_bid_price_h = round(ask_bid_price / 2.0, price_precision) if price_precision else round(
                ask_bid_price / 2.0)

            bid_price, ask_price = avg_price - ask_bid_price_h, avg_price + (ask_bid_price - ask_bid_price_h)

        else:
            ask_bid_percent = ask_bid_percent * adj_percent
            if adj_percent > 1:
                ask_bid_percent = max(ask_bid_percent, min_adj_value)
            # 单边价差调整
            ask_percent = ASK_BID_PERCENT_SPEC.get("ASK_{}".format(self.symbol.split("-")[0]), ask_bid_percent)
            bid_percent = ASK_BID_PERCENT_SPEC.get("BID_{}".format(self.symbol.split("-")[0]), ask_bid_percent)

            if self.symbol.split("-")[1] in ["BTC", "ETH"]:  # BTC区和ETH区的交易对价差最小值控制
                ask_percent, bid_percent = max(ask_percent, 0.005), max(bid_percent, 0.005)

            bid_price, ask_price = avg_price * (1 - bid_percent), avg_price * (1 + ask_percent)

        # 通过价格变化矫正买卖量
        rate = (avg_price - self.latest_update_price) / self.latest_update_price if self.latest_update_price else 0
        self.rate = rate
        self.ask_rate, self.bid_rate = await update_volume_via_price(symbol, rate)

        # 通过对冲池量矫正价差
        update_config_via_hedge = await update_price_percent_via_hedge(symbol)
        self.spread_price_weight = update_config_via_hedge['spread_percent']
        self.spread_amount_weight = update_config_via_hedge['amount_percent']
        self.spread_defense_amount_weight = update_config_via_hedge['defense_amount_percent']
        self.to_change = update_config_via_hedge['to_change']

        adj_weight = update_config_via_hedge['scaled_percent']
        bid_price = bid_price * (1 - adj_weight)
        ask_price = ask_price * (1 + adj_weight)

        price_precision_gap = 1 / (10 ** price_precision)
        if ask_price - bid_price < price_precision_gap:
            bid_price, ask_price = avg_price - price_precision_gap, avg_price

        self.logger.info(f"{self.ss.NAME}, {symbol}, 上次价格：{self.latest_update_price} 最新价格：{avg_price}"
                         f"{ask_bid_percent= } {ask_bid_price= } {bid_price= } {ask_price= }")

        return bid_price, ask_price

    async def create_orders_batch(self, buy_orders, sell_orders):
        to_create = buy_orders[0:1] + sell_orders[0:1] + buy_orders[1:] + sell_orders[1:]
        orders = []

        if len(to_create) > 0:
            self.logger.info(f"{self.ss.NAME}-{self.symbol}:create_orders_batch:-------->")
            to_create_orders = [
                {"symbol": order["symbol"], "type": order["type"], "amount": order["amount"], "price": order["price"]}
                for order in to_create]
            create_res = await self.abc.add_batch_asyncio(to_create_orders)
            try:
                with self.logger.catch(reraise=True):
                    if create_res.get("errno") != 0:
                        err_msg = f"{self.ss.NAME}, {self.symbol}, {create_res}"
                        self.errors.append(err_msg)
                    else:
                        orders_list = create_res["result"]
                        org_orders_list = create_res["args"]
                        if len(orders_list) != len(org_orders_list):
                            msg = f"len(orders_list) != len(org_orders_list)"
                            self.logger.error(msg)
                            self.errors.append(msg)
                        for ind, order in enumerate(orders_list):
                            order_id = order.get("order_sn")
                            if order_id is None:
                                self.errors.append(order_id)
                            if order_id:
                                # self.logger.info(f"flash loop create order id:{order_id}")
                                orders.append(order_id)
                                side = "buy" if org_orders_list[ind]['type'] == "buy-limit" else "sell"
                                self.order_list.append(
                                    {'order_sn': order_id, 'ctime': create_res['ctime'],
                                     'price': org_orders_list[ind]['price'], 'side': side})
            except (Exception, BaseException) as e:
                self.logger.info(f"create_orders {traceback.format_exc()}")
                await recode_msg.recode_error_msg(f"create_orders {repr(e)}", 'send_telegram_important_msg_url')

            # if len(self.errors) / len(to_create) >= 0.01:
            create_error_len = len(self.errors)
            # if create_error_len > 2:
            if self.errors:
                self.logger.error(self.errors)
                await recode_msg.recode_error_msg(f"create_orders {set(self.errors)} - num: {create_error_len}",
                                                  'send_telegram_important_msg_url')
                self.order_error = True
            else:
                self.order_error = False
                await i_live_well(f"{self.symbol}|{self.ss.NAME}", max(SEND_MIN_TIME * 2, self.ss.sleepTime) * 1.5, 0)

            self.errors.clear()

            return orders

    async def create_orders(self, buy_orders, sell_orders):
        to_create = buy_orders[0:1] + sell_orders[0:1] + buy_orders[1:] + sell_orders[1:]
        orders = []

        if len(to_create) > 0:
            self.logger.info(f"{self.ss.NAME}-{self.symbol}:orders_to_create:-------->")

            orders_list = [asyncio.create_task(self.abc.add_asyncio(symbol=order['symbol'],
                                                                    type=order['type'],
                                                                    amount=order['amount'],
                                                                    price=order['price'])) for order in to_create]

            for order in orders_list:
                try:
                    with self.logger.catch(reraise=True):
                        res = await order
                        if res.get("errno") != 0:
                            err_msg = f"{self.ss.NAME}, {self.symbol}, {res}"
                            self.errors.append(err_msg)
                        else:
                            order_id = res.get("result", {}).get("order_sn")
                            args = res.get("args")
                            if order_id:
                                # self.logger.info(f"flash loop create order id:{order_id}")
                                orders.append(order_id)
                                side = "buy" if args['data']['type'] == "buy-limit" else "sell"
                                self.order_list.append(
                                    {'order_sn': order_id, 'ctime': args['data']['ctime'],
                                     'price': args['data']['price'], 'side': side})
                except (Exception, BaseException) as e:
                    self.logger.info(f"create_orders {traceback.format_exc()}")
                    await recode_msg.recode_error_msg(f"create_orders {repr(e)}", 'send_telegram_important_msg_url')

            # if len(self.errors) / len(to_create) >= 0.01:
            create_error_len = len(self.errors)
            if create_error_len > 2:
                await recode_msg.recode_error_msg(f"create_orders {set(self.errors)} - num: {create_error_len}",
                                                  'send_telegram_important_msg_url')
                self.order_error = True
            else:
                self.order_error = False
                await i_live_well(f"{self.symbol}|{self.ss.NAME}", max(SEND_MIN_TIME * 2, self.ss.sleepTime) * 1.5, 0)

            self.errors.clear()

            return orders

    async def cancel_price_orders(self, ask1_price, bid1_price):
        price_precision = int(config.SYMBOLS_ORDER_CONDITION[self.symbol].get("price", 8))
        p = 1 / 10 ** price_precision
        ask1_price = round(ask1_price, price_precision) if price_precision else round(ask1_price)
        bid1_price = round(bid1_price, price_precision) if price_precision else round(bid1_price)
        cancel_cross_list = []
        cancel_list = []
        # all_cancel_list = []
        begin_time = time.time()
        orders = self.order_list
        if self.request_time > self.ss.RESET_TIMES:
            self.request_time = 0
        if not orders or self.request_time % 5 == 0 or self.order_error:
            try:
                with self.logger.catch(reraise=True):
                    orders = await self.abc.current_list_order_details(self.symbol, 300)
                    current_time = int(time.time())
                    new_orders = []

                    for o in orders:
                        c_time = int(time.mktime(time.strptime(o['ctime'], "%Y-%m-%d %H:%M:%S")))
                        o["ctime"] = c_time
                        if self.request_time != 0:
                            # 时间太长的单子就表示撤不掉的
                            if current_time - c_time < 10 * 60:
                                new_orders.append(o)
                        else:
                            # self.logger.info(f"{self.symbol}-get_all_current_list_order_details")
                            new_orders.append(o)
                    self.order_list = new_orders

            except (Exception, BaseException) as e:
                self.logger.info(f"current_list_order_details {traceback.print_exc()}")
                await recode_msg.recode_error_msg(f"current_list_order_details {repr(e)}", 'send_telegram_important_msg_url')
        self.request_time = self.request_time + 1

        try:
            with self.logger.catch(reraise=True):
                for order in orders:
                    orderid = order['order_sn']
                    ctime = order['ctime']
                    price = float(order['price'])
                    side = order['side']
                    if True:
                    # if time.time() - time_stamp < 10 * 60:
                    # if 1:  # abs(ctime - int(time.time())) > self.ss.cancel_order_time:
                        if side == "buy" and price + p >= ask1_price:
                            # self.logger.info(f"{self.symbol}, cross-order, {side}, {price}, {ask1_price}")
                            cancel_cross_list.append(orderid)
                        elif side == "sell" and price - p <= bid1_price:
                            # self.logger.info(f"{self.symbol}, cross-order, {side}, {price}, {bid1_price}")
                            cancel_cross_list.append(orderid)
                        else:
                            cancel_list.append(orderid)
                    # all_cancel_list.append(orderid)

                if cancel_cross_list:
                    cancel_time = await self.cancel_cross_orders(cancel_cross_list)
                    self.logger.warning(f'{self.ss.NAME}:{self.symbol}---->Cancel Cross Order :{cancel_time}')
                running_time = round(time.time() - begin_time, 2)
                self.logger.warning(f'{self.ss.NAME}:{self.symbol}---->Cancel Cross Order Time: {running_time}s.')
                # 正常应该放在真正撤单的地方清除，但是如果存在接口报错，会导致变量一直增加，保险机制每5次请求一次currenct_list接口赋值
                self.order_list = []
                self.flash_orders = []
        except (Exception, BaseException) as e:
            self.logger.info(f"cancel_price_orders {traceback.format_exc()}")
            await recode_msg.recode_error_msg(f"cancel_price_orders {repr(e)}", 'send_telegram_important_msg_url')

        return cancel_list
        # return all_cancel_list

    async def cancel_cross_orders(self, order_ids):
        begin_time = time.time()

        cancel_list = order_ids
        if cancel_list:
            try:
                with self.logger.catch(reraise=True):
                    res = await self.abc.cancel(cancel_list)
                    errno = res.get("errno", 0)
                    fail_list = res.get('fail')
                    if errno == -1 and fail_list:
                        res = await self.abc.cancel(fail_list)
                        self.logger.info(f"cancel_cross_orders-try_again1 {res}")
                    elif errno == -1:
                        res = await self.abc.cancel(cancel_list)
                        self.logger.info(f"cancel_cross_orders-try_again2 {res}")
            except (Exception, BaseException) as e:
                self.logger.info(f"cancel_cross_orders {traceback.format_exc()}")
                await recode_msg.recode_error_msg(f"cancel_cross_orders {repr(e)}", 'send_telegram_important_msg_url')
        running_time = round(time.time() - begin_time, 2)
        self.logger.warning(f'{self.ss.NAME}:{self.symbol}---->Cancel running time: {running_time}s.')
        return running_time

    async def update_adj_price(self):
        try:
            with self.logger.catch(reraise=True):
                bid_price, ask_price = await self.get_price(self.symbol)
        except Exception as e:
            message = f"{self.symbol}, {self.ss.NAME}"
            self.logger.info(f"{message} - {traceback.format_exc()}")
            await recode_msg.recode_error_msg(f"{message} - {repr(e)}", 'send_telegram_important_msg_url')
            await asyncio.sleep(CancelWarningTime)

        return bid_price, ask_price

    def prepare_orders(self, bid_price, ask_price):
        return [], []

    async def loop(self):
        try:
            with self.logger.catch(reraise=True):
                # Step 1
                bid_price, ask_price = await self.update_adj_price()
                if bid_price is None and ask_price is None:
                    self.logger.info(f"{self.ss.NAME}, {self.symbol}, 波动小!")
                    if not self.order_error:
                        await i_live_well(f"{self.symbol}|{self.ss.NAME}",
                                          max(SEND_MIN_TIME * 2, self.ss.sleepTime) * 1.5, 0)
                    return

                # Step 2
                if self.symbol in config.USE_GEAR_SYMBOLS and time.time() - self.order_data.get("ts", 0) > 5:
                    asks_data, bids_data, ex = await libs_price_async.get_weight_gears_price(self.symbol, )
                    self.order_data = {"asks": asks_data, "bids": bids_data, "ex": ex, "ts": time.time()}
                buy_orders, sell_orders = self.prepare_orders(bid_price, ask_price)
                cancel_orders = await self.cancel_price_orders(ask_price, bid_price)

                self.buy_orders = buy_orders[:10]
                self.sell_orders = sell_orders[:10]

                if 0 < self.ss.percent_order < 1:
                    buy_number = int(self.ss.percent_order * len(buy_orders))
                    sell_number = int(self.ss.percent_order * len(sell_orders))
                    cancel_number = int(self.ss.percent_order * len(cancel_orders))

                    for i in range(int(1 / self.ss.percent_order) + 1):
                        t1 = asyncio.create_task(
                            self.create_orders_batch(buy_orders[i * buy_number:i * buy_number + buy_number],
                                                     sell_orders[i * sell_number:i * sell_number + sell_number]))
                        #
                        # if self.symbol in ["WLFI-USDT", "ERA-USDT", "PUMP-USDT", "H-USDT", "IDOL-USDT"]:
                        #     t1 = asyncio.create_task(
                        #         self.create_orders_batch(buy_orders[i * buy_number:i * buy_number + buy_number],
                        #                                  sell_orders[i * sell_number:i * sell_number + sell_number]))
                        # else:
                        #     t1 = asyncio.create_task(
                        #         self.create_orders(buy_orders[i * buy_number:i * buy_number + buy_number],
                        #                            sell_orders[i * sell_number:i * sell_number + sell_number]))
                        if i == 0:  # 首次先确保下单完成，再撤单，之后下单和撤单进行并发，最终等待结果
                            await t1
                        t2 = asyncio.create_task(
                            self.cancel_cross_orders(cancel_orders[i * cancel_number:i * cancel_number + cancel_number]))
                        if i != 0:
                            await t1
                        running_time = await t2
                        if running_time > CancelWarningTime:
                            await recode_msg.recode_error_msg(
                                str("%s:%s撤销时间出现异常，当前撤销时间：%s" % (self.ss.NAME, self.symbol, running_time)),
                                'send_telegram_important_msg_url')
                else:
                    t1 = asyncio.create_task(self.create_orders_batch(buy_orders, sell_orders))
                    # if self.symbol in ["WLFI-USDT", "ERA-USDT", "PUMP-USDT", "H-USDT", "IDOL-USDT"]:
                    #     t1 = asyncio.create_task(self.create_orders_batch(buy_orders, sell_orders))
                    # else:
                    #     t1 = asyncio.create_task(self.create_orders(buy_orders, sell_orders))

                    await t1
                    t2 = asyncio.create_task(self.cancel_cross_orders(cancel_orders))
                    running_time = await t2
                    if running_time > CancelWarningTime:
                        await recode_msg.recode_error_msg(
                            str("%s:%s撤销时间出现异常，当前撤销时间：%s" % (self.ss.NAME, self.symbol, running_time)),
                            'send_telegram_important_msg_url')
                self.logger.info(f'{self.ss.NAME}:{self.symbol} --------------- END')
                await self.logger.complete()
        except (Exception, BaseException) as e:
            raise e

    async def loop_flash(self):
        if self.symbol not in config.NEAR_FLASH_SYMBOL:
            return
        try:
            # 因为可能已经下一轮正常逻辑的时候撤掉了，self.flash_orders会被清空
            if self.flash_orders:
                # res = await self.abc.cancel(cancel_orders)
                res = await self.cancel_cross_orders(self.flash_orders)
            order_num = 3 if self.symbol.split("-")[0] in ["BTC", "ETH"] else 2

            if len(self.buy_orders) >= order_num and len(self.sell_orders) >= order_num:
                buy_order = random.sample(self.buy_orders[:6], order_num)
                sell_order = random.sample(self.sell_orders[:6], order_num)

                bid_flag, ask_flag = True, True
                for order in buy_order:
                    if self.symbol.split("-")[0] in ["BTC"]:
                        order["amount"] = random.uniform(1, 1.1)
                    elif self.symbol.split("-")[0] in ["ETH"]:
                        order["amount"] = random.uniform(10, 15)
                    else:
                        order["amount"] = random.uniform(order["amount"] * 0.3, order["amount"] * 0.4)

                    if bid_flag:
                        order['price'] = order['price'] - 0.1 ** int(
                            config.SYMBOLS_ORDER_CONDITION[self.symbol].get("price", 8))
                        bid_flag = False

                for order in sell_order:
                    if self.symbol.split("-")[0] in ["BTC"]:
                        order["amount"] = random.uniform(1, 1.1)
                    elif self.symbol.split("-")[0] in ["ETH"]:
                        order["amount"] = random.uniform(10, 15)
                    else:
                        order["amount"] = random.uniform(order["amount"] * 0.3, order["amount"] * 0.4)
                    if ask_flag:
                        order['price'] = order['price'] + 0.1 ** int(
                            config.SYMBOLS_ORDER_CONDITION[self.symbol].get("price", 8))
                        ask_flag = False

                # self.logger.info(f"{self.symbol} into flash loop 下买单：{buy_order}, 下卖单：{sell_order}")
                self.flash_orders = await self.create_orders(buy_order, sell_order)
        except (Exception, BaseException) as e:
            self.logger.error(f"loop_flash_error:{traceback.format_exc()}")
            raise e




if __name__ == '__main__':
    run()