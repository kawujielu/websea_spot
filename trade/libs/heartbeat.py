import time
import ujson
import traceback

import libs
from libs import libs_price_async, libs_price, currency_feature
from many_configs.spot_currency_config import NORMAL_FOLLOW_CURRENCY
from many_configs import global_variable
import asyncio
import sys
import os
import hashlib
from loguru import logger


HEART_BEAT_KEY = "HEART_BEAT"
SEND_INTERVAL_TIME = 2


def register_monitor(task_name):
    if not task_name:
        print(f"register_monitor args error")
        return

    # 根据运行脚本与参数，生成自定义ID，避免启动同一套程序，不同运行参数，心跳之间相互覆盖，导致报警闪烁。
    # 避免不同脚本，但是心跳关联，相互覆盖，导致报警闪烁
    sys.argv[0] = sys.argv[0].split(os.path.sep)[-1]   # 避免本地和服务器路径不同，导致心跳报警异常闪烁
    pid_str = ''
    for i in sys.argv:
        if i == ">>":
            break
        pid_str += i
    self_pid = str(hashlib.md5(pid_str.encode()).hexdigest())[-8:]
    item_server_name = task_name.split('|')[0]
    item_server_sub_name_pre = f"{task_name.split('|')[1]}"

    main_server_name = item_server_name.split('_')[0]
    main_server_sub_name = f"{item_server_name.split('_')[1]}{task_name.split('|')[1]}"

    monitor_dict = {}
    for s in [("item_instance", item_server_name), ("main_instance", main_server_name)]:
        server_name_pid = f"{s[1]}#{self_pid}"
        if server_name_pid not in global_variable.ZEUS_MONITOR:
            global_variable.ZEUS_MONITOR[server_name_pid] = {
                "server": server_name_pid, "index": 4, "container": {}, "sos": ""
            }
        monitor_dict[s[0]] = global_variable.ZEUS_MONITOR[server_name_pid]
    monitor_dict["main_server_sub_name"] = main_server_sub_name
    monitor_dict["item_server_sub_name_pre"] = item_server_sub_name_pre
    monitor_dict["task_name"] = task_name

    global_variable.monitor.set(monitor_dict)


def heartbeat_server_parse(thread_name):
    """
    {main_server}_{item_sub_server}|{sub_server}

    """
    try:
        item_server_name = thread_name.split("|")[0]
        item_sub_server = item_server_name.split("_")[1] if len(item_server_name.split("_")) >= 2 else "None_item_sub_server"
        sub_server = thread_name.split("|")[1] if len(thread_name.split("|")) >= 2 else "None_sub_server"
    except:
        item_sub_server, sub_server = "", ""
    return item_sub_server, sub_server


def heart_monitor():
    while True:
        try:
            all_values = collector_heartbeat_data()
            if all_values:
                libs_price.redis_db_heart_beat.execute_command("HSET", HEART_BEAT_KEY, *all_values)
        except Exception as e:
            print(f"heart_monitor {traceback.format_exc()} {repr(e)}")
        finally:
            time.sleep(SEND_INTERVAL_TIME)


async def heart_monitor_async():
    while True:
        try:
            all_values = collector_heartbeat_data()
            if all_values:
                await libs_price_async.redis_db_heart_beat.async_connection.execute_command("HSET", HEART_BEAT_KEY, *all_values)
        except Exception as e:
            print(f"heart_monitor {traceback.format_exc()} {repr(e)}")
        finally:
            await asyncio.sleep(SEND_INTERVAL_TIME)


def collector_heartbeat_data():
    all_values = []
    for server_key in global_variable.ZEUS_MONITOR:
        ts_servers = global_variable.ZEUS_MONITOR[server_key]
        if ts_servers["container"]:
            error_msg = ""
            frequencys = []
            for k, ser in ts_servers["container"].items():
                diff = time.time() - ser["last_update"]
                if diff > ser["frequency"]:
                    error_msg = f"{k}超时{diff}s、{error_msg}"
                frequencys.append(ser["frequency"])
            min_frequency = min(frequencys)
            if error_msg:
                all_values.append(ts_servers["server"])
                all_values.append(ujson.dumps({'send_time': 0,
                                               'frequency': min_frequency,
                                               "index": ts_servers["index"],
                                               "sos": ts_servers["sos"] if ts_servers["sos"] else "**",
                                               "note": error_msg}))
            else:
                all_values.append(ts_servers["server"])
                all_values.append(ujson.dumps({'send_time': time.time(),
                                               'frequency': max(frequencys),
                                               "index": ts_servers["index"],
                                               "sos": ts_servers["sos"] if ts_servers["sos"] else "**",
                                               }))
    return all_values


def i_live_transit_station(server_key, item_sub_server=None, frequency=10, heart_type=0,
                           last_update=None, sos="**", extend="",
                           ):
    """
    server_key 主服务
    sub_server 子服务 或者 主服务下的交易对
    frequency 心跳间隔时长-秒
    heart_type 心跳类型
        0 : 默认逻辑使用传入的frequency
        1 : 下单检测
        2 : 外部买卖一推送
        3 : 买卖一推送
    last_update 发出心跳时间（消息推送设置为外部交易所推送的时间）
    sos 处理人员
    extend 搭配sub_server使用，用于区别具体哪个服务比如现货或者合约，usdt区还是btc区等
    """
    update_frequency = transit_station_frequency(heart_type, item_sub_server, frequency)

    monitor_instance = global_variable.monitor.get()
    server = monitor_instance.get(server_key)
    if server_key == "main_instance":
        sub_server = monitor_instance.get("main_server_sub_name")
    else:
        sub_server = f'{monitor_instance.get("item_server_sub_name_pre")}-{item_sub_server}'
    try:
        sub_server = f"{sub_server}|{extend}"
        server["container"][sub_server] = {"frequency": update_frequency,
                                           "last_update": time.time() if last_update is None else last_update}
        server["server"] = f"{server['server']}"
        server["sos"] = sos
    except Exception as e:
        print(f"i_live_transit_station {traceback.format_exc()} {repr(e)}")


def transit_station_frequency(heart_type, sub_server, frequency):
    # 下单检测 或者 市场价格
    if heart_type == 1:
        max_frequency = frequency * 60
        symbol = sub_server
        currency, part = symbol.split("-")

        level = currency_feature.currency_dangerous_level(currency)
        if level > 1:
            monitor_instance = global_variable.monitor.get()
            task_name = monitor_instance.get("task_name", "None")
            if task_name not in global_variable.AUTO_ADJ_FREQUENCY:
                global_variable.AUTO_ADJ_FREQUENCY[task_name] = {}
            market_price_auto = global_variable.AUTO_ADJ_FREQUENCY[task_name]
            if currency not in market_price_auto:
                market_price_auto[currency] = {"diff_list": [0], "latest_rev": time.time()}
            else:
                now = time.time()
                diff_time = int(now - market_price_auto[currency]["latest_rev"])
                market_price_auto[currency]["latest_rev"] = now
                if diff_time > 10:
                    market_price_auto[currency]["diff_list"].append(diff_time)
                    market_price_auto[currency]["diff_list"] = market_price_auto[currency]["diff_list"][-50:]
            update_frequency = min(max(max(market_price_auto[currency]["diff_list"]), frequency), max_frequency)
            if update_frequency == max_frequency:
                logger.info(f'{currency} - {market_price_auto[currency]["diff_list"]} - '
                            f'{max(market_price_auto[currency]["diff_list"])}')
        else:
            update_frequency = frequency
    # 买卖n档位，如果某个交易对经常超时，那么需要评估风险减少相应的流动性，增加数据接受时间间隔的容忍度
    elif heart_type == 2:
        update_frequency = frequency
    # abc的现货合约买卖一推送
    elif heart_type == 3:
        update_frequency = 60 * 5
    else:
        update_frequency = frequency
    return update_frequency

