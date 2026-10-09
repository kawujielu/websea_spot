
import traceback
import sys
import random
from libs.config_update_ser import maintenance_status
from strategy import strategy_base_settings
from strategy.strategy_base import BaseStrategyHub
from strategy.depth_strategy import depth_settings as ss
import config
import time
import asyncio
from loguru import logger
from strategy.defense_strategy import defense_settings as defense_ss
from many_config import risk_control_c
from libs import recode_msg
import copy
from many_config import global_variable


class DepthStrategyHub(BaseStrategyHub):
    def prepare_order(self, index, bid_price, ask_price, near_precision_step, defense_precision_step, p_step):
        threshold = strategy_base_settings.ORDER_MIN_QTY_THRESHOLD[self.symbol]
        mean_order_size = strategy_base_settings.MEAN_ORDER_SIZE[self.symbol]
        start_index, end_index = self.ss.orders_num
        quantity_unit = max(mean_order_size, threshold)
        if abs(index) < end_index / 3:
            quantity = max(random.uniform(quantity_unit * 1.8, quantity_unit * 2.3), threshold)
        elif abs(index) < end_index / 3 * 2:
            quantity = max(random.uniform(quantity_unit * 1.2, quantity_unit * 1.5), threshold)
        else:
            quantity = max(random.uniform(quantity_unit * 0.4, quantity_unit * 0.6), threshold)

        quantity = max(quantity, threshold)

        # 当 quantity=threshold的时候，做一个随机的处理
        if quantity == threshold:
            quantity = quantity*random.uniform(0.73, 1.33)

        if index < 0:
            price = ask_price + (defense_ss.orders_num[0]-2) * near_precision_step + (defense_ss.orders_num[1] - defense_ss.orders_num[0] + 1) * defense_precision_step + (abs(index) - start_index + 1) * p_step
        else:
            price = bid_price - (defense_ss.orders_num[0]-2) * near_precision_step - (defense_ss.orders_num[1] - defense_ss.orders_num[0] + 1) * defense_precision_step - (abs(index) - start_index + 1) * p_step

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
        start_index, end_index = self.ss.orders_num
        all_order_num = end_index + 1

        avg_price = (bid_price + ask_price) / 2
        start_end_precision = strategy_base_settings.START_END_PRECISION.get(self.symbol,
                                                                             strategy_base_settings.START_END_PRECISION_COMMON)

        expect_nearly_step_price = avg_price * start_end_precision / 50 / 8
        precision = int(config.SYMBOLS_ORDER_CONDITION[self.symbol]["price"])
        precision_price = round(0.1 ** precision, precision)
        nearly_step_price = expect_nearly_step_price if expect_nearly_step_price > precision_price else precision_price

        precision_step_base = avg_price * random.uniform(start_end_precision, start_end_precision + 0.01) / 50 * self.spread_price_weight  # 每步价差的基础数值

        dangerous_level = config.SPOT_CURRENCY_CONFIG[self.currency]["dangerous_level"]
        risk_control = risk_control_c.dangerous_scaled_percent[dangerous_level]
        near_precision_step = max(precision_price, precision_step_base * risk_control["near"])  # 加权后每步价差的数值
        defense_precision_step = max(precision_price, precision_step_base * risk_control["defense"])
        precision_step = max(precision_price, precision_step_base * risk_control["depth"])
        p_step = max(precision_step, nearly_step_price)

        if nearly_step_price / precision_price < 2:
            all_order_num = all_order_num + 12
            self.logger.info(f"{self.symbol} 深度增加档位")
        update_hangqing_time = global_variable.PRICE_UPDATE_SIGNAL.get("hangqing", 0)
        auto_hangqing = False if time.time() - update_hangqing_time > 30 else True
        if auto_hangqing:
            all_order_num = start_index + 4
        for i in range(start_index, all_order_num):
            buy_orders.append(self.prepare_order(i, bid_price, ask_price, near_precision_step,
                                                 defense_precision_step, p_step))
            sell_orders.append(self.prepare_order(-i, bid_price, ask_price, near_precision_step,
                                                  defense_precision_step, p_step))

        self.logger.info(f"{self.symbol}-{self.ss.NAME} bids_price:{[x['price'] for x in buy_orders]}, "
                         f"asks_price:{[x['price'] for x in sell_orders]}")

        return buy_orders, sell_orders


async def run(symbol, abc):
    await asyncio.sleep(random.uniform(0, 10))
    logger.remove()
    logger_ = copy.deepcopy(logger)
    logger_.add(f'./log/{symbol}_{ss.NAME}.log', rotation='100 MB', retention='1 days', compression='zip',
                enqueue=True, )
    logger_.add(sys.__stdout__)
    logger.add(sys.__stdout__)
    mmld = DepthStrategyHub(symbol=symbol, abc=abc, ss=ss, logger=logger_)
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

                # 日志记录报错信息
                await mmld.logger.complete()
                await asyncio.sleep(3)

            if time.time() - start_time > ss.sleepTime:
                continue
            else:
                await asyncio.sleep(ss.sleepTime - (int(time.time()) - start_time))
        except BaseException:
            logger_.info(f"{traceback.format_exc()}")
