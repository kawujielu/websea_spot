# -- 不能注释，此导入为初始化
import initialization
# ---
import asyncio
import sys
from many_configs import global_variable
from many_configs.spot_currency_config import (price_market_ex_symbols, price_depth_ex_symbols,
                                               price_depth_ex_abc_symbols, price_trans_symbols, spec_symbol_rate_mapping)
from many_configs.contract_currency_config import contract_price_ex_symbols, contract_price_trans_symbols
from many_configs.base_config import EXCHANGE_ACTIVE, ExchangeCode, EXCHANGE_MAX_SUB_DEFAULT, EXCHANGE_MAX_SUB_PER_WS
from ws_libs.funding_rate import get_funding_rate, funding_rate_fetch
from ws_libs import ws_ask_bid_center
from libs import libs_price_async, decorator
from libs.heartbeat import heart_monitor_async, i_live_transit_station
from time import time
from loguru import logger
from traceback import format_exc
from libs import recode_msg
input_exs = sys.argv[2]
exs = input_exs.split(",")

heartbeat_ask_bid_pair = {}
ask_bid_pair = {}
# 可能合约上线的交易对在现货中没有上线，需要订阅现货合约中所有交易对
all_ex = list(set(list(price_market_ex_symbols.keys()) + list(price_depth_ex_symbols.keys()) + list(contract_price_ex_symbols.keys())))
for ex in all_ex:
    ask_bid_pair[ex] = list(price_market_ex_symbols.get(ex, set()) | price_depth_ex_symbols.get(ex, set()) | contract_price_ex_symbols.get(ex, set()))


busd_usdt_config = {}


class ExchangeDataParse(object):
    @staticmethod
    async def get_weight_price_n(data, n):
        try:
            ask_all = [float(d[0]) for d in data["asks"]]
            ask_1 = ask_all[0]
            len_ask_n = len(ask_all)
            bid_all = [float(d[0]) for d in data["bids"]]
            bid_1 = bid_all[0]
            len_bid_n = len(bid_all)

            nn = min([n, len_ask_n, len_bid_n])
            price_weight_n = (sum(ask_all[:nn]) + sum(bid_all[:nn])) / (nn * 2)

            return ask_1, bid_1, price_weight_n
        except:
            logger.error(f"{data =}\n{format_exc()}")
            await recode_msg.recode_error_msg(f"get_weight_price_n计算前买卖n均价错误！{data} ", 'depth_price')

            return None, None, None

    @classmethod
    async def bn_data_parse(cls, data, symbol, n=1):
        """
        data : 交易所ws订阅数据
        symbol: ws订阅交易对（外部）
        需要对接转换数据，特殊处理订阅BUSD交易对
        """
        try:
            ask_1, bid_1, price_weight_n = await cls.get_weight_price_n(data, n)
            if symbol[-4:] == "busd":
                if time() - busd_usdt_config.get("latest_update", 0) > 10 or (not busd_usdt_config.get("price")):
                    price = await libs_price_async.get_weight_price('BUSD-USDT')
                    if price:
                        busd_usdt_config["price"] = float(price)
                        busd_usdt_config["latest_update"] = time()
                ask_1 *= busd_usdt_config["price"]
                bid_1 *= busd_usdt_config["price"]
                price_weight_n *= busd_usdt_config["price"]
            return ask_1, bid_1, price_weight_n
        except:
            logger.error(f"{symbol =} {data =}\n{format_exc()}")
            return None, None, None

    @classmethod
    async def hb_data_parse(cls, data, symbol, n=1):
        try:
            return await cls.get_weight_price_n(data, n)
        except:
            logger.error(f"{symbol =} {data =}\n{format_exc()}")
            return None, None, None

    @classmethod
    async def okex_data_parse(cls, data, symbol, n=1):
        try:
            return await cls.get_weight_price_n(data, n)
        except:
            logger.error(f"{symbol =} {data =}\n{format_exc()}")
            return None, None, None

    @classmethod
    async def gate_data_parse(cls, data, symbol, n=1):
        try:
            return await cls.get_weight_price_n(data, n)
        except:
            logger.error(f"{symbol =} {data =}\n{format_exc()}")
            return None, None, None

    @classmethod
    async def mxc_data_parse(cls, data, symbol, n=1):
        try:
            new_data = {"asks": [[i["price"], i["quantity"]] for i in data["asks"]],
                        "bids": [[i["price"], i["quantity"]] for i in data["bids"]]}
            return await cls.get_weight_price_n(new_data, n)
        except:
            logger.error(f"{symbol =} {data =}\n{format_exc()}")
            return None, None, None

    @classmethod
    async def kucoin_data_parse(cls, data, symbol, n=1):
        try:
            return await cls.get_weight_price_n(data, n)
        except:
            logger.error(f"{symbol =} {data =}\n{format_exc()}")
            return None, None, None

    @classmethod
    async def bitget_data_parse(cls, data, symbol, n=1):
        try:
            return await cls.get_weight_price_n(data, n)
        except:
            logger.error(f"{symbol =} {data =}\n{format_exc()}")
            return None, None, None

    @classmethod
    async def kraken_data_parse(cls, data, symbol, n=1):
        try:
            return await cls.get_weight_price_n(data, n)
        except:
            logger.error(f"{symbol =} {data =}\n{format_exc()}")
            return None, None, None

    @classmethod
    async def bn_ws_symbol(cls, symbol):
        return symbol.replace("-", "").lower()

    @classmethod
    async def hb_ws_symbol(cls, symbol):
        return symbol.replace("-", "").lower()

    @classmethod
    async def okex_ws_symbol(cls, symbol):
        return symbol

    @classmethod
    async def gate_ws_symbol(cls, symbol):
        return symbol.replace("-", "_")

    @classmethod
    async def kucoin_ws_symbol(cls, symbol):
        return symbol

    @classmethod
    async def mxc_ws_symbol(cls, symbol):
        return symbol.replace("-", "")

    @classmethod
    async def bitget_ws_symbol(cls, symbol):
        return symbol.replace("-", "")


async def distribution_data(symbol, exchange, ask, bid, mid_price_list, ask_bid_price_list):
    if ask and bid:
        abc_symbol = price_trans_symbols[exchange][symbol]
        spec_rate = spec_symbol_rate_mapping.get(exchange, {}).get(abc_symbol, ("", 1))
        ask *= spec_rate[1]
        bid *= spec_rate[1]
        if abc_symbol in price_depth_ex_abc_symbols.get(exchange, []):
            mid_price = (ask + bid) / 2
            mid_price_list.append({"symbol": abc_symbol, "exchange": f"{exchange}_depth", "price": mid_price})
        ask_bid_price_list.append(
            {"symbol": abc_symbol, "exchange": exchange, "ask1": str(ask), "bid1": str(bid)})
    else:
        logger.warning(f"{exchange} {symbol} {ask =} {bid =}")
        await recode_msg.recode_error_msg(f"{exchange} {symbol} {ask =}  {bid =} 盘口存在无数据，请检查", 'depth_price')


@decorator.monitor_handler
async def price_2_db():
    i_live_transit_station("main_instance", frequency=0.3)
    latest_update = time()
    monitor_s = []
    last_data = {}
    while True:
        try:
            now_time = time()
            data_mappings = global_variable.G_SYMBOL_GEAR20
            exchanges = list(data_mappings.keys())
            push_currencies = set()

            for exchange in exchanges:
                if not data_mappings[exchange]:
                    continue
                ask_bid_price_list = []
                mid_price_list = []
                symbol_data_mappers = list(data_mappings[exchange].keys())
                for symbol in symbol_data_mappers:
                    if symbol not in price_trans_symbols.get(exchange, []):
                        continue
                    data_parse_function = getattr(ExchangeDataParse, f"{exchange}_data_parse")
                    ask, bid, _ = await data_parse_function(data_mappings[exchange][symbol], symbol, 1)
                    await distribution_data(symbol, exchange, ask, bid, mid_price_list, ask_bid_price_list)
                    if exchange in [ExchangeCode.bn.value] and ask and bid:
                        abc_symbol = price_trans_symbols[exchange][symbol]
                        mid_p = (ask + bid) / 2
                        p_threshold = 0.00008 if abc_symbol in ["SOL-USDT"] else 0.001
                        if last_data.get(f"{exchange}_{abc_symbol}") and abs(mid_p / last_data.get(f"{exchange}_{abc_symbol}") - 1) > p_threshold:
                            push_currency = abc_symbol.split("-")[0]
                            push_currencies.add(push_currency)
                            logger.warning(f"{exchange} {abc_symbol} 触发行情")
                        last_data[f"{exchange}_{abc_symbol}"] = mid_p

                # 循环完一个交易所进行IO切换，让给ws获取数据
                if ask_bid_price_list:
                    # await libs_price_async.rs_update_ask_bid(ask_bid_price_list)
                    asyncio.create_task(libs_price_async.rs_update_ask_bid(ask_bid_price_list))
                if mid_price_list:
                    await libs_price_async.rs_update_price(mid_price_list)
                if push_currencies:
                    await libs_price_async.publish_contract_signal(
                        {"currencies": list(push_currencies), "update_time": time()})
                i_live_transit_station("main_instance", frequency=0.3)

                if now_time - latest_update > 5:
                    monitor_s.append(f"{exchange}: {len(ask_bid_price_list)}- {len(mid_price_list)}")
            if monitor_s:
                logger.info(f"{monitor_s}")
                latest_update = now_time
                monitor_s = []
            diff_save_db = time() - now_time
            if diff_save_db > 0.3:
                await recode_msg.recode_error_msg(f"price_2_db 存redis 超时 {diff_save_db}", 'todolist')
        except:
            msg = f"现货价格存入redis报错 {format_exc()}"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'depth_price')
        finally:
            await asyncio.sleep(0.17)


@decorator.monitor_handler
async def symbol_gear20_2_db():
    gear20_exchanges = [ExchangeCode.bn.value,  ExchangeCode.gate.value]
    open_ex = set(gear20_exchanges) & set(exs)
    i_live_transit_station("main_instance", frequency=8)
    # item_instance 不进行初始化，属于买卖一子集，不是所有交易对都有订阅
    while True:
        try:
            now_time = time()
            data_mappings = global_variable.G_SYMBOL_GEAR20
            send_data = []
            for exchange in open_ex:

                # 如果现货中没有这个交易所，发送心跳
                if not price_trans_symbols.get(exchange):
                    i_live_transit_station("main_instance", frequency=8)
                    continue
                symbol_data_mappers = list(data_mappings.get(exchange, {}).keys())
                for symbol in symbol_data_mappers:
                    if symbol not in price_trans_symbols[exchange]:
                        continue
                    asks = data_mappings[exchange][symbol]["asks"][:20]
                    bids = data_mappings[exchange][symbol]["bids"][:20]
                    symbol = price_trans_symbols[exchange][symbol]

                    if asks and bids:
                        spec_rate = spec_symbol_rate_mapping.get(exchange, {}).get(symbol, ("", 1))[1]
                        if spec_rate != 1:
                            asks = [[float(i[0]) * spec_rate, float(i[1]) / spec_rate] for i in asks]
                            bids = [[float(i[0]) * spec_rate, float(i[1]) / spec_rate] for i in bids]

                        send_data.append({"symbol": symbol, "exchange": exchange, "asks": str(asks), "bids": str(bids)})
                        i_live_transit_station("main_instance", frequency=8)
                logger.info(f"{exchange =} {len(symbol_data_mappers)}")
            await libs_price_async.rs_update_gear(send_data)
            diff_save_db = time() - now_time
            if diff_save_db > 0.2:
                await recode_msg.recode_error_msg(f"symbol_gear20_2_db 存redis 超时 {diff_save_db}", 'todolist')
        except Exception as e:
            msg = f'档位信息存入redis报错{e} {format_exc()}'
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'depth_price')
        finally:
            await asyncio.sleep(5)


@decorator.monitor_handler
async def contract_price_2_db():
    open_ex = set(contract_price_ex_symbols.keys()) & set(exs)
    open_sy = set()
    for exchange in open_ex:
        open_sy.update(contract_price_ex_symbols[exchange])
    if open_sy:
        i_live_transit_station("main_instance", frequency=0.2)
    # item_instance 不进行初始化，属于买卖一子集，不是所有交易对都有订阅
    latest_update = time()
    monitor_s = []
    while True:
        try:
            now_time = time()
            times_str = []
            data_mappings = global_variable.G_SYMBOL_GEAR20
            for exchange in open_ex:
                send_data = []
                for sy in open_sy:
                    # sy 外部交易所交易对形式
                    # wsy 外部交易所ws返回交易对形式
                    # symbol 对应abc 交易对形式
                    if sy not in contract_price_ex_symbols.get(exchange, []):
                        continue
                    symbols_parse_function = getattr(ExchangeDataParse, f"{exchange}_ws_symbol")
                    wsy = await symbols_parse_function(sy)
                    if data := data_mappings[exchange].get(wsy):
                        data_parse_function = getattr(ExchangeDataParse, f"{exchange}_data_parse")
                        ask_1, bid_1, weight_price = await data_parse_function(data, wsy, 3)
                        if ask_1 and bid_1 and weight_price:
                            diff_percent = ask_1 / bid_1
                            if diff_percent > 1.02:
                                _percent = diff_percent - 1
                                msg = f"合约价格对标现货盘口 {exchange} {sy} 价差{_percent:.2f}"
                                logger.info(f"{msg} {data}")
                                await recode_msg.recode_error_msg(msg, 'todolist')
                                continue
                            symbol = contract_price_trans_symbols[exchange][wsy]
                            spec_rate = spec_symbol_rate_mapping.get(exchange, {}).get(symbol, ("", 1))
                            weight_price *= spec_rate[1]
                            funding_rate = await get_funding_rate(symbol)
                            funding_rate_weight_price = weight_price * (1 + funding_rate)
                            # logger.info(f"{sy} {weight_price =} {funding_rate_weight_price =}")
                            send_data.append({"symbol": symbol, "exchange": exchange, "price": funding_rate_weight_price})
                            i_live_transit_station("main_instance", frequency=0.2)
                time1 = time()
                await libs_price_async.update_contract_ask_bid_price(send_data)
                times_str.append(f"{exchange}-{time()-now_time}-{time()-time1}")

                if now_time - latest_update > 5:
                    monitor_s.append(f"{exchange}: {len(send_data)}")
            if monitor_s:
                logger.info(f"{monitor_s}")
                latest_update = now_time
                monitor_s = []
            diff_save_db = time() - now_time
            if diff_save_db > 0.2:
                logger.info(f"contract_price_2_db 存redis 超时 {times_str} - {diff_save_db}")
                await recode_msg.recode_error_msg(f"contract_price_2_db 存redis 超时 {diff_save_db}", 'todolist')
        except Exception as e:
            msg = f'合约价格存入redis报错{e} {format_exc()}'
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'depth_price')
        finally:
            await asyncio.sleep(0.1)


async def main(exs):
    tasks = []
    for ex in exs:
        if ex not in EXCHANGE_ACTIVE:
            raise Exception(f"{ex} 不在EXCHANGE_ACTIVE中")
        global_variable.G_SYMBOL_GEAR20[ex] = {}
        target_ex_symbols = ask_bid_pair.get(ex)
        if not target_ex_symbols:
            continue
        heartbeat_ask_bid_pair[ex] = target_ex_symbols
        # loguru.logger.info(f'{ex} depth symbols {target_ex_symbols}')
        ex_symbol_number = len(target_ex_symbols)
        part_symbol_number = EXCHANGE_MAX_SUB_PER_WS.get(ex, EXCHANGE_MAX_SUB_DEFAULT)

        trans_symbols = price_trans_symbols.get(ex, {}) | contract_price_trans_symbols.get(ex, {})
        for i in range(int(ex_symbol_number / part_symbol_number) + 1):
            target_ex_part_symbol = target_ex_symbols[part_symbol_number * i:part_symbol_number * (i + 1)]
            if not target_ex_part_symbol:
                continue
            if not hasattr(ws_ask_bid_center, f"get_{ex}_depth"):
                continue
            spot_ask_bid_function = getattr(ws_ask_bid_center, f"get_{ex}_depth")
            tasks.append(asyncio.create_task(spot_ask_bid_function(trans_symbols , target_ex_part_symbol,
                         monitor=f"价格服务_中心化|{ex}现货买卖一订阅服务{i}")))

    # 不能提到上面写，保证G_SYMBOL_GEAR20已经被初始化
    tasks.append(asyncio.create_task(heart_monitor_async()))
    tasks.append(asyncio.create_task(price_2_db(monitor="价格服务_中心化|现货买卖一存redis")))
    tasks.append(asyncio.create_task(symbol_gear20_2_db(monitor="价格服务_中心化|现货二十档存redis")))
    tasks.append(asyncio.create_task(contract_price_2_db(monitor="价格服务_中心化|合约买卖n存redis")))
    tasks.append(asyncio.create_task(funding_rate_fetch(monitor="价格服务_中心化|资金费率")))

    for i in tasks:
        await i


if __name__ == '__main__':
    asyncio.run(main(exs))
