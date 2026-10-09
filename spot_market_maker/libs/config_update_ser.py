import asyncio
import copy
import time
import traceback
from datetime import datetime, timezone
import json
from config import (currency_conf_danger_currency, price_rate_configs)
from libs import libs_price_async
from many_config import global_variable
from strategy import strategy_base_settings
import config
from loguru import logger

config_maintenance = {}
config_update_time = {}
config_special_symbols = {}


async def maintenance_status(symbol=None):
    update_time = config_update_time.get("MAINTENANCE_UPDATE", 0)
    time_now = time.time()
    if time_now - update_time > 60:
        config_update_time["MAINTENANCE_UPDATE"] = time_now
        config_maintenance.update(await libs_price_async.redis_db_control.async_connection.hgetall("maintenance_status"))
        config_special_symbols.update(await libs_price_async.redis_db_control.async_connection.hgetall("symbols_status"))
    start_time = config_maintenance.get("start_time", 0)
    end_time = config_maintenance.get("end_time", 0)
    is_active = config_maintenance.get("is_active", "")
    if start_time and end_time and is_active == "is_active":
        start_time = int(datetime.timestamp(
            datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc).astimezone(tz=None)))
        end_time = int(datetime.timestamp(
            datetime.strptime(end_time, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc).astimezone(tz=None)))
        if start_time <= time_now <= end_time:
            logger.info("当前处于系统维护中........")
            return True

    if symbol in config_special_symbols:
        time_period = config_special_symbols.get(symbol, "0|0")
        try:
            start_time = int(datetime.timestamp(
                datetime.strptime(time_period.split("|")[0], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc).astimezone(tz=None)))
            end_time = int(datetime.timestamp(
                datetime.strptime(time_period.split("|")[1], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc).astimezone(tz=None)))
        except (Exception, BaseException) as e:
            logger.info(f"maintenance_status exception {symbol}, {traceback.format_exc()}")
            return False

        if start_time <= time_now <= end_time:
            logger.info(f"{symbol} 处于系统维护中........")
            return True

    return False


async def update_price_percent():
    update_time = config_update_time.get("PRICE_PERCENT_UPDATE", 0)
    time_now = time.time()
    if time_now - update_time > 60 * 1:
        config_update_time["PRICE_PERCENT_UPDATE"] = time_now
        redis_info = await libs_price_async.redis_db_control.async_connection.hgetall("price_percent")
        ask_bid_percent_spec_org = copy.deepcopy(strategy_base_settings.ASK_BID_PERCENT_SPEC_ORG)
        for r in redis_info:
            if r.endswith('_PRICE'):
                ask_bid_percent_spec_org[r] = min(max(0.0, float(redis_info[r])), 200)
            else:
                ask_bid_percent_spec_org[r] = min(max(0.0, float(redis_info[r])), 1)
        strategy_base_settings.ASK_BID_PERCENT_SPEC.update(ask_bid_percent_spec_org)
        for key in list(strategy_base_settings.ASK_BID_PERCENT_SPEC.keys()):
            if key not in ask_bid_percent_spec_org:
                del strategy_base_settings.ASK_BID_PERCENT_SPEC[key]


async def update_price_percent_via_hedge(symbol):
    """
    hedge_cny:对冲缺口阈值折合人民币
    scaled_percent：买卖一价差单边偏移量百分比
    spread_percent：档位价差倍数
    amount_percent：近盘口深度倍数
    defense_amount_percent： 防御盘口深度倍数
    # 通过对冲池量矫正价差,
    如果没获取到内存中的值。获取新的值。并计算当前的对冲量适合调整价差为多少偏移量合适
    如果获取到内存中的值，判断上次更新时间和当前时间是否相差1分钟，
        如果相差大于一分钟：
            重新获取新的值
        否则：
            获取内存中的上一次的更新的加权系数
        {'BTC': {'amounts': -0.0001763570522883292,
                'amounts_as_AQ': -39.520994640990516,
                 'avg_AQ_price': 108675.28403878243,
                 'consequent_hedging_hours': 0.0,
                 'hedged_currencies': 'BTC',
                 'hedging_states': 0,
                 'is_alertings': 0,
                 'thresholds': -0.8924727420975108,
                 'thresholds_as_AQ': -200000.0}, }

    :param redis_hedge_db symbol:
    :return: adj_weight
    """
    time_now = time.time()
    currency = symbol.split("-")[0]
    quote = symbol.split("-")[1]

    if time_now - global_variable.currency_hedge_scaled_percent['last_update_time'] > 2:
        try:
            global_variable.currency_hedge_scaled_percent['last_update_time'] = time_now

            logger.info(f'-----------------更新对冲配置-----------------{datetime.now()}')
            hedge_data = await libs_price_async.redis_db_control.async_connection.hgetall("update_price_percent_via_hedge")
            hangqing_data = await libs_price_async.redis_db_control.async_connection.hgetall("spot_hangqing")
            hedge_data = {k: json.loads(v) for k, v in hedge_data.items()}
            hangqing_data = {k: json.loads(v) for k, v in hangqing_data.items()}
            global_variable.currency_hedge_scaled_percent['last_time_hedge_data'] = hedge_data
            global_variable.currency_hangqing_scaled_percent['last_time_hangqing_config'] = hangqing_data
        except BaseException as e:
            logger.info(f"{traceback.format_exc()}")

    def fetch_currency_hedge_data(c):
        # 通过对冲修改对应配置
        hedge_adj = {
            "scaled_percent": 0, "spread_percent": 1, "amount_percent": 1, "defense_amount_percent": 1, "to_change": ""
        }
        try:
            currency_threshold_l = config.SPOT_CURRENCY_CONFIG[c]["hedge_threshold"]
            currency_hedge_scaled = global_variable.currency_hedge_scaled_percent[currency_threshold_l]  # 单独的币种阈值的配置
            last_time_hedge_data = global_variable.currency_hedge_scaled_percent['last_time_hedge_data']  # 整体的上一次对冲文件的配置

            amounts_as_AQ = abs(last_time_hedge_data[c]['amounts_as_AQ'])
            thresholds_as_AQ = abs(last_time_hedge_data[c]['thresholds_as_AQ'])

            # 对冲行为
            if int(last_time_hedge_data[c]['amounts_as_AQ']) > 0:
                to_change = "bid"
            elif int(last_time_hedge_data[c]['amounts_as_AQ']) < 0:
                to_change = "ask"
            else:
                to_change = ""
            hedge_adj["to_change"] = to_change
            # 币种在收税币种或者币种不在收税币种并且对冲缺口大于对冲阈值
            # amounts_as_AQ：对冲缺口
            # thresholds_as_AQ：对冲阈值
            if c in currency_conf_danger_currency or (c not in currency_conf_danger_currency and amounts_as_AQ > thresholds_as_AQ):
                for scaled in currency_hedge_scaled:
                    if amounts_as_AQ >= scaled["hedge_cny"]:
                        hedge_adj["scaled_percent"] = float(scaled['scaled_percent'])
                        hedge_adj["spread_percent"] = max(float(scaled['spread_percent']), 1)
                        hedge_adj["amount_percent"] = min(float(scaled['amount_percent']), 1)
                        hedge_adj["defense_amount_percent"] = min(float(scaled['defense_amount_percent']), 1)
                        hedge_adj["has_change"] = True
                        logger.info(f"{symbol}  对冲缺口折合AQ: {amounts_as_AQ} 对冲阈值折合AQ: {thresholds_as_AQ} '防御盘口深度倍数': {scaled}")
                        break
        except BaseException as e:
            logger.info(f'{symbol} 未配置对冲配置，已使用默认值 - {traceback.format_exc()}')
        return hedge_adj

    def fetch_currency_hangqing_data(c):
        # 通过行情判断修改对应配置
        try:
            last_time_hangqing_config = global_variable.currency_hangqing_scaled_percent['last_time_hangqing_config']  # 整体的上一次对冲文件的配置
            if not last_time_hangqing_config.get(c):
                return
            hangqing = last_time_hangqing_config[c]['hangqing']
            trigger_date = last_time_hangqing_config[c]['trigger_date']
            if hangqing:
                currency_hangqing_scaled = copy.deepcopy(global_variable.currency_hangqing_scaled_percent[c])  # 单独的币种阈值的配置
                currency_hangqing_scaled['to_change'] = "hangqing"
                logger.info(f'{symbol} 行情判断生效，触发时间 {trigger_date},修改配置 currency_hangqing_scaled ==> {currency_hangqing_scaled}')
                return currency_hangqing_scaled
        except BaseException as e:
            logger.info(f"{symbol} 获取行情配置失败 {traceback.format_exc()}")

    update_config_via_hedge = fetch_currency_hedge_data(currency)
    update_config_via_hangqing = fetch_currency_hangqing_data(currency)
    if update_config_via_hangqing:
        update_config_via_hedge.update(update_config_via_hangqing)
    return update_config_via_hedge


async def update_config_precisions():
    """
    更新 config 精度数据
    """
    try:
        db_precisions = await libs_price_async.get_precision_config()
        if not db_precisions:
            return
        config.SYMBOLS_ORDER_CONDITION.update(db_precisions)
    except Exception as e:
        logger.info(f'{datetime.now()}-----------------更新最新精度[失败]-----------------{traceback.format_exc()}')


async def update_volume_via_price(symbol, price_change_percent):
    """
    根据A网K线获取，判断近盘口，买卖盘的增减倍数
    """
    ask_rate, bid_rate = 1, 1
    if not price_change_percent:
        return ask_rate, bid_rate
    try:
        for item in price_rate_configs:
            if abs(price_change_percent) > item['rate'] and price_change_percent < 0:  # 跌
                ask_rate, bid_rate = item['max_rate'], item['min_rate']
            elif abs(price_change_percent) > item['rate'] and price_change_percent > 0:  # 涨
                ask_rate, bid_rate = item['min_rate'], item['max_rate']
    except Exception as e:
        logger.info(f"获取远程的买卖加权倍数失败{symbol},{traceback.format_exc()}")
        ask_rate, bid_rate = 1, 1
    finally:
        # print("----------rate,ask_rate, bid_rate----------", price_change_percent, ask_rate, bid_rate)
        return ask_rate, bid_rate


async def update_price_percent_to_max(currency, ask_bid_percent):
    await libs_price_async.redis_db_control.async_connection.hset("price_percent", currency, ask_bid_percent * 2)
    await libs_price_async.redis_db_adj.async_connection.hset("auto_adj_percent", currency, f"{ask_bid_percent * 2}_{datetime.now()}")
    await libs_price_async.redis_db_control.async_connection.hset("trade_volume_percent", currency, 0.1)
    strategy_base_settings.ASK_BID_PERCENT_SPEC[currency] = ask_bid_percent


async def update_volume_percent():
    update_time = config_update_time.get("VOLUME_PERCENT_UPDATE", 0)
    time_now = time.time()
    if time_now - update_time > 60 * 1:
        config_update_time["VOLUME_PERCENT_UPDATE"] = time_now
        redis_info = await libs_price_async.redis_db_control.async_connection.hgetall("volume_percent")
        mean_order_size_org = copy.deepcopy(strategy_base_settings.MEAN_ORDER_SIZE_ORG)
        order_min_qty_threshold_org = copy.deepcopy(strategy_base_settings.ORDER_MIN_QTY_THRESHOLD_ORG)
        for r in redis_info:
            r_percent = min(max(0.000001, float(redis_info[r])), 100.0)
            global_variable.VOLUME_AJD_PERCENT[r] = r_percent

            mean_order_size_org[r] = strategy_base_settings.MEAN_ORDER_SIZE_ORG.get(r, 0) * r_percent
            order_min_qty_threshold_org[r] = strategy_base_settings.ORDER_MIN_QTY_THRESHOLD_ORG.get(r, 0) * r_percent
        strategy_base_settings.MEAN_ORDER_SIZE.update(mean_order_size_org)
        strategy_base_settings.ORDER_MIN_QTY_THRESHOLD.update(order_min_qty_threshold_org)

        for key in list(strategy_base_settings.MEAN_ORDER_SIZE.keys()):
            if key not in mean_order_size_org:
                del strategy_base_settings.MEAN_ORDER_SIZE[key]

        for key in list(strategy_base_settings.ORDER_MIN_QTY_THRESHOLD.keys()):
            if key not in order_min_qty_threshold_org:
                del strategy_base_settings.ORDER_MIN_QTY_THRESHOLD[key]


if __name__ == "__main__":
    async def main():
        while True:
            await update_volume_via_price("BTC-USDT", 1)
            await asyncio.sleep(3)

    asyncio.run(main())
