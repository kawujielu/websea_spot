
# -- 不能注释，此导入为初始化
import initialization
# ---
from ujson import JSONDecodeError
import os
import time
import requests
import threading
import logging
from libs.senddd import send_telegram
from libs import libs_config, libs_price
from logging.handlers import TimedRotatingFileHandler
from many_configs.base_config import EXCHANGE_ACTIVE
from many_configs import global_variable
from libs.heartbeat import i_live_transit_station, heart_monitor

RATIO = {"ETH": 0.0026, "BTC": 0.0026, "EOS": 0.0026, "BCH": 0.006, "BSV": 0.006, "LTC": 0.006,
         "XMR": 0.006, "UFO": 0.006}  # 只检测这些交易对，超过设置比率报警

GET_PRICE_FREQUENCY = 8

price_symbols_pair = libs_config.price_symbols_pair
api_url = {'zb_symbols': "http://api.zb.today/data/v1/allTicker", "hb_symbols": "https://api.huobi.com/market/tickers",
           "okex_symbols": "https://www.okex.com/api/spot/v3/instruments/ticker",
           "bn_symbols": "https://api.binance.com/api/v3/ticker/price", }


def create_log():
    log_fmt = "%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s"
    formatter = logging.Formatter(log_fmt)

    log_file_handler = TimedRotatingFileHandler(filename="log/price_check.log", when="D", interval=1, backupCount=2)
    log_file_handler.setFormatter(formatter)

    logging.basicConfig(level=logging.INFO, filename='/dev/null')  # 不打印到控制台
    log = logging.getLogger()
    log.addHandler(log_file_handler)
    return log


def reset_data(ex_name, result):
    """
    根据不同数据来源，统一数据格式为{ex_name:{symbol:price,...}}
    :param ex_name: 交易所名字，格式为name_symbols
    :param result: 从接口返回的数据
    :return:统一后的数据格式{ex_name:{symbol:price,...}}
    """
    all_data = {}
    all_data[ex_name] = {}
    if ex_name == "hb_symbols":
        for data in result['data']:
            symbol = data.get("symbol")
            price = data.get("close")
            all_data[ex_name][symbol] = price
    elif ex_name == "okex_symbols":
        for data in result:
            symbol = data.get("instrument_id")
            price = data.get("last")
            all_data[ex_name][symbol] = price
    elif ex_name == "bn_symbols":
        for data in result:
            symbol = data.get("symbol")
            price = data.get("price")
            all_data[ex_name][symbol] = price
    elif ex_name == "zb_symbols":
        for data in result:
            symbol = data
            price = result.get(symbol).get("last")
            all_data[ex_name][symbol] = price
    return all_data


def write_redis(exchange, all_data, source_data):
    """
    将获取到的价格写入redis数据库
    :param exchange: 交易所名字，格式为name_symbols
    :param all_data: 接口数据，格式为{ex_name:{symbol:price,...}}
    :return:
    """
    no_data_symbols = []
    useful_data = {}
    useful_data[exchange] = {}
    redis_ex = exchange.split("_")[0]
    symbols = price_symbols_pair[exchange]
    send_data = []
    for symbol in symbols:
        if exchange == "zb_symbols":
            # todo: 币种转换
            pass
        elif exchange == "bn_symbols":
            symbol_new = symbol.replace('-', '')
        if symbol_new in all_data[exchange]:
            price = all_data.get(exchange).get(symbol_new)
            useful_data[exchange][symbol] = all_data[exchange][symbol_new]
            send_data.append({"symbol": symbol, "exchange": redis_ex, "price": price})
            i_live_transit_station("main_instance", frequency=GET_PRICE_FREQUENCY + 5)
            i_live_transit_station("item_instance", f"{symbol}", frequency=GET_PRICE_FREQUENCY + 5)
        else:
            no_data_symbols.append(symbol_new)
    libs_price.rs_update_price(send_data)
    if no_data_symbols:
        send_telegram(f"A 从{exchange}中接收到的数据没有{no_data_symbols}的价格", 'price_check', libs_config.DEBUG)
        updateLog.warning(f"从{exchange}中接收到的数据没有{no_data_symbols}的价格，原始数据为{source_data}")
    return useful_data


def compare_redis(exchange, all_data):
    """
    获取到的价格与redis中的价格对比，查过指定价差的报警
    :param exchange: 交易所名字，name_symbols
    :param all_data: 接口数据，格式为{ex_name:{symbol:price,...}}
    :return:
    """
    redis_ex = exchange.split("_")[0]
    for symbol in all_data[exchange]:
        symbol_first = symbol.split('-')[0]
        price = float(all_data[exchange][symbol])
        price_redis_str = libs_price.redis_db_market_price.hget(symbol, redis_ex)
        if price_redis_str:
            price_redis = float(price_redis_str)
            if symbol_first in RATIO:
                ratio = RATIO[symbol_first]
                spread = round((price_redis - price) / price, 4)
                if abs(spread) <= ratio:
                    updateLog.info(
                        f"{exchange} {symbol} redis:{price_redis} my:{price},差价为{spread * 100}%，在{ratio * 100}%范围内，正常。")
                else:
                    send_telegram(
                        f"A {exchange} {symbol} redis:{price_redis} my:{price},差价为{spread * 100}%，大于±{ratio * 100}%。",
                        'price_check', libs_config.DEBUG)
                    updateLog.warning(
                        f"{exchange} {symbol} redis:{price_redis} my:{price},差价为{spread * 100}%，大于±{ratio * 100}%。")
            else:
                spread = round((price_redis - price) / price, 4)
                updateLog.info(f"{exchange} {symbol} redis:{price_redis} my:{price},差价为{spread * 100}%")
        else:
            updateLog.info(f"{exchange} {symbol} redis:None my:{price}")


def get_data(ex_name, url):
    """
    访问接口，整理数据
    :param ex_name:交易所名字，name_symbols
    :param url: 接口地址
    :return: 整理后的数据，格式为{ex_name:{symbol:price,...}}
    """
    try:
        source_data_unjson = requests.get(url, timeout=1, verify=False)
        source_data = source_data_unjson.json()
    except Exception as e:
        if not (issubclass(requests.exceptions.ConnectTimeout, type(e)) or issubclass(requests.exceptions.ReadTimeout,
                                                                                      type(e))):
            if "source_data_unjson" in locals().keys():
                updateLog.error(
                    f"发现新的错误,{e},type:{type(e)},状态码为:{source_data_unjson.status_code},返回数据为:{source_data_unjson.text}")
            else:
                updateLog.error(f"发现新的错误,请求URL出错，{e},type:{type(e)}")
        raise e
    all_data = reset_data(ex_name, source_data)
    return all_data, source_data


def main(ex_name, url):
    """
    主程序，先获取数据、再写入redis、核查
    :param ex_name: 交易所名字，name_symbols
    :param url: 接口地址
    :return:
    """
    count_timeout = 0
    i_live_transit_station("main_instance", frequency=GET_PRICE_FREQUENCY + 5)
    [i_live_transit_station("item_instance", f"{symbol}", frequency=GET_PRICE_FREQUENCY + 5) for symbol in price_symbols_pair[ex_name]]

    while True:
        source_data = "****没数据就挂了"
        try:
            if count_timeout > 2:
                send_telegram(f"A {ex_name}连续请求超时{count_timeout}次", 'price_check', libs_config.DEBUG)
                updateLog.error(f"A {ex_name}连续请求超时{count_timeout}次")
            start = time.time()
            all_data, source_data = get_data(ex_name, url)
            useful_data = write_redis(ex_name, all_data, source_data)
            compare_redis(ex_name, useful_data)
            updateLog.info(f"{ex_name}完成，耗时{time.time() - start}秒")
            count_timeout = 0
        except requests.exceptions.ConnectTimeout as e:
            count_timeout += 1
            updateLog.error(f"A {ex_name} requests.exceptions.ConnectTimeout，{e}。")
            continue
        except requests.exceptions.ReadTimeout as e:
            count_timeout += 1
            updateLog.error(f"A {ex_name} requests.exceptions.ReadTimeout，{e}。")
            continue
        except JSONDecodeError as e:
            count_timeout += 1
            updateLog.error(f"A {ex_name} json.decoder.JSONDecodeError，{e}。")
            continue

        except BaseException as e:
            send_telegram(f"A {ex_name}获取数据失败，{e}。", 'price_check', libs_config.DEBUG)
            if "source_data" in locals().keys():
                updateLog.error(f"A {ex_name}获取数据失败，{e},type:{type(e)},接收数据为{source_data}")
            else:
                updateLog.error(f"A {ex_name}获取数据失败，{e},type:{type(e)}")
            continue
        finally:
            time.sleep(GET_PRICE_FREQUENCY)


def UFO():
    symbol = "UFO-USDT"
    url_bkex = "https://api.bkex.co/v2/q/depth?symbol=UFO_USDT&depth=5"
    url_zb = "http://api.zb.today/data/v1/depth?market=ufo_usdt&size=5"
    count_timeout = 0
    while True:
        for url in [url_bkex, url_zb]:
            try:
                if count_timeout > 2:
                    send_telegram(f"A {ex_name}连续请求超时{count_timeout}次", 'price_check', libs_config.DEBUG)
                    updateLog.error(f"A {ex_name}连续请求超时{count_timeout}次")
                res = requests.get(url, verify=False).json()
                count_timeout = 0
                if "bkex" in url:
                    exchange = "bkex_depth"
                    bid1 = res["data"]["ask"][0]
                    ask1 = res["data"]["bid"][0]
                elif "zb" in url:
                    exchange = "zb_depth"
                    ask1 = res["asks"][-1]
                    bid1 = res["bids"][0]

                bid1 = [float(i) for i in bid1]
                ask1 = [float(i) for i in ask1]
                price = (bid1[0] + ask1[0]) / 2
                print(price, exchange)
                libs_price.rs_update_price([{"symbol": symbol, "exchange": exchange, "price": price}])
                i_live_transit_station("ZEUS_MONITOR_RESTFUL_PRICE", exchange, GET_PRICE_FREQUENCY + 5, sos="齐峥")
                if exchange == "zb_depth":  # 比对价格
                    price_redis = float(libs_price.redis_db_market_price.hget(symbol, exchange))
                    spread = round((price_redis - price) / price, 4)
                    ratio = RATIO["UFO"]
                    if abs(spread) <= ratio:
                        updateLog.info(
                            f"{exchange} {symbol} redis:{price_redis} my:{price},差价为{spread * 100}%，在{ratio * 100}%范围内，正常。")
                    else:
                        send_telegram(
                            f"A {exchange} {symbol} redis:{price_redis} my:{price},差价为{spread * 100}%，大于±{ratio * 100}%。",
                            'price_check', libs_config.DEBUG)
                        updateLog.warning(
                            f"{exchange} {symbol} redis:{price_redis} my:{price},差价为{spread * 100}%，大于±{ratio * 100}%。")
            except requests.exceptions.ConnectTimeout as e:
                count_timeout += 1
                updateLog.error(f"A {exchange} requests.exceptions.ConnectTimeout，{e}。")
                continue
            except requests.exceptions.ReadTimeout as e:
                count_timeout += 1
                updateLog.error(f"A {exchange} requests.exceptions.ReadTimeout，{e}。")
                continue
            except JSONDecodeError as e:
                count_timeout += 1
                updateLog.error(f"A {exchange} json.decoder.JSONDecodeError，{e}。")
                continue
            except BaseException as e:
                send_telegram(f"A 出现没有预料到的异常，error:{e}", 'price_check', libs_config.DEBUG)
                updateLog.error(f"A {exchange} 没有预料到的异常，{e}。")
                continue
        time.sleep(GET_PRICE_FREQUENCY)


if __name__ == '__main__':
    logPath = os.path.join(os.getcwd(), 'log')
    if not os.path.exists(logPath):
        os.mkdir(logPath)
    updateLog = create_log()
    trade_thread_list = []
    for ex_name in api_url:
        no_symbol_ex = ex_name.split("_")[0]
        if EXCHANGE_ACTIVE.get(no_symbol_ex):
            url = api_url[ex_name]
            trade_thread_list.append(threading.Thread(target=main, args=(ex_name, url), kwargs={"monitor": f"价格服务_中心化|{ex_name}-restful价格存入redis"}))
    trade_thread_list.append(threading.Thread(target=UFO, args=()))
    trade_thread_list.append(threading.Thread(target=heart_monitor, args=()))
    for t in trade_thread_list:
        t.start()
    for t in trade_thread_list:
        t.join()
