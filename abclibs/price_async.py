
import ssl
import time
import threading
import asyncio
from load import load_remote
from aredis import StrictRedis
import json


try:
    from . import config as libs_config
except:
    LIBS_HOST = "10.0.209.181"
    libs_config = load_remote.urllib_model(f"server@{LIBS_HOST}", "/home/server/abclibs/config.py")

USDT_AQ_PRICE = None
USDT_AQ_UPDATE = 0

LATEST_SYMBOL_PRICE = {}
LATEST_SYMBOL_DB_PRICE = {}
LATEST_SYMBOL_ASK_BID_DB_PRICE = {}
LATEST_SYMBOL_GEAR = {}
SYMBOLS_PRECISION_UPDATETIME = {}
SYMBOLS_PRECISION = {}
CONTRACT_SYMBOLS_PRECISION_UPDATETIME = {}
CONTRACT_SYMBOLS_PRECISION = {}


class RedisAsync(object):
    @property
    def async_connection(self):
        session_name = threading.current_thread().name
        protocol_ssl = {} if libs_config.DEBUG else {"ssl": True, "ssl_context": ssl._create_unverified_context()}

        if not self._async_connection.get(session_name):
            self._async_connection[session_name] = StrictRedis(host=self.redis_config["host"],
                                                               db=self.redis_config["db"],
                                                               port=self.redis_config["port"],
                                                               password=self.redis_config["password"],
                                                               timeout=3, connect_timeout=3,
                                                               encoding='utf-8',
                                                               decode_responses=True,
                                                               **protocol_ssl)

        return self._async_connection[session_name]

    @property
    def async_pubsub(self):
        session_name = threading.current_thread().name
        if not self._async_pubsub.get(session_name):
            self._async_pubsub[session_name] = self.async_connection.pubsub()
        return self._async_pubsub[session_name]

    def __init__(self, redis_config):
        self.redis_config = redis_config
        self._async_connection = {}
        self._async_pubsub = {}


redis_db_market_price = RedisAsync(libs_config.RS_CONF_MARKET_PRICE)
redis_db_market_price_2 = RedisAsync(libs_config.RS_CONF_MARKET_PRICE_2)
redis_db_askbid_price = RedisAsync(libs_config.RS_CONF_ASKBID_PRICE)
redis_db_askbid_price_2 = RedisAsync(libs_config.RS_CONF_ASKBID_PRICE_2)
redis_db_gears = RedisAsync(libs_config.RS_CONF_GEAR)
redis_db_contract_price = RedisAsync(libs_config.RS_CONF_CONTRACT_PRICE)
redis_db_contract_price_2 = RedisAsync(libs_config.RS_CONF_CONTRACT_PRICE_2)
redis_db_control = RedisAsync(libs_config.RS_CONF_CONTROL)
redis_db_node = RedisAsync(libs_config.RS_CONF_NODE)
redis_db_vol = RedisAsync(libs_config.RS_CONF_VOL)
redis_db_heart_beat = RedisAsync(libs_config.RS_CONF_HEART_BEAT)
redis_db_adj = RedisAsync(libs_config.RS_CONF_ADJ)


# ------------------------------------------ 现货 ------------------------------------------


async def usdt_aq_otc(rs_instance):
    return 7
    global USDT_AQ_PRICE, USDT_AQ_UPDATE
    # 如果本地缓存大于10s，去redis更新本地缓存
    # 如果usdt_aq_price为初始值，去redis更新本地缓存
    if (time.time() - USDT_AQ_UPDATE > libs_config.CACHE_TIME) or (not USDT_AQ_PRICE):
        rs_usdt_aq_price = await rs_instance.async_connection.hmget("hb_otc_usdt_aq", "price", "update")
        if rs_usdt_aq_price and rs_usdt_aq_price[0] and rs_usdt_aq_price[1]:
            price = float(rs_usdt_aq_price[0])
            update = int(rs_usdt_aq_price[1])
            if time.time() - update < libs_config.MAX_VALID_TIME:
                USDT_AQ_PRICE = price
                USDT_AQ_UPDATE = int(time.time())
                return USDT_AQ_PRICE
            else:
                return None
        return None
    elif (time.time() - USDT_AQ_UPDATE < libs_config.CACHE_TIME) and USDT_AQ_PRICE:
        return USDT_AQ_PRICE
    else:
        return None


async def rs_update_price(source_data):
    async with await redis_db_market_price.async_connection.pipeline(transaction=False) as pipeline:
        for i in source_data:
            symbol, source, price = i["symbol"], i["exchange"], float(i["price"])
            price_adj_percent = libs_config.PRICE_ADJ.get(symbol, 1)
            # if price_adj_percent != 1:
            #     print(f"price-adj {symbol} {source} {price=} {price_adj_percent=}")
            price = price * price_adj_percent

            source_symbol = "{symbol}-{source}".format(symbol=symbol, source=source)
            none_times = LATEST_SYMBOL_PRICE.get(source_symbol, {}).get("none_times", 0)
            # 程序第一次运行，只设置上次价格，不写入数据库
            if not none_times:
                LATEST_SYMBOL_PRICE[source_symbol] = {"price": price, "none_times": 1, "except_time": 0}
            else:
                latest_price = LATEST_SYMBOL_PRICE[source_symbol]["price"]
                except_time = LATEST_SYMBOL_PRICE[source_symbol]["except_time"]
                # 如果异常价格超过2秒或者正常价格那么写入数据库，否则开始记录异常时间
                if (except_time and time.time() - except_time > 2) or abs(latest_price - price) / latest_price < 0.2:
                    LATEST_SYMBOL_PRICE[source_symbol]["except_time"] = 0
                    LATEST_SYMBOL_PRICE[source_symbol]["price"] = price

                    latest_redis = LATEST_SYMBOL_DB_PRICE.get(f"{source_symbol}_update", 0)
                    if LATEST_SYMBOL_DB_PRICE.get(source_symbol, 0) != price or time.time() - latest_redis > 5:
                        await pipeline.hmset(symbol, mapping={source: price, f"{source}_update": int(time.time())})
                        LATEST_SYMBOL_DB_PRICE[source_symbol] = price
                        LATEST_SYMBOL_DB_PRICE[f"{source_symbol}_update"] = time.time()

                    # else:
                    #     print("{}-{}价格一样不写入".format(source_symbol, price))
                elif not except_time:
                    print("{}-{}价格持续偏离".format(source_symbol, price))
                    LATEST_SYMBOL_PRICE[source_symbol]["except_time"] = time.time()
                else:
                    print("{}-{}价格持续偏离中".format(source_symbol, price))
        await pipeline.execute()


async def rs_update_ask_bid(source_data):
    async with await redis_db_askbid_price.async_connection.pipeline(transaction=False) as pipeline:
        for i in source_data:
            symbol, source, ask, bid = i["symbol"], i["exchange"], float(i["ask1"]), float(i["bid1"])
            currency = symbol.split("-")[0]
            source_symbol_ask = "{symbol}-{source}-{t}".format(symbol=symbol, source=source, t="ask")
            source_symbol_bid = "{symbol}-{source}-{t}".format(symbol=symbol, source=source, t="bid")
            source_symbol_ask_update = "{symbol}-{source}-{t}-update".format(symbol=symbol, source=source, t="ask")
            source_symbol_bid_update = "{symbol}-{source}-{t}-update".format(symbol=symbol, source=source, t="bid")
            update_dict = {}
            ask, bid = ask * libs_config.PRICE_ADJ.get(symbol, 1), bid * libs_config.PRICE_ADJ.get(symbol, 1)
            if (abs(LATEST_SYMBOL_ASK_BID_DB_PRICE.get(source_symbol_ask, 0) - ask) / ask > 0.00001 and time.time() -
                LATEST_SYMBOL_ASK_BID_DB_PRICE.get(source_symbol_ask_update, 0) > 1) or (
                    abs(LATEST_SYMBOL_ASK_BID_DB_PRICE.get(source_symbol_ask, 0) - ask) / ask > 0.00002):
                update_dict[f"{source}_ask"] = ask
                LATEST_SYMBOL_ASK_BID_DB_PRICE[source_symbol_ask] = ask
                LATEST_SYMBOL_ASK_BID_DB_PRICE[source_symbol_ask_update] = time.time()
            if (abs(LATEST_SYMBOL_ASK_BID_DB_PRICE.get(source_symbol_bid, 0) - bid) / bid > 0.00001 and time.time() -
                LATEST_SYMBOL_ASK_BID_DB_PRICE.get(source_symbol_bid_update, 0) > 1) or (
                    abs(LATEST_SYMBOL_ASK_BID_DB_PRICE.get(source_symbol_bid, 0) - bid) / bid > 0.00002):
                update_dict[f"{source}_bid"] = bid
                LATEST_SYMBOL_ASK_BID_DB_PRICE[source_symbol_bid] = bid
                LATEST_SYMBOL_ASK_BID_DB_PRICE[source_symbol_bid_update] = time.time()
            if not update_dict and not libs_config.SPOT_CURRENCY_CONFIG.get(currency, {}).get("is_stable_coin", False):
                # print(f"{symbol} 价格一样不写入{LATEST_SYMBOL_ASK_BID_DB_PRICE.get(source_symbol_ask, 0)}, {ask}, "
                #       f"{LATEST_SYMBOL_ASK_BID_DB_PRICE.get(source_symbol_bid, 0)}, {bid}")
                continue
            #     print("{}-{}价格一样不写入".format(source_symbol_ask, ask, source_symbol_bid, bid))
            LATEST_SYMBOL_ASK_BID_DB_PRICE["number"] = LATEST_SYMBOL_ASK_BID_DB_PRICE.get("number", 0) + 1
            if time.time() - LATEST_SYMBOL_ASK_BID_DB_PRICE.get("update", 0) > 5:
                print("5s-number", LATEST_SYMBOL_ASK_BID_DB_PRICE.get("number", 0) - LATEST_SYMBOL_ASK_BID_DB_PRICE.get("latest_number", 0))
                LATEST_SYMBOL_ASK_BID_DB_PRICE["latest_number"] = LATEST_SYMBOL_ASK_BID_DB_PRICE.get("number", 0)
                LATEST_SYMBOL_ASK_BID_DB_PRICE["update"] = time.time()
            update_dict[f"{source}_update"] = int(time.time())
            await pipeline.hmset(symbol, mapping=update_dict)
        await pipeline.execute()


async def rs_update_gear(source_data):
    async with await redis_db_gears.async_connection.pipeline(transaction=False) as pipeline:
        for i in source_data:
            symbol, source, asks, bids = i["symbol"], i["exchange"],i["asks"], i["bids"]
            source_symbol_ask = "{symbol}-{source}-{t}".format(symbol=symbol, source=source, t="ask")
            source_symbol_bid = "{symbol}-{source}-{t}".format(symbol=symbol, source=source, t="bid")
            update_dict = {}
            if LATEST_SYMBOL_GEAR.get(source_symbol_ask) != asks:
                update_dict[f"{source}_asks"] = asks
                LATEST_SYMBOL_GEAR[source_symbol_ask] = asks
            if LATEST_SYMBOL_GEAR.get(source_symbol_bid) != bids:
                update_dict[f"{source}_bids"] = bids
                LATEST_SYMBOL_GEAR[source_symbol_bid] = bids
            else:
                continue
            #     print("{}-{}价格一样不写入".format(source_symbol_ask, ask, source_symbol_bid, bid))
            if not update_dict:
                continue
            update_dict[f"{source}_update"] = int(time.time())
            await pipeline.hmset(symbol, mapping=update_dict)
        await pipeline.execute()


# 获取个交易所加权价格：包括市场成交价和买卖一加权平均计算的市场价
async def _rs_get_price(symbol, redis_instance):
    if symbol == "USDT-AQ":
        usdt_aq_otc_price = await usdt_aq_otc(redis_instance)
        if usdt_aq_otc_price:
            return usdt_aq_otc_price

    price = await redis_instance.async_connection.hgetall(symbol)
    sum_w = 0
    sum_price = 0
    # print("rs_get_price", symbol, price)
    for source, p in price.items():
        if "_update" in source:
            continue
        # 如果是成交价N分钟没有更新，降低其加权系数
        if "_depth" not in source and time.time() - int(price.get(f"{source}_update", 0)) > 60 * 15:
            w = libs_config.weighting.get(source, 0) * 0.2
        else:
            w = libs_config.weighting.get(source, 0)
        if w:
            sum_price += w * float(p)
            sum_w += w
    return sum_price / sum_w


def _get_base_rate(symbol):
    return symbol in libs_config.base_symbols_rate_forward


async def _get_rate(symbol1, symbol2, redis_instance):
    symbol = "{}-{}".format(symbol1, symbol2)
    if symbol not in libs_config.base_symbols_order:
        symbol = "{}-{}".format(symbol2, symbol1)

    if symbol in ["BTC-AQ", "ETH-AQ"]:
        return await _rs_get_price("{}-{}".format(symbol.split("-")[0], "USDT"), redis_instance) * await _rs_get_price(
                "{}-{}".format("USDT", "AQ"), redis_instance)
    elif symbol in ["BTC-ETH"]:
        return await _rs_get_price("{}-{}".format(symbol.split("-")[0], "USDT"), redis_instance) / await _rs_get_price(
                "{}-{}".format("ETH", "USDT"), redis_instance)
    else:
        return await _rs_get_price(symbol, redis_instance)


# [对外接口，换算完汇率价格] 获取个交易所加权价格：包括市场成交价和买卖一加权平均计算的市场价
async def get_weight_price(symbol, source="redis_db_master"):
    """
    某个数字货币例如BTC，会使用某个（唯一）基础数字货币例如USDT即BTC-USDT来对标
    """
    if source == "redis_db_master":
        redis_instance = redis_db_market_price
    else:
        redis_instance = redis_db_market_price_2
        ready = await redis_instance.async_connection.get(source)
        if not ready:
            print("get_weight_price partner not ready!!!!")
            return None

    if symbol == "USDT-AQ":
        return await _rs_get_price(symbol, redis_instance)

    s = symbol.split("-")[0]
    base_s = symbol.split("-")[1]
    base_broker = libs_config.symbol_base_mapper[s]
    # base_symbol = symbol.replace(base_s, base_broker)
    base_symbol = f"{s}-{base_broker}"
    # 拿到对标交易对价格
    base_price = await _rs_get_price(base_symbol, redis_instance)
    # 拿到汇率转换
    if base_broker != base_s:
        rate = await _get_rate(base_broker, base_s, redis_instance)
        forward = _get_base_rate((base_broker, base_s))
        if forward:
            price = base_price * rate
        else:
            price = base_price / rate
    else:
        price = base_price
    print("rs_get_price", symbol, price)
    return price


# 获取现货各交易所最大卖一和最小买一价格
async def _rs_get_ask_bid_price(symbol, redis_instance):
    if symbol == "USDT-AQ":
        usdt_aq_otc_price = await usdt_aq_otc(redis_db_market_price)
        if usdt_aq_otc_price:
            return usdt_aq_otc_price, usdt_aq_otc_price

    data = await redis_instance.async_connection.hgetall(symbol)
    now_s = time.time()
    prices_list, spend_s_list = [], {}
    for k, v in data.items():
        source, side = k.split("_")[0], k.split("_")[1]
        spend_s = now_s - float(data[f"{source}_update"])
        spend_s_list[source] = spend_s
        if k in [f"{source}_ask", f"{source}_bid"]:
            if spend_s < libs_config.MAX_SPOST_ASK_BID_VALID_TIME:
                prices_list.append(float(v))
            else:
                print(f"{symbol} {source} {side} 超时{spend_s}秒")
    if prices_list:
        ask1 = max(prices_list)
        bid1 = min(prices_list)
    else:
        ask1 = None # data[f"{near_source}_ask"]
        bid1 = None # data[f"{near_source}_bid"]
        print(f"{symbol}所有交易所都已超时或者买卖一不存在，使用市场价格，ask1:{ask1},bid1:{bid1}")
    print("get_ask1_bid1_price", symbol, ask1, bid1, prices_list)
    return ask1, bid1


# [对外接口，换算完汇率价格] 获取现货各交易所最大卖一和最小买一价格
async def get_weight_aks_bid(symbol, source="redis_db_master"):
    """
    某个数字货币例如BTC，会使用某个（唯一）基础数字货币例如USDT即BTC-USDT来对标
    """
    if source == "redis_db_master":
        redis_instance = redis_db_askbid_price
    else:
        redis_instance = redis_db_askbid_price_2
        ready = await redis_instance.async_connection.get(source)
        if not ready:
            print("get_weight_aks_bid partner not ready!!!!")
            return None

    # 特殊处理，USDT-AQ不应该由这种方式
    if symbol == "USDT-AQ":
        price = await _rs_get_price(symbol, redis_db_market_price)
        return price, price

    s = symbol.split("-")[0]
    base_s = symbol.split("-")[1]
    base_broker = libs_config.symbol_base_mapper[s]
    # base_symbol = symbol.replace(base_s, base_broker)
    base_symbol = f"{s}-{base_broker}"
    # 拿到对标交易对价格
    ask, bid = await _rs_get_ask_bid_price(base_symbol, redis_instance)
    if ask is None or bid is None:
        return ask, bid
    # 拿到汇率转换
    if base_broker != base_s:
        rate = await _get_rate(base_broker, base_s, redis_db_market_price)  # 这个要去价格库拿到价格数据
        forward = _get_base_rate((base_broker, base_s))
        if forward:
            ask, bid = ask * rate, bid * rate
        else:
            ask, bid = ask / rate, bid / rate
    else:
        ask, bid = ask, bid
    print("rs_get_price", symbol, ask, bid)
    return ask, bid


# 获取多个交易所的近盘口，用于映射盘口
async def _rs_get_gear_price(symbol, redis_instance):
    data = await redis_instance.async_connection.hgetall(symbol)
    now_s = time.time()
    asks, bids = {}, {}
    spend_s_list = {}
    expire_time_s = 4 * 60 * 60
    for k, v in data.items():
        source, side = k.split("_")[0], k.split("_")[1]
        spend_s = now_s - float(data[f"{source}_update"])
        spend_s_list[source] = spend_s
        if k in [f"{source}_asks", f"{source}_bids"]:
            v = eval(v)
            if spend_s < expire_time_s:
                if k == f"{source}_asks":
                    asks[source] = v
                elif k == f"{source}_bids":
                    bids[source] = v
            else:
                print(f"{source} {side} 超时{spend_s}秒")
    if asks and bids:
        if asks.get("bn") and bids.get("bn"):
            asks = asks["bn"]
            bids = bids["bn"]
            ex = "bn"
        elif asks.get("gate") and bids.get("gate"):
            asks = asks["gate"]
            bids = bids["gate"]
            ex = "gate"
        else:
            print(f"{symbol} 档位对标数据异常，data:{data}")
            return None, None, ""
    else:
        asks = None  # data[f"{near_source}_ask"]
        bids = None  # data[f"{near_source}_bid"]
        ex = ""
        # print(f"所有交易所都已超时，使用{spend_s_list}的价格，ask1:{ask1},bid1:{bid1}")
    # print("get_gear_price", symbol, asks, bids)
    return asks, bids, ex


# [对外接口，换算完汇率价格]  获取多个交易所的近盘口，用于映射盘口
async def get_weight_gears_price(symbol, source="redis_db_master"):
    """
    某个数字货币例如BTC，会使用某个（唯一）基础数字货币例如USDT即BTC-USDT来对标
    """
    if source == "redis_db_master":
        redis_instance = redis_db_gears
    else:
        redis_instance = redis_db_gears
        ready = await redis_instance.async_connection.get(source)
        if not ready:
            print("get_weight_gear_price partner not ready!!!!")
            return None

    s = symbol.split("-")[0]
    base_s = symbol.split("-")[1]
    base_broker = libs_config.symbol_base_mapper[s]
    # base_symbol = symbol.replace(base_s, base_broker)  # -base_s -base_broker
    base_symbol = f"{s}-{base_broker}"
    # 拿到对标交易对价格
    asks, bids, ex = await _rs_get_gear_price(base_symbol, redis_instance)
    if asks is None or bids is None:
        return asks, bids, ex
    # 拿到汇率转换
    if base_broker != base_s:
        rate = await _get_rate(base_broker, base_s, redis_db_market_price)  # 这个要去价格库拿到价格数据
        forward = _get_base_rate((base_broker, base_s))
        if forward:
            asks = [[float(i[0]) * rate, i[1]] for i in asks]
            bids = [[float(i[0]) * rate, i[1]] for i in bids]
        else:
            asks = [[float(i[0]) / rate, i[1]] for i in asks]
            bids = [[float(i[0]) / rate, i[1]] for i in bids]
    else:
        asks, bids = asks, bids
    # print("rs_get_gear_price", symbol, asks, bids)
    return asks, bids, ex


# ------------------------------------------ 合约 ------------------------------------------
# 最开始的逻辑是从技术部获取标记价格，后来优化为自己从外部拿买卖n计算标记价格，
# 如果外部价格有那么使用外部，如果有问题使用技术部获取标记价格

async def update_contract_price(source_data):
    async with await redis_db_contract_price.async_connection.pipeline(transaction=False) as pipeline:
        for i in source_data:
            await pipeline.hmset(i, {"price": source_data[i], "update": int(time.time())})
        await pipeline.execute()


async def update_contract_ask_bid_price(source_data):
    async with await redis_db_contract_price.async_connection.pipeline(transaction=False) as pipeline:
        for i in source_data:
            await pipeline.hmset(i["symbol"], {f"{i['exchange']}_price": i["price"],
                                               f"{i['exchange']}_update": int(time.time())})
        await pipeline.execute()


async def publish_contract_signal(source_data):
    if source_data:
        await redis_db_contract_price.async_connection.publish("publish_contract_signal", json.dumps(source_data))


async def update_contract_offset(source_data):
    async with await redis_db_contract_price.async_connection.pipeline(transaction=False) as pipeline:
        for i in source_data:
            await pipeline.hmset("CONTRACT_OFFSET_PRICE", {i["symbol"]: i["offset"]})
        await pipeline.execute()


async def get_contract_offset(symbol):
    offset = await redis_db_contract_price.async_connection.hget("CONTRACT_OFFSET_PRICE", symbol)
    offset = float(offset) if offset else 0
    return offset if abs(
        offset) < libs_config.CONTRACT_MAX_OFFSET_PERCENT else libs_config.CONTRACT_MAX_OFFSET_PERCENT * abs(
        offset) / offset


async def update_contract_askbid_offset(source_data):
    async with await redis_db_contract_price.async_connection.pipeline(transaction=False) as pipeline:
        for i in source_data:
            await pipeline.hmset("CONTRACT_ASKBID_OFFSET_PRICE", {f'{i["symbol"]}-ask': i["ask_offset"],
                                                                  f'{i["symbol"]}-bid': i["bid_offset"],
                                                                  })
        await pipeline.execute()


async def get_contract_askbid_offset(symbol):
    ask_offset = await redis_db_contract_price.async_connection.hget("CONTRACT_ASKBID_OFFSET_PRICE",
                                                               "{}-{}".format(symbol, "ask"))
    ask_offset = float(ask_offset) if ask_offset else 0
    ask_offset = ask_offset if abs(
        ask_offset) < libs_config.CONTRACT_MAX_ASKBID_OFFSET_PERCENT else libs_config.CONTRACT_MAX_ASKBID_OFFSET_PERCENT * abs(
        ask_offset) / ask_offset

    bid_offset = await redis_db_contract_price.async_connection.hget("CONTRACT_ASKBID_OFFSET_PRICE",
                                                               "{}-{}".format(symbol, "bid"))
    bid_offset = float(bid_offset) if bid_offset else 0
    bid_offset = bid_offset if abs(
        bid_offset) < libs_config.CONTRACT_MAX_ASKBID_OFFSET_PERCENT else libs_config.CONTRACT_MAX_ASKBID_OFFSET_PERCENT * abs(
        bid_offset) / bid_offset

    return ask_offset, bid_offset


# 合约价格优先使用买卖一计算的市场价，如果更新不及时
# 使用市场成交价，如果更新不及时
# 使用现货价格
async def _get_contract_price(symbol, redis_instance):
    # is_aq = True if "-AQ" in symbol else False
    # if is_aq:
    #     trans_symbol = symbol.replace("-AQ", "-USDT")
    # else:
    #     trans_symbol = symbol
    trans_symbol = symbol

    contract_price = await redis_instance.async_connection.hgetall(trans_symbol)
    price = contract_price.pop("price", None)
    price = float(price) if price else price
    update = int(contract_price.pop("update", 0))
    ex_price_list = []
    # 因为现货买卖一是按照交易所启动的，无法加权各个交易所价格，所以都写入在获取的时候加权
    for k, v in contract_price.items():
        if "price" in k:
            source, _ = k.split("_")
            u = int(contract_price.get(f"{source}_update", 0))
            #  因为价格是获取的买卖一定时推送，所以60s之内一定有数据，如果没有数据说明相应服务是停止了，需要过滤掉。
            if time.time() - u < 60:
                ex_price_list.append(float(v))
        continue
    if ex_price_list:
        p = sum(ex_price_list) / len(ex_price_list)
    elif time.time() - update < libs_config.MAX_CONTRACT_VALID_TIME:
        print(symbol, "Get Contract Price Timeout- ASKBID, Use Spot Market Mark Price !")
        p = price
    else:
        p = None
    if p:
        # if is_aq:
        #     p = float(p) * 6.5
        # else:
        #     p = float(p)
        return p
    price = await get_weight_price(symbol)
    print(symbol, "Get Contract Price Timeout, Use Spot Price !")
    return price


# [对外接口] 合约价格对外接口
async def get_contract_weight_price(symbol, source="redis_db_master"):
    if source == "redis_db_master":
        redis_contract_instance = redis_db_contract_price
    else:
        redis_contract_instance = redis_db_contract_price_2
        ready = await redis_contract_instance.async_connection.get(source)
        if not ready:
            print("rs_get_contract_price partner not ready!!!!")
            return None
    price = await _get_contract_price(symbol, redis_contract_instance)
    # 资金费用暂时注释
    # offset = await get_contract_offset(symbol)
    # print("get offset ", offset)
    # price = price * (1+offset)

    ask_offset, bid_offset = await get_contract_askbid_offset(symbol)
    print("ask_offset", ask_offset, "bid_offset", bid_offset, "price", price)
    contract_price = (price * (1+ask_offset) + price * (1+bid_offset)) / 2
    return contract_price


async def get_precision_config(symbol=None, name='redis_precision'):
    global SYMBOLS_PRECISION_UPDATETIME, SYMBOLS_PRECISION, CONTRACT_SYMBOLS_PRECISION_UPDATETIME, CONTRACT_SYMBOLS_PRECISION
    precision_update_time = SYMBOLS_PRECISION_UPDATETIME
    symbols_precision = SYMBOLS_PRECISION
    if name == 'contract_redis_precision':
        precision_update_time = CONTRACT_SYMBOLS_PRECISION_UPDATETIME
        symbols_precision = CONTRACT_SYMBOLS_PRECISION
    current_time = int(time.time())
    update_time = precision_update_time.get('update', 0)
    if current_time - update_time >= 60 * 10:
        precision_update_time['update'] = current_time
        symbol_precision = await redis_db_control.async_connection.hgetall(name)
        for k, v in symbol_precision.items():
            precision = json.loads(v)
            symbols_precision[k] = precision
        cu_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print('update_precision', cu_time)
    if symbol:
        precision = symbols_precision.get(symbol, {})
        print('rs_get_precision', symbol, precision)
    else:
        precision = symbols_precision
        # print('rs_get_precision', precision)
    return precision


async def main():
    await get_weight_gears_price("BTC-USDT")


if __name__ == "__main__":
    asyncio.run(main())
