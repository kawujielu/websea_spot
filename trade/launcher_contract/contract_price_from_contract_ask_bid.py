
# -- 不能注释，此导入为初始化
import initialization
# ---
import time
import asyncio
from ws_libs import ws_contract_ask_bid
from many_configs import global_variable
from many_configs.contract_currency_config import CONTRACT_ABC_SYMBOL_EXCHANGES_FROM_CONTRACT, \
    contract_price_trans_symbols_from_contract, contract_price_all_symbols_from_contract, \
    contract_price_ex_symbols_from_contract, CONTRACT_PRICE_SYMBOL_CONFIG
from datetime import datetime
import traceback
from loguru import logger
from libs.heartbeat import i_live_transit_station, heart_monitor_async
from libs import libs_price_async, decorator
from many_configs.base_config import EXCHANGE_MAX_SUB_DEFAULT, EXCHANGE_MAX_SUB_PER_WS
from many_configs.contract_currency_config import spec_contract_symbol_rate_mapping
from libs import recode_msg
import numpy as np
from many_configs.base_config import ExchangeCode


@decorator.monitor_handler
async def contract_ask1_bid1_2_db():
    i_live_transit_station("main_instance", frequency=6)
    for symbol in CONTRACT_ABC_SYMBOL_EXCHANGES_FROM_CONTRACT:
        for exc in CONTRACT_ABC_SYMBOL_EXCHANGES_FROM_CONTRACT[symbol]:
            i_live_transit_station("item_instance", f"{exc}{symbol}", frequency=7)

    last_data = {}
    while True:
        try:
            now_time = time.time()
            data_mappings = global_variable.G_CONTRACT_PRICE_BY_CONTRACT_ASK_BID
            send_data = []
            push_currencies = set()
            for symbol in contract_price_all_symbols_from_contract:
                try:
                    for exchange in CONTRACT_ABC_SYMBOL_EXCHANGES_FROM_CONTRACT[symbol]:
                        if not data_mappings.get(exchange, {}).get(symbol):
                            print(f"{datetime.now()} 合约买卖一价格{exchange} {symbol} 未创建")
                            continue
                        if time.time() - data_mappings[exchange][symbol]['ts'] > 5:
                            print(f"{datetime.now()} 合约买卖一价格{exchange} {symbol} 超时"
                                  f"{time.time() - data_mappings[exchange][symbol]['ts']}s")
                            # break
                        try:
                            price_ask = float(data_mappings[exchange][symbol]["price_ask"])
                            price_bid = float(data_mappings[exchange][symbol]["price_bid"])
                        except:
                            msg = f"合约保存价格 {exchange} {symbol} {data_mappings[exchange][symbol]}"
                            logger.info(msg)
                            await recode_msg.recode_error_msg(msg, 'send_telegram_important_msg_url')
                            continue

                        if np.isnan(price_ask) or np.isnan(price_bid) or not price_ask or not price_bid:
                            msg = f"合约保存价格 {exchange} {symbol} {data_mappings[exchange][symbol]}"
                            logger.info(msg)
                            await recode_msg.recode_error_msg(msg, 'send_telegram_important_msg_url')
                            continue

                        diff_percent = price_ask / price_bid
                        if price_ask / price_bid > 1.02 and symbol not in ["CRV-USDT"]:
                            _percent = diff_percent-1
                            msg = f"合约价格对标合约盘口 ：{exchange} {symbol} 价差{_percent:.2f}"
                            logger.info(f"{msg} {price_ask} {price_bid}")
                            await recode_msg.recode_error_msg(msg, 'todolist')
                            continue

                        price = (price_ask + price_bid) / 2
                        if (price and last_data.get(f"{exchange}_{symbol}") != price) or (time.time() - last_data.get(f"{exchange}_{symbol}_update", 0) > 4):
                            if exchange in [ExchangeCode.bn.value, ExchangeCode.okex.value] and last_data.get(f"{exchange}_{symbol}") and abs(price / last_data.get(f"{exchange}_{symbol}") - 1) > 0.001:
                                push_currency = symbol.split("-")[0]
                                push_currencies.add(push_currency)
                            last_data[f"{exchange}_{symbol}"] = price
                            last_data[f"{exchange}_{symbol}_update"] = int(time.time())
                            funding_rate = CONTRACT_PRICE_SYMBOL_CONFIG.get(symbol, {}).get("price_offset", 0)
                            spec_rate = spec_contract_symbol_rate_mapping.get(exchange, {}).get(symbol, ("", 1))[1]
                            funding_rate_weight_price = price * (1 + funding_rate) * spec_rate
                            print(f"{datetime.now().strftime('%d %H:%M:%S')} {exchange}-{symbol}: {price} {funding_rate} {funding_rate_weight_price}")
                            # 合约价格对标合约买卖n为加权之后价格存储为一个hash, 现货因为启动方式当前脚本只启动一个，没办法加权，所以分开
                            send_data.append({"symbol": symbol, "exchange": f"c-{exchange}", "price": funding_rate_weight_price})
                        last_update = data_mappings[exchange][symbol]['ts']
                        # 合约对标价格和通过现货对标的合约价格心跳应该保持一致，两个文件可能轮换启动
                        i_live_transit_station("item_instance", f"{exchange}{symbol}", frequency=7,
                                               last_update=last_update)
                    i_live_transit_station("main_instance", frequency=6)
                except Exception as e:
                    print(f'{datetime.now()} {symbol}合约买卖一价格获取错误', e, traceback.format_exc())
            await libs_price_async.update_contract_ask_bid_price(send_data)
            diff_save_db = time.time() - now_time
            if diff_save_db > 0.25:
                msg = f"contract_ask1_bid1_2_db 存redis 超时 {diff_save_db}"
                logger.info(msg)
                await recode_msg.recode_error_msg(msg, 'todolist')
            if push_currencies:
                await libs_price_async.publish_contract_signal({"currencies": list(push_currencies), "update_time": time.time()})
        except Exception as e:
            logger.info(f'合约价格存入redis报错 {e}, {traceback.format_exc()}')
            await recode_msg.recode_error_msg(f"合约价格存入redis报错！！！", 'depth_price')
        finally:
            await asyncio.sleep(0.071)


@decorator.monitor_handler
async def push_hangqing_2_db():
    i_live_transit_station("main_instance", frequency=1)
    hangqing_data = {}
    symbols = ["BTC-USDT", "ETH-USDT"]
    hangqing_threshold = {
        "BTC-USDT": (0.0015, 0.004),
        "ETH-USDT": (0.002, 0.005),
    }
    ex = ExchangeCode.bn.value

    for symbol in symbols:
        hangqing_data[symbol] = []

    last_send_time = 0
    while True:
        try:
            ex_data_mappings = global_variable.G_CONTRACT_PRICE_BY_CONTRACT_ASK_BID[ex]
            hangqing_send_flag = False
            for symbol in symbols:
                try:
                    if symbol not in ex_data_mappings:
                        await asyncio.sleep(0.1)
                        continue
                    price_ask = float(ex_data_mappings[symbol]["price_ask"])
                    price_bid = float(ex_data_mappings[symbol]["price_bid"])
                except:
                    msg = f"push_hangqing_2_db {symbol} {ex_data_mappings[symbol]}"
                    logger.info(msg)
                    await recode_msg.recode_error_msg(msg, 'send_telegram_important_msg_url')
                    await asyncio.sleep(0.1)
                    continue

                if np.isnan(price_ask) or np.isnan(price_bid) or not price_ask or not price_bid:
                    msg = f"push_hangqing_2_db {symbol} {ex_data_mappings[symbol]}"
                    logger.info(msg)
                    await recode_msg.recode_error_msg(msg, 'send_telegram_important_msg_url')
                    await asyncio.sleep(0.1)
                    continue

                price = (price_ask + price_bid) / 2
                if price:
                    hangqing_data[symbol].append(price)
                    hangqing_data[symbol] = hangqing_data[symbol][-100:]
                    max_data = max(hangqing_data[symbol])
                    min_data = min(hangqing_data[symbol])
                    diff_spreed = max_data / min_data - 1
                    if diff_spreed > hangqing_threshold[symbol][1]:
                        hangqing_send_flag = True
                        logger.info(f"{symbol} 行情 {diff_spreed} > {hangqing_threshold[symbol][1]}")
                        break
                    temp_data = hangqing_data[symbol][-50:]
                    max_data = max(temp_data)
                    min_data = min(temp_data)
                    diff_spreed = max_data / min_data - 1
                    if max_data / min_data - 1 > hangqing_threshold[symbol][0]:
                        hangqing_send_flag = True
                        logger.info(f"{symbol} 行情 {diff_spreed} > {hangqing_threshold[symbol][0]}")
                        break
            now_time = time.time()
            if hangqing_send_flag and now_time - last_send_time > 4:
                await libs_price_async.publish_contract_signal({"currencies": ["hangqing"], "update_time": now_time})
                last_send_time = now_time
            i_live_transit_station("main_instance", frequency=1)
        except Exception as e:
            logger.info(f'push_hangqing_2_db {e}, {traceback.format_exc()}')
            await recode_msg.recode_error_msg(f"push_hangqing_2_db报错！！！", 'depth_price')
        finally:
            await asyncio.sleep(0.1)



async def main():
    """
        如果特殊情况下，需要获取合约买卖一作为合约价格，比如币安现货维护合约正常使用，并且市场只能对标币安，那么就去对标币安合约，如果维护结束，需要先判断现货和合约是否有价差等
    """

    tasks = []
    for ex, symbols in contract_price_ex_symbols_from_contract.items():
        ex_symbol_number = len(symbols)
        symbols = list(symbols)
        part_symbol_number = EXCHANGE_MAX_SUB_PER_WS.get(ex, EXCHANGE_MAX_SUB_DEFAULT)
        for i in range(int(ex_symbol_number / part_symbol_number) + 1):
            target_ex_part_symbol = symbols[part_symbol_number * i:part_symbol_number * (i + 1)]
            global_variable.G_CONTRACT_PRICE_BY_CONTRACT_ASK_BID[ex] = {}
            tasks.append(asyncio.create_task(getattr(ws_contract_ask_bid, f'get_{ex}_depth')
                                             (contract_price_trans_symbols_from_contract[ex],
                                              target_ex_part_symbol,
                                              monitor=f"合约对标合约价格_获取价格|{ex}合约买卖价{i}"
                                              ),
                                             )
                         )

    tasks.append(asyncio.create_task(contract_ask1_bid1_2_db(monitor=f"合约对标合约价格_数据库|合约"), ))
    tasks.append(asyncio.create_task(push_hangqing_2_db(monitor=f"合约对标合约价格_行情|合约"), ))
    tasks.append(asyncio.create_task(heart_monitor_async()))

    for t in tasks:
        await t


if __name__ == '__main__':
    asyncio.run(main())
