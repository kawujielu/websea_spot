import random
import asyncio
import datetime
import time
import traceback
from decimal import Decimal
import libs
from many_configs.account_config import DEX_ACCOUNT
from libs.recode_msg import recode_error_msg
from libs.feature_utils import get_currency_exposure, in_threshold_decision
from many_configs import global_variable
from many_configs.base_config import SwapCode
from core_external.order import cancel_and_record_order, hedge_symbol
from core_external.market import best_ask_bid, get_exchange_depth_amounts
from loguru import logger
from auto_wd.wd import send_wd_signal

background_tasks = set()
background_tasks_name = set()
_alert_ts = {}
_ALERT_INTERVAL = 2 * 60


def _throttled_alert(key):
    now = time.time()
    if now - _alert_ts.get(key, 0) < _ALERT_INTERVAL:
        return False
    _alert_ts[key] = now
    return True


# TODO 是否发送，数据库写入不成功等问题。

def discard(task):
    background_tasks_name.discard(task.get_name())
    background_tasks.discard(task)


def register_task(task_name, task):
    background_tasks_name.add(task_name)
    background_tasks.add(task)
    task.add_done_callback(discard)


async def update_hedge_counter(currency, weight_price, start_hedge_time, hedge_exchange):
    # status 0 表示未对冲  1表示正在对冲 增加缺口数量
    diff_min = int((time.time() - start_hedge_time) // 60)
    if diff_min >= 10:
        exposure = await get_currency_exposure(currency)
        await recode_error_msg(f'@kawujielu_sky @TB147258 {hedge_exchange}交易所 {currency}对冲超过{diff_min}min !, 当前缺口数量 {exposure}, 价值 {int(weight_price * exposure)} U', server="dex_hedge")


async def dex_order_control_hub():
    ORDER_EXCESS_TIME = 6 * 60

    account_nonce_mapping = {}

    while True:
        await asyncio.sleep(5)


async def start_symbol_dex_hedge(currency, nonce, gas_price_step=0, ex_acc=None):
    try:
        await asyncio.sleep(5)
    except Exception:
        msg = f"{currency} {traceback.format_exc()}"
        await recode_error_msg(msg, server="dex_hedge")
        await asyncio.sleep(5)

# 第二步: 开始对冲
async def cex_symbol_hedge_hub(currency):
    order = {}  # {"bn": orderId}
    start_hedge_time = time.time()
    while True:
        try:
            currency_hedge_config = global_variable.SHARE_SYMBOL_HEDGE_CONFIG[currency]
            exchanges = currency_hedge_config["exchanges"]
            logger.info(f'currency_hedge_config:{currency_hedge_config}')
            # 交易对停止，或者停机，撤销当前订单，并记录，异常发送消息，继续循环撤单
            if (not currency_hedge_config["status"]) or (not global_variable.SERVICE_STATUS):
                order_exs = list(order.keys())
                for order_ex in order_exs:
                    orderid = order[order_ex]
                    symbol = exchanges[order_ex]["symbol"]
                    await recode_error_msg(f"{order_ex} {currency} 收到停机请求", server="spot_hedge")
                    res = await cancel_and_record_order(symbol, orderid, order_ex, currency)
                    if res == "撤单异常":
                        await recode_error_msg(f"停止{order_ex} {currency} {orderid =}撤单失败", server="spot_hedge")
                        await asyncio.sleep(3)
                        continue
                    order.pop(order_ex, None)
                break

            # 先撤单才会更新对冲缺口，再进行阈值判断
            order_exs = list(order.keys())
            for order_ex in order_exs:
                orderid = order[order_ex]
                symbol = exchanges[order_ex]["symbol"]
                res = await cancel_and_record_order(symbol, orderid, order_ex, currency)
                if res == "撤单异常":
                    await recode_error_msg(f"{order_ex} {currency} {orderid =}撤单失败", server="spot_hedge")
                else:
                    order.pop(order_ex, None)
            exposure = await get_currency_exposure(currency)

            weight_price = await libs.libs_price_async.get_weight_price(f"{currency}-USDT")
            exposure_value = abs(exposure) * weight_price
            # 时间超过阈值报警
            hedge_exchange = None
            for i_ex in exchanges:
                # 配置权重为0，该交易所不进行对冲
                if float(exchanges[i_ex]["percent"]) > 0:
                    hedge_exchange = i_ex
                    break
            await update_hedge_counter(currency, weight_price, start_hedge_time, hedge_exchange)

            # 敞口币量和敞口的市值与对应阈值比较, 不需要进行对冲，退出前撤单并记录
            tag = await in_threshold_decision(currency, weight_price)
            logger.info(f"敞口数量:{exposure} {weight_price} {exposure_value} {abs(exposure) < float(currency_hedge_config['hedge_threshold'])} {(exposure_value < currency_hedge_config['hedge_threshold_USDT'])} {tag}") # 临时增加日志
            if abs(exposure) < float(currency_hedge_config["hedge_threshold"]) and (
                    exposure_value < currency_hedge_config["hedge_threshold_USDT"]) and not(
                    await in_threshold_decision(currency, weight_price)):

                # 退出之前撤销当前订单，并记录
                order_exs = list(order.keys())
                for ex in order_exs:
                    orderid = order[ex]
                    symbol = exchanges[ex]["symbol"]
                    res = await cancel_and_record_order(symbol, orderid, ex, currency)
                    if res == "撤单异常":
                        await asyncio.sleep(3)
                        continue
                    order.pop(ex, None)
                break

            hedge_count = -exposure
            side = "SELL" if hedge_count < 0 else "BUY"
            for i_ex in exchanges:
                # 当前交易所有订单（代表撤单失败），不进行下单
                if order.get(i_ex):
                    continue
                # 配置权重为0，该交易所不进行对冲
                if float(exchanges[i_ex]["percent"]) <= 0:
                    continue

                # 判断币的买卖方向，最后根据外部交易对判断买卖方向
                cur_exchange_symbol = exchanges[i_ex]["symbol"]
                s_currency = cur_exchange_symbol.split("-")[0]

                # 判断对冲交易所是否能够进行此方向下单
                hedge_side = exchanges[i_ex]["hedge_side"].upper()
                if (hedge_side == "SELL" and side == "BUY") or (hedge_side == "BUY" and side == "SELL"):
                    continue
                cur_exchange_hedge_currency = exchanges[i_ex]["hedge_currency"]
                cur_exchange_hedge_other = exchanges[i_ex]["hedge_other"]

                if (currency not in cur_exchange_hedge_currency and cur_exchange_hedge_currency not in currency) \
                        or (cur_exchange_hedge_currency not in cur_exchange_symbol) \
                        or (cur_exchange_hedge_other not in cur_exchange_symbol) \
                        or (cur_exchange_hedge_currency == cur_exchange_hedge_other):
                    msg = f"{currency}: {cur_exchange_hedge_currency} {cur_exchange_symbol} 对冲配置错误"
                    await recode_error_msg(msg, server="spot_hedge")
                    continue

                # 判断外部交易对买卖方向
                if side == "SELL":
                    if s_currency == cur_exchange_hedge_currency:
                        symbol_side = "SELL"
                    else:
                        symbol_side = "BUY"
                else:
                    if s_currency == cur_exchange_hedge_currency:
                        symbol_side = "BUY"
                    else:
                        symbol_side = "SELL"

                # 判断下单价格
                price = await best_ask_bid(cur_exchange_symbol, i_ex)
                logger.info(f'best_ask_bid:{cur_exchange_symbol} {i_ex} {price}')
                add_price = None
                avg_price = None
                hedge_style = exchanges[i_ex]["hedge_style"]
                if symbol_side == "SELL":
                    if hedge_style == "maker":
                        add_price = float(price["asks"])
                    elif hedge_style == "avg":
                        add_price = (float(price["asks"]) + float(price["bids"])) / 2
                    elif hedge_style == "taker":
                        add_price = float(price["bids"])
                else:
                    if hedge_style == "maker":
                        add_price = float(price["bids"])
                    elif hedge_style == "avg":
                        add_price = (float(price["asks"]) + float(price["bids"])) / 2
                    elif hedge_style == "taker":
                        add_price = float(price["asks"])

                # 计算对冲币相对于quote的价格
                if s_currency == cur_exchange_hedge_currency:
                    hedge_currency_price = add_price
                else:
                    hedge_currency_price = 1 / add_price

                # 根据spec_symbol_rate_mapping 计算abc数量和abc价格
                pr_amount = libs.spec_symbol_rate_mapping.get(i_ex, {}).get(cur_exchange_symbol, 1)
                currency_price = hedge_currency_price * pr_amount

                # min(对冲出口价值计算数量；敞口数量;钱包数量)
                add_amount = min(
                    float(currency_hedge_config["hedge_qty_usdt_per"]) / currency_price,
                    abs(hedge_count)) * float(exchanges[i_ex]["percent"])

                if global_variable.FASTER_HEDGE:
                    logger.info(f"{currency} 进入均价对冲计算逻辑")
                    # TODO 这部分逻辑没有考虑mongo交易对和对冲交易对是否一样，quote不一样，价格相比较就是错误的，但是实际的情况都是一样的。
                    # abc_position = round(global_variable.ABC_POSITIONS.get(currency, 0), 8)
                    # last_abc_position = round(
                    #     global_variable.ABC_ASSET_AVG_PRICE.get(currency, {}).get('abc_position', 0), 8)
                    #
                    # if not global_variable.ABC_ASSET_AVG_PRICE.get(currency) or (
                    #         global_variable.ABC_ASSET_AVG_PRICE.get(currency) and last_abc_position != abc_position):
                    #     avg_price = await abc_asset_position_instance.asset_position_process_avg_price(
                    #         cur_exchange_symbol, exposure)
                    #     global_variable.ABC_ASSET_AVG_PRICE[currency] = {'abc_position': abc_position,
                    #                                                      'avg_price': avg_price}
                    # else:
                    #     avg_price = global_variable.ABC_ASSET_AVG_PRICE[currency]['avg_price']
                    # TODO 需要转换成对冲交易对的价格进行比较，这个均价的价格是U
                    avg_price = global_variable.ABC_POSITIONS_AVG_PRICE.get(currency, 0)
                    avg_price = min(max(avg_price, currency_price*0.9), currency_price*1.1)
                    hedge_side_avg_price = avg_price / pr_amount
                    depth_amount = await get_exchange_depth_amounts(
                        exchange=i_ex, symbol=cur_exchange_symbol, price=hedge_side_avg_price, side=side)
                    depth_amount = depth_amount / pr_amount
                    if depth_amount:
                        depth_amount *= 0.9
                        logger.info(f"{currency} 均价对冲 {add_price=} {add_amount=} {depth_amount=} {hedge_count=} {avg_price=}")
                        add_amount = min(depth_amount, abs(hedge_count))
                        add_price = hedge_side_avg_price

                # 通过对冲交易所币的买卖方向进行判断需要的钱包余额最大买入卖出量
                wallet_exchange_currency = global_variable.WALLET_EXCHANGE_CURRENCY.get(i_ex, {})
                logger.info(f'{i_ex} : {wallet_exchange_currency} {side}')

                if side == "SELL":
                    wallet_currency = float(wallet_exchange_currency.get(cur_exchange_hedge_currency, 0)) / pr_amount
                    can_sell_amount = wallet_currency
                    logger.info(f"转账前条件判断:{currency} {add_amount=} {can_sell_amount=}")
                    if add_amount > can_sell_amount:
                        need_quantity = exposure * float(exchanges[i_ex]['percent'])
                        need_currency = currency
                        await send_wd_signal(need_currency, need_quantity, 1, i_ex)
                        diff = add_amount - can_sell_amount
                        add_amount = can_sell_amount * 0.95
                        if _throttled_alert(f"insufficient_hedge:{i_ex}:{currency}"):
                            asyncio.create_task(
                                recode_error_msg(f">>>>>>>>>{i_ex} 需要对冲 {need_quantity} {currency}  资金不够对冲，请联系资产 @TB147258", server="spot_hedge"))
                else:
                    wallet_currency = float(wallet_exchange_currency.get(exchanges[i_ex]["hedge_other"], 0))
                    can_buy_amount = wallet_currency / currency_price
                    if add_amount > can_buy_amount:
                        need_quantity = int(exposure_value * float(exchanges[i_ex]['percent']))
                        need_currency = exchanges[i_ex]['hedge_other']
                        await send_wd_signal(need_currency, need_quantity, 1, i_ex)
                        diff = add_amount - can_buy_amount
                        add_amount = can_buy_amount * 0.95
                        if _throttled_alert(f"insufficient_hedge:{i_ex}:{need_currency}"):
                            asyncio.create_task(
                                recode_error_msg(f"️‍>>>>>>>>>{i_ex} 需要 {need_quantity} {need_currency} 资金不够，请联系资产 @TB147258", server="spot_hedge"))

                if add_amount * currency_price > 20 or currency_hedge_config.get("force_all") == "yes":
                    add_amount = add_amount * pr_amount
                    # 防止精度导致无法下单
                    logger.info(
                        f"{i_ex}: {cur_exchange_symbol}-{symbol_side}-amount: {add_amount}-price: {add_price}")

                    # 计算均价
                    orderid = await hedge_symbol(cur_exchange_symbol, symbol_side, add_amount, add_price, i_ex, currency, avg_price=avg_price)
                    if orderid:
                        order[i_ex] = orderid

            sleep_time = currency_hedge_config["sleep_time"]
            await asyncio.sleep(max(random.uniform(sleep_time - 2, sleep_time + 2), 2))
        except Exception:
            msg = f"{currency} {traceback.format_exc()}"
            await recode_error_msg(msg, server="spot_hedge")
            await asyncio.sleep(5)

# 第一步: 检测是否需要对冲
async def exposure_detection_and_hedge():
    service_status_start = True
    service_status_end = True
    wallet_alert_last_update = 0

    while True:
        try:
            if not global_variable.SERVICE_STATUS:
                if service_status_start:
                    await recode_error_msg(f"cex所有币种收到停机请求", server="spot_hedge")
                    service_status_start = False
                if (not background_tasks) and service_status_end:
                    await recode_error_msg(f"cex所有币种停机完成", server="spot_hedge")
                    service_status_end = False
                await asyncio.sleep(5)
                continue

            service_status_start = True
            service_status_end = True

            for currency in global_variable.SHARE_SYMBOL_HEDGE_CONFIG:
                try:
                    weight_price = await libs.libs_price_async.get_weight_price(f"{currency}-USDT")
                except Exception:
                    msg = f"{traceback.format_exc()}"
                    await recode_error_msg(f"{currency} get price error !", server="spot_hedge")
                    continue
                currency_hedge_config = global_variable.SHARE_SYMBOL_HEDGE_CONFIG[currency]
                exposure = await get_currency_exposure(currency)

                all_exes = currency_hedge_config['exchanges'].keys()
                dex_exes = [ex for ex in all_exes if
                            ex.split("_")[0] in DEX_ACCOUNT and currency_hedge_config['exchanges'][ex]['percent'] == 1]
                dex_chain_name = dex_exes[0] if dex_exes else None
                # 允许去中心对冲对冲开启时可直接进入去检测订单(在阈值不满足)，为了能够检测到未检查完但是在阈值预警内的订单
                exceeded_threshold = abs(exposure) >= float(currency_hedge_config["hedge_threshold"]) or (
                        abs(exposure) * weight_price) >= currency_hedge_config["hedge_threshold_USDT"] or (
                    await in_threshold_decision(currency, weight_price))

                if exceeded_threshold and not dex_chain_name and currency_hedge_config["status"]:
                    # 中心对冲和去中心不允许同时执行
                    if currency not in background_tasks_name:
                        logger.info(f'币种: {currency} 开始在中心化交易所对冲！！！')
                        task = asyncio.create_task(cex_symbol_hedge_hub(currency), name=currency)
                        register_task(currency, task)
            try:
                logger.info(global_variable.WALLET_EXCHANGE_CURRENCY)
                msg_list = []
                for ex, wallet_info in global_variable.WALLET_EXCHANGE_CURRENCY.items():
                    if ex in ['bn', 'gate']:
                        v_usdt = wallet_info.get("USDT", 0)
                        if ex in ["gate"] and float(v_usdt) < 3000:
                            msg = f">>>>>>>>>>>>>>>>>> -------gate usdt 少于 3000u 【联系资产】补充资金 ! @TB147258"
                            logger.info(msg)
                            msg_list.append(msg)
                        if ex in ["bn"] and float(v_usdt) < 8000:
                            msg = f">>>>>>>>>>>>>>>>>> -------bn usdt 少于 8000u 【联系资产】补充资金 ! @TB147258"
                            await send_wd_signal("USDT", 20000, 1, ex)
                            logger.info(msg)
                            msg_list.append(msg)
                        if time.time() - wallet_alert_last_update > 1 * 60 and msg_list:
                            msg = " \n ".join(msg_list)
                            await recode_error_msg(msg, server="spot_hedge")
                            wallet_alert_last_update = time.time()
            except Exception:
                msg = f"{traceback.format_exc()}"
                await recode_error_msg(msg, server="spot_hedge")

            logger.info(f'当前处于中心化交易所对冲队列的币种数量: {len(background_tasks_name)}')
            await asyncio.sleep(5)
        except Exception:
            msg = f"{traceback.format_exc()}"
            await recode_error_msg(msg, server="spot_hedge")
            await asyncio.sleep(1)
