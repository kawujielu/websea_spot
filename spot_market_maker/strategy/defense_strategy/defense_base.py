import traceback
import sys
import time
import random
from libs.config_update_ser import maintenance_status
from strategy import strategy_base_settings
from strategy.defense_strategy import defense_settings as ss
import config
from strategy.strategy_base import BaseStrategyHub
import asyncio
from loguru import logger
from many_config import risk_control_c
from libs import recode_msg
import copy
from many_config import global_variable


class DefenseStrategyHub(BaseStrategyHub):
    def prepare_order(self, index, bid_price, ask_price, near_precision_step, p_step,
                      defence_to_near_min_diff, step_spread):
        threshold = strategy_base_settings.ORDER_MIN_QTY_THRESHOLD[self.symbol]
        mean_order_size = strategy_base_settings.MEAN_ORDER_SIZE[self.symbol]
        quantity_unit = max(mean_order_size, threshold)
        start_index, end_index = self.ss.orders_num

        big_choices = self.bigchoices_buy if index > 0 else self.bigchoices_sell
        small_choices = self.smallchoices_buy if index > 0 else self.smallchoices_sell

        if start_index <= abs(index) <= start_index + step_spread:
            quantity = abs(quantity_unit) * (
                    abs(index) + 1 - start_index) * random.uniform(0.1, 0.3)
        elif abs(index) in big_choices:
            index1 = start_index + 4
            quantity = abs(quantity_unit) * (
                    abs(index1) + 1 - start_index) * random.uniform(0.8, 1) * 3

        elif abs(index) in small_choices:
            index1 = start_index + 4
            quantity = abs(quantity_unit) * (
                    abs(index1) + 1 - start_index) * random.uniform(0.8, 1) / 5

        else:
            index1 = start_index + 5
            quantity = abs(quantity_unit) * (
                    abs(index1) + 1 - start_index) * random.uniform(0.8, 1)

        if (self.to_change == "hangqing") or (self.to_change == "ask" and index < 0) or (self.to_change == "bid" and index > 0):
            quantity *= self.spread_defense_amount_weight
        else:
            quantity = max(quantity, threshold)

        level_start = ss.orders_num[0]

        if index < 0:
            price = ask_price + (level_start - 2) * near_precision_step + (abs(index) - level_start + 1) * p_step
            try:
                if self.symbol in config.USE_GEAR_SYMBOLS and self.order_data.get("asks"):
                    diff_ask = abs(float(self.order_data["asks"][-1][0]) - float(self.order_data["asks"][0][0]))
                    price = ask_price + max(diff_ask, defence_to_near_min_diff) + (abs(index) - level_start + 2) * p_step
            except Exception as e:
                self.logger.info(f"{self.symbol} defence 对标计算价格 {traceback.format_exc()}")
                recode_msg.recode_error_msg(f"{self.symbol} defence 对标计算价格", "send_telegram_important_msg_url")

        else:
            price = bid_price - (level_start - 2) * near_precision_step - (abs(index) - level_start + 1) * p_step
            try:
                if self.symbol in config.USE_GEAR_SYMBOLS and self.order_data.get("bids"):
                    diff_bid = abs(float(self.order_data["bids"][0][0]) - float(self.order_data["bids"][-1][0]))
                    price = bid_price - max(diff_bid, defence_to_near_min_diff) - (abs(index) - level_start + 2) * p_step
            except Exception as e:
                self.logger.info(f"{self.symbol} defence 对标计算价格 {traceback.format_exc()}")
                recode_msg.recode_error_msg(f"{self.symbol} defence 对标计算价格", "send_telegram_important_msg_url")

        prepared_order = {
            'symbol': self.symbol,
            'amount': quantity,
            'price': price,
            'type': "sell-limit" if index < 0 else "buy-limit"
        }
        return prepared_order

    def prepare_orders(self, bid_price, ask_price):
        buy_orders = []
        sell_orders = []

        start_index, end_index = self.ss.orders_num

        avg_price = (bid_price + ask_price) / 2
        start_end_precision = strategy_base_settings.START_END_PRECISION.get(self.symbol,
                                                                             strategy_base_settings.START_END_PRECISION_COMMON)

        expect_nearly_step_price = avg_price * start_end_precision / 50 / 8
        precision = int(config.SYMBOLS_ORDER_CONDITION[self.symbol]["price"])
        precision_price = round(0.1 ** precision, precision)
        nearly_step_price = expect_nearly_step_price if expect_nearly_step_price > precision_price else precision_price

        defence_to_near_min_diff = precision_price * max(15, len(self.order_data.get("bids", [])))  # defence到near的最小价差
        precision_step_base = avg_price * (random.uniform(start_end_precision, start_end_precision + 0.01) / 50) * self.spread_price_weight  # 每步价差的基础数值

        dangerous_level = config.SPOT_CURRENCY_CONFIG[self.currency]["dangerous_level"]
        risk_control = risk_control_c.dangerous_scaled_percent[dangerous_level]
        near_precision_step = max(precision_price, precision_step_base * risk_control["near"])
        defense_precision_step = max(precision_price, precision_step_base * risk_control["defense"])
        p_step = max(defense_precision_step, nearly_step_price)

        step_spread = 4
        index_seed = [x for x in range(start_index + step_spread, end_index + 1)]
        seeds_buy = random.sample(index_seed, 5)
        seeds_sell = random.sample(index_seed, 5)
        self.bigchoices_buy = seeds_buy[:2]
        self.smallchoices_buy = seeds_buy[2:]
        self.bigchoices_sell = seeds_sell[:2]
        self.smallchoices_sell = seeds_sell[2:]

        for i in range(start_index, end_index + 1):
            buy_orders.append(self.prepare_order(i, bid_price, ask_price, near_precision_step, p_step,
                                                 defence_to_near_min_diff, step_spread))
            sell_orders.append(self.prepare_order(-i, bid_price, ask_price, near_precision_step, p_step,
                                                  defence_to_near_min_diff, step_spread))

        update_hangqing_time = global_variable.PRICE_UPDATE_SIGNAL.get("hangqing", 0)
        auto_hangqing = False if time.time() - update_hangqing_time > 30 else True
        if auto_hangqing:
            self.logger.info(f"{self.symbol} 防御盘口进入自动行情")
            buy_orders = buy_orders[:-4]
            sell_orders = sell_orders[:-4]

        def adj_amount_via_price_rate(ask_rate, bid_rate):
            """
            通过ask_rate|bid_rate调整
            1.对应盘口 加权倍数
            """
            nonlocal buy_orders, sell_orders
            # 1.对应盘口 加权倍数
            if ask_rate == 1 and bid_rate == 1:
                return
            # ll1=sum([x["amount"] for x in buy_orders])/sum([x["amount"] for x in sell_orders])
            for order in buy_orders:
                order['amount'] *= bid_rate
            for order in sell_orders:
                order['amount'] *= ask_rate
            print(f'{self.symbol} 开始调整 rate：{self.rate} ask_rate：{ask_rate},bid_rate：{bid_rate}')

        adj_amount_via_price_rate(self.ask_rate, self.bid_rate)  # 通过ask_rate|bid_rate调整， 1.对应盘口 加权倍数 2.对应增加大单的量，减小小单的量

        self.logger.info(f"{self.symbol}-{self.ss.NAME} bids_price:{[x['price'] for x in buy_orders]}, asks_price:{[x['price'] for x in sell_orders]}")

        return buy_orders, sell_orders


async def run(symbol, abc):
    await asyncio.sleep(random.uniform(0, 10))
    logger.remove()
    logger_ = copy.deepcopy(logger)
    logger_.add(f'./log/{symbol}_{ss.NAME}.log', rotation='100 MB', retention='1 days', compression='zip',
                enqueue=True, )
    logger_.add(sys.__stdout__)
    logger.add(sys.__stdout__)
    mmld = DefenseStrategyHub(symbol=symbol, abc=abc, ss=ss, logger=logger_)
    while True:
        try:
            start_time = int(time.time())
            try:
                with mmld.logger.catch(reraise=True):
                    if await maintenance_status(symbol):
                        await asyncio.sleep(ss.sleepTime - (int(time.time()) - start_time))
                        continue
                    await mmld.loop()
            except Exception as f:
                message = f"{mmld.ss.NAME} {mmld.symbol} {sys.exc_info()} 发生异常"
                logger_.error(f"run-error {message} {traceback.format_exc()}")
                await recode_msg.recode_error_msg(message, 'send_telegram_important_msg_url')

                await mmld.logger.complete()
                await asyncio.sleep(3)
                continue

            if time.time() - start_time > ss.sleepTime:
                continue
            else:
                await asyncio.sleep(ss.sleepTime - (int(time.time()) - start_time))
        except BaseException:
            logger_.info(f"{traceback.format_exc()}")
