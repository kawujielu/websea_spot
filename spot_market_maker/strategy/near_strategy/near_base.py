
import traceback
import sys
import time
import random
from strategy.near_strategy import near_settings as ss
from strategy import strategy_base_settings
from strategy.strategy_base import BaseStrategyHub
from config import (DEBUG, currency_conf_danger_currency)
import asyncio
from loguru import logger
from libs.config_update_ser import maintenance_status
from many_config import risk_control_c, global_variable
import config
from libs import recode_msg
import copy
import numpy as np


class NearStrategyHub(BaseStrategyHub):

    def prepare_order(self, index, bid_price, ask_price, p_step, adj_price):
        threshold = max(strategy_base_settings.ORDER_MIN_QTY_THRESHOLD[self.symbol],
                        float(config.SYMBOLS_ORDER_CONDITION[self.symbol].get("minQuantity", 0)))
        mean_order_size = strategy_base_settings.MEAN_ORDER_SIZE[self.symbol]
        quantity_unit = max(mean_order_size, threshold)
        start_index, end_index = self.ss.orders_num

        spec_symbol_liquidity = ss.SPEC_SYMBOL_LIQUIDITY.get(self.currency, {}).get(abs(index))
        if spec_symbol_liquidity:
            precision = int(config.SYMBOLS_ORDER_CONDITION[self.symbol]["price"])
            precision_price = round(0.1 ** precision, precision)
            quantity = random.uniform(0.1, 1.2) * spec_symbol_liquidity[0]
            p_step = precision_price * 20
        else:
            if abs(index) == 1:
                quantity = random.uniform(threshold, threshold * 3)
            elif abs(index) in list(range(2, 3)):
                quantity = random.uniform(quantity_unit * 0.06, quantity_unit * 0.08)
            else:
                quantity = random.uniform(quantity_unit * 0.5, quantity_unit * 0.8)

            if self.currency in ["USDT", "BUSD", "HUSD", "USDC"]:
                if abs(index) == 1:
                    quantity = random.uniform(1000, 8000)
                else:
                    quantity = random.uniform(quantity_unit * 25, quantity_unit * 30)
            if self.symbol == "BTC-USDT" and abs(index) > end_index:
                quantity = random.uniform(quantity * 1.8, quantity * 2)

            adj_percent = min(float(self.price_polaris.get(self.symbol, 1)), strategy_base_settings.max_adj_percent)
            if adj_percent > 1:
                quantity = quantity * 0.7
            # # 大小单 数量矫正
            big_choices = self.bigchoices_buy if index > 0 else self.bigchoices_sell
            small_choices = self.smallchoices_buy if index > 0 else self.smallchoices_sell

            if abs(index) in big_choices:
                if abs(index) == max(big_choices):
                    quantity = quantity * 5
                else:
                    quantity = quantity * 2.5
            elif abs(index) in small_choices:
                quantity = quantity * 0.3

            quantity = max(quantity, threshold) * 1.4 * random.uniform(0.9, 1.3)

            if abs(index) in big_choices + small_choices:
                # 模拟用户下整数的单
                quantity = float("%0.1e" % quantity)

        # 风控策略
        if abs(index) in [1, 2, 4] and self.currency in currency_conf_danger_currency:
            quantity = float(config.SYMBOLS_ORDER_CONDITION[self.symbol]["minQuantity"])
            quantity = random.uniform(quantity, quantity * 5)

        if (self.to_change == "hangqing") or (self.to_change == "ask" and index < 0) or (self.to_change == "bid" and index > 0):
            quantity *= self.spread_amount_weight

        p_step *= random.uniform(0.9, 1.2)
        if index < 0:
            price = ask_price + (abs(index) - 1) * p_step + adj_price
        else:
            price = bid_price - (abs(index) - 1) * p_step - adj_price

        prepared_order = {
            'symbol': self.symbol,
            'amount': quantity,
            'price': price,
            'type': "sell-limit" if index < 0 else "buy-limit"
        }

        return prepared_order

    def prepare_orders(self, bid_price, ask_price):
        """
            1、根据调整后的买卖1价格，阶梯法下单
        """
        buy_orders = []
        sell_orders = []

        avg_price = (bid_price + ask_price) / 2
        start_end_precision = strategy_base_settings.START_END_PRECISION.get(self.symbol,
                                                                             strategy_base_settings.START_END_PRECISION_COMMON)

        dangerous_level = config.SPOT_CURRENCY_CONFIG[self.currency]["dangerous_level"]

        precision_step_base = avg_price * start_end_precision / 50
        expect_nearly_step_price = precision_step_base * random.uniform(1, 1.2) * self.spread_price_weight * risk_control_c.dangerous_scaled_percent[dangerous_level]["near"]
        precision = int(config.SYMBOLS_ORDER_CONDITION[self.symbol]["price"])
        precision_price = round(0.1 ** precision, precision)
        p_step = max(expect_nearly_step_price, precision_price)
        start_index, end_index = self.ss.orders_num  # 起止档位

        adj_price = 0
        if self.currency in ["USDT", "BUSD", "HUSD", "USDC"]:
            if self.quote == "USDT":
                adj_price = 0 # precision_price
        elif self.quote in ["BTC"]:
            p_step *= 1.5

        p_step = round(p_step, precision) if precision else round(p_step)
        adj_price = round(adj_price, precision) if precision else round(adj_price)

        # 控制大单和小单
        index_seed = list(range(2, end_index - start_index + 1))
        seeds_buy = random.sample(index_seed, len(index_seed) // 2)
        seeds_sell = random.sample(index_seed, len(index_seed) // 2)
        self.bigchoices_buy = seeds_buy[:2]
        self.smallchoices_buy = seeds_buy[2:]
        self.bigchoices_sell = seeds_sell[:2]
        self.smallchoices_sell = seeds_sell[2:]

        # 拓展档位
        extend_num = self.ss.base_extend_num.get(self.symbol, 0)

        def adj_extend_orders_via_price_rate(ask_rate, bid_rate):
            """
            根据ask_rate|bid_rate 增加拓展大单
            """
            # 增加对应方向的大单的数量
            _extend_num = random.choice([1, 2, 3])
            if ask_rate > bid_rate:
                extend_seed_indexes = list(set(index_seed) - set(self.bigchoices_sell+self.smallchoices_sell))
                if len(extend_seed_indexes) > _extend_num:
                    extend_big_order_indexes = random.sample(extend_seed_indexes, _extend_num)
                else:
                    extend_big_order_indexes = extend_seed_indexes
                self.bigchoices_sell.extend(extend_big_order_indexes)
            elif ask_rate < bid_rate:
                extend_seed_indexes = list(set(index_seed) - set(self.bigchoices_buy+self.smallchoices_buy))
                if len(extend_seed_indexes) > _extend_num:
                    extend_big_order_indexes = random.sample(extend_seed_indexes, _extend_num)
                else:
                    extend_big_order_indexes = extend_seed_indexes
                self.bigchoices_buy.extend(extend_big_order_indexes)

        adj_extend_orders_via_price_rate(self.ask_rate, self.bid_rate)  # 根据ask_rate|bid_rate 增加拓展大单

        for i in range(start_index, end_index + extend_num + 1):
            buy_orders.append(self.prepare_order(i, bid_price, ask_price, p_step, adj_price))
            sell_orders.append(self.prepare_order(-i, bid_price, ask_price, p_step, adj_price))

        def adj_amount_via_price_rate(ask_rate, bid_rate):
            """
            通过ask_rate|bid_rate调整
            1.对应盘口 加权倍数
            """
            nonlocal buy_orders, sell_orders
            # 1.对应盘口 加权倍数
            if ask_rate == 1 and bid_rate == 1:
                return
            for order in buy_orders:
                order['amount'] *= bid_rate
            for order in sell_orders:
                order['amount'] *= ask_rate

            print(f'{self.symbol} 开始调整 rate：{float("%0.2e" % self.rate)} ask_rate：{ask_rate},bid_rate：{bid_rate}')

        adj_amount_via_price_rate(self.ask_rate, self.bid_rate)  # 通过ask_rate|bid_rate调整， 1.对应盘口 加权倍数

        def handle_small_big_price():
            nonlocal sell_orders
            nonlocal buy_orders
            """
            模拟用户下整数位的价格
            """
            if self.symbol.split("-")[0] in ["USDT", "BUSD", "HUSD", "USDC"]:
                return None
            sell_orders = sorted(sell_orders, key=lambda x: x['price'])
            buy_orders = sorted(buy_orders, key=lambda x: x['price'], reverse=True)

            for t in ["buy", "sell"]:
                if t == "buy":
                    t_orders = buy_orders
                    choices = self.bigchoices_buy + self.smallchoices_buy
                else:
                    t_orders = sell_orders
                    choices = self.bigchoices_sell + self.smallchoices_sell

                t_price_spread = t_orders[-1]['price'] - t_orders[0]['price']

                if t_price_spread > precision_price * 10:
                    seed_indexes = random.sample(choices, 2)
                    start_price = round(t_orders[0]['price'], precision)
                    end_price = round(t_orders[-1]['price'], precision)
                    for seed_index in seed_indexes:
                        index = seed_index - 1
                        upgrade_price = round(t_orders[index]['price'], precision - 1)

                        if start_price < upgrade_price < end_price and upgrade_price > 0:
                            last_price = t_orders[index]['price']
                            t_orders[index]['price'] = upgrade_price

        handle_small_big_price()  # 模拟用户下整数位的价格

        try:
            if self.symbol in config.USE_GEAR_SYMBOLS and self.order_data.get("bids") and self.order_data.get("asks"):
                new_buy_orders, new_sell_orders = [], []
                ask_data, bid_data = self.order_data["asks"], self.order_data["bids"]
                v_percent = global_variable.VOLUME_AJD_PERCENT.get(self.symbol, 1)
                for index, a in enumerate(ask_data[:14]):
                    diff_price_a = abs(float(a[0]) - float(ask_data[0][0]))
                    diff_price_a *= random.uniform(0.9, 1.2)
                    price_a = ask_price if index == 0 else ask_price + max(diff_price_a, precision_price * index)  # 防止因为精度问题导致单子重合
                    new_sell_orders.append({
                        'symbol': self.symbol,
                        'amount': float(a[1]) * random.uniform(0.5, 0.8) * v_percent,
                        'price': price_a,
                        'type': "sell-limit"
                    })
                for index, b in enumerate(bid_data[:14]):
                    diff_price_b = abs(float(b[0]) - float(bid_data[0][0]))
                    diff_price_b *= random.uniform(0.9, 1.2)
                    price_b = bid_price if index == 0 else bid_price - max(diff_price_b, precision_price * index)  # 防止因为精度问题导致单子重合
                    new_buy_orders.append({
                        'symbol': self.symbol,
                        'amount': float(b[1]) * random.uniform(0.5, 0.8) * v_percent,
                        'price': price_b,
                        'type': "buy-limit"
                    })
                buy_orders = new_buy_orders if len(new_buy_orders) >= len(buy_orders) else new_buy_orders + buy_orders[len(new_buy_orders):]
                sell_orders = new_sell_orders if len(new_sell_orders) >= len(sell_orders) else new_sell_orders + sell_orders[len(new_sell_orders):]
        except Exception as e:
            print(f"{self.symbol}, 近盘口near档位替换出错， error: {repr(e)}")

        update_hangqing_time = global_variable.PRICE_UPDATE_SIGNAL.get("hangqing", 0)
        auto_hangqing = False if time.time() - update_hangqing_time > 30 else True
        if auto_hangqing:
            self.logger.info(f"{self.symbol} 近盘口进入自动行情")
            buy_orders = buy_orders[:-4]
            sell_orders = sell_orders[:-4]

        #和U区5%下大单
        cash_value = config.large_order_value.get(self.symbol.split("-")[0], config.LARGE_ORDER_VALUE_DEFAULT)
        buy_amount = 0
        sell_amount = 0
        for big_order_percent_default, big_order_percent_origin in config.BIG_ORDERS.items():
            big_order_percent = big_order_percent_origin.get(self.symbol.split("-")[0], big_order_percent_default)
            # random_result = random.choice(["ask_order_use_ask1", "bid_order_use_bid1"])
            # if random_result == "ask_order_use_ask1":
            #     big_order_sell_price = ask_price * (1 + big_order_percent)
            #     big_order_buy_price = avg_price * (1 - big_order_percent)
            # else:
            #     big_order_buy_price = bid_price * (1 - big_order_percent)
            #     big_order_sell_price = avg_price * (1 + big_order_percent)

            big_order_sell_price = ask_price * (1 + big_order_percent)
            big_order_buy_price = bid_price * (1 - big_order_percent)
            symbol_flag = True
            if self.symbol.split("-")[1] in ["USDT", ]:
                buy_amount = cash_value / big_order_buy_price
                sell_amount = cash_value / big_order_sell_price
            else:
                symbol_flag = False

            if self.to_change == "hangqing":
                buy_amount *= self.spread_amount_weight
                sell_amount *= self.spread_amount_weight

            if symbol_flag:

                ask_large_order = {
                    'symbol': self.symbol,
                    'amount': random.uniform(sell_amount * 0.8, sell_amount * 1.2),
                    'price': big_order_sell_price,
                    'type': "sell-limit"
                }
                bid_large_order = {
                    'symbol': self.symbol,
                    'amount': random.uniform(buy_amount * 0.8, buy_amount * 1.2),
                    'price': big_order_buy_price,
                    'type': "buy-limit"
                }

                buy_orders.append(bid_large_order)
                sell_orders.append(ask_large_order)
        # print(f"sell-{self.symbol}", self.bigchoices_sell, self.smallchoices_sell, [x['amount'] for x in sell_orders])
        # print(f"buy-{self.symbol}", self.bigchoices_buy, self.smallchoices_buy, [x['amount'] for x in buy_orders])
        self.logger.info(f"{self.symbol}-{self.ss.NAME} bids_price:{[x['price'] for x in buy_orders]}, asks_price:{[x['price'] for x in sell_orders]}")

        return buy_orders, sell_orders


async def run(symbol, abc):
    await asyncio.sleep(random.uniform(0, 4))
    logger.remove()
    logger_ = copy.deepcopy(logger)
    logger_.add(f'./log/{symbol}_{ss.NAME}.log', rotation='100 MB', retention='1 days', compression='zip',
                enqueue=True, )
    logger_.add(sys.__stdout__)
    logger.add(sys.__stdout__)
    mmld = NearStrategyHub(symbol=symbol, abc=abc, ss=ss, logger=logger_)
    loop_time_latest = time.time()
    spend_time_list = []
    while True:
        try:
            start_time = int(time.time())
            try:
                with mmld.logger.catch(reraise=True):
                    if await maintenance_status(symbol):
                        await asyncio.sleep(ss.sleepTime - (int(time.time()) - start_time))
                        continue
                    start_loop = time.time()
                    await mmld.loop()
                    end_time = time.time()
                    spend_time = end_time - start_loop
                    spend_time_list.append(spend_time)
                    spend_time_list = spend_time_list[-60:]
                    if end_time - loop_time_latest > 20:
                        spend_time_array = np.array(spend_time_list)
                        if len(spend_time_array[spend_time_array > 1.2]) > 20 or len(spend_time_array[spend_time_array > 3]) > 5:
                            await recode_msg.recode_error_msg(str(f"非常紧急情况！！！ 现货{symbol} 单次循环时间超时严重"), 'send_telegram_important_msg_url')
                        loop_time_latest = time.time()
            except Exception as f:
                message = f"{mmld.ss.NAME} {mmld.symbol} {sys.exc_info()} 发生异常"
                logger_.error(f"run-error {message} {traceback.format_exc()}")
                await recode_msg.recode_error_msg(message, 'send_telegram_important_msg_url')

                await mmld.logger.complete()
                await asyncio.sleep(3)
                continue

            spec_sleep_time = ss.SPEC_SLEEP_TIME.get(symbol, ss.sleepTime)
            start_flash_s = time.time()
            if start_flash_s - start_time < spec_sleep_time:
                wait_time = spec_sleep_time - (start_flash_s - start_time)
                try:
                    with mmld.logger.catch(reraise=True):
                        for i in range(50):
                            if time.time() - start_flash_s > wait_time:
                                break
                            update_signal_time = global_variable.PRICE_UPDATE_SIGNAL.get(mmld.currency)
                            if update_signal_time and update_signal_time > start_flash_s:
                                logger_.info(f"{symbol} 收到信号")
                                break
                            await mmld.loop_flash()
                            end_time = time.time() - start_time
                            if end_time > spec_sleep_time:
                                break
                            else:
                                _time = spec_sleep_time - end_time
                                for _ in range(int(_time // 0.1)):
                                    update_signal_time = global_variable.PRICE_UPDATE_SIGNAL.get(mmld.currency)
                                    if update_signal_time and update_signal_time > start_flash_s:
                                        logger_.info(f"{symbol} 收到信号")
                                        break
                                    await asyncio.sleep(0.1)
                                else:
                                    await asyncio.sleep(0.1)
                                    continue
                                break
                except Exception as f:
                    print(f"近盘口闪单出现错误，{repr(f)}")
                    await mmld.logger.complete()
                # await asyncio.sleep(spec_sleep_time - (int(time.time()) - start_time))
        except BaseException:
            logger_.info(f"{traceback.format_exc()}")
