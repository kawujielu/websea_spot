from many_configs.spot_currency_config import price_market_ex_symbols, price_depth_ex_symbols, price_trans_symbols
from libs import libs_price
from many_configs.base_config import ExchangeCode

"""
如果某个交易所A停机
实时成交价-包括市场价格和买卖n计算的市场价格：
    1 币种只有A交易所对标，那么需要查看是否有新的交易所可以对标和对冲，如果最终A是唯一的对标交易所，那么不能清理掉redis这些币种
    关于A交易所实时成交价，在停机期间根据对冲缺口人工干预。
用来确定盘口价差的买卖一价格：
    1 买卖一价格15min自动过时弃用，所以暂时不需要清理redis数据

以上两个重要价格，需要关注本身对标两个交易所，但是这两个交易所价差特别大的情况，需要灵活处理
"""

all_symbols = []
# 注意：在操作的时候先不要把要停机的交易所改成false
for t in price_market_ex_symbols:
    all_symbols.extend([price_trans_symbols[t][i] for i in price_market_ex_symbols[t]])

for t in price_depth_ex_symbols:
    all_symbols.extend([price_trans_symbols[t][i] for i in price_depth_ex_symbols[t]])
all_symbols = set(all_symbols)

price_redis_db = libs_price.redis_db_market_price
market_config_redis_db = libs_price.redis_db_control
askbid_price_redis_db = libs_price.redis_db_askbid_price


# TODO dangerous_symbols 特殊处理一下
def dangerous_symbols(ex):
    container = {}
    for s in all_symbols:
        for t in price_market_ex_symbols:
            if s in price_market_ex_symbols[t]:
                if s in container:
                    container[s].add(t)
                else:
                    container[s] = {t}
        for t in price_depth_ex_symbols:
            if s in price_depth_ex_symbols[t]:
                if s in container:
                    container[s].add(t)
                else:
                    container[s] = {t}
    for t in container:
        if len(container[t]) <= 1 and ex in container[t]:
            # print(t, )
            print(t, set(container[t]))
    return
    res1 = market_config_redis_db.hgetall('price_percent')
    print(res1)
    res2 = market_config_redis_db.hgetall('trade_volume_percent')
    print(res2)
    org_price_percent = {}
    org_trade_volume_percent = {}
    # to_do_list = ["AE", "YAMV2", "AR", "BCHA", "CRU", "NEST", "BTM", "PEARL", "GOF", "RING", "XRT", "CVP", "LAMB", "SWRV", "PHA", "EGT", "ACH", "GXC"]
    to_do_list = ["DIA", "REP", "FLM", "ENJ", "SC", "SRM", ]
    for s in to_do_list:
        market_config_redis_db.hset('price_percent', s, 0.2)
        if res1.get(s):
            print(s, res1.get(s))
            org_price_percent[s] = res1.get(s)

        # market_config_redis_db.hset('trade_volume_percent', "{}-USDT".format(s, ), 0.01)
        # if res2.get(s):
        #     print(s, res2.get(s))
        #     org_trade_volume_percent[s] = res2.get(s)

    res = market_config_redis_db.hgetall('price_percent')
    print(res)
    res = market_config_redis_db.hgetall('trade_volume_percent')
    print(res)
    print("org_price_percent", org_price_percent)
    print("org_trade_volume_percent", org_trade_volume_percent)
    #
    # org_price_percent = {'FIL6': '0.1'}
    # org_trade_volume_percent = {'FIL6': '0.1'}
    # for s in to_do_list:
    #     if s in org_price_percent:
    #         print("price_percent set", s, org_price_percent[s])
    #         market_config_redis_db.hset('price_percent', s, org_price_percent[s])
    #     else:
    #         print("price_percent del", s, )
    #         market_config_redis_db.hdel('price_percent', s)
    #
    #     if s in org_trade_volume_percent:
    #         print("trade_volume_percent set", s, org_trade_volume_percent[s])
    #         market_config_redis_db.hset('trade_volume_percent', s, org_trade_volume_percent[s])
    #     else:
    #         print("trade_volume_percent del", s)
    #         market_config_redis_db.hdel('trade_volume_percent', s)

# --------------------------- 剔除redis中某个交易所价格 ---------------------------

okex_except = ["DORA-USDT", "ANC-USDT", "JFI-USDT", "KINE-USDT", "XCH-USDT", "LON-USDT", "ICP-USDT"]
hb_except = ["NSURE-USDT", "APN-USDT", "AE-USDT", "ACH-USDT", "PEARL-USDT", "GXC-BTC", "XRT-USDT", "MDX-USDT", "RING-USDT", "DAI-USDT", "YAM-USDT", "AR-USDT", "CRU-USDT", "NEST-USDT",]
bn_except = []
gate_except = ["SHIB-USDT", "FEI-USDT", "JGN-USDT", "ETHA-USDT", "AKITA-USDT", "OXY-USDT", "LAVA-USDT", "LPT-USDT", "FIL6-USDT", "BAMBOO-USDT"]


def disable_trade(exchange):
    disable_symbols = price_market_ex_symbols.get(exchange, set())
    disable_symbols = {price_trans_symbols[exchange][i] for i in disable_symbols}
    for s in disable_symbols:
        if exchange == "okex" and s in okex_except:
            continue
        elif exchange == "hb" and s in hb_except:
            continue
        elif exchange == "bn" and s in bn_except:
            continue
        elif exchange == "gate" and s in gate_except:
            continue
        print(f"{s} is delete process")
        price_redis_db.hdel(s, exchange)
        price_redis_db.hdel(s, f"{exchange}_update")


def disable_depth_trade(exchange):
    disable_symbols = price_depth_ex_symbols.get(exchange, set())
    disable_symbols = {price_trans_symbols[exchange][i] for i in disable_symbols}
    for s in disable_symbols:
        if exchange == "okex" and s in okex_except:
            continue
        elif exchange == "hb" and s in hb_except:
            continue
        elif exchange == "bn" and s in bn_except:
            continue
        elif exchange == "gate" and s in gate_except:
            continue
        print(s, f"{exchange}_depth is delete process")
        price_redis_db.hdel(s, f"{exchange}_depth")
        price_redis_db.hdel(s, f"{exchange}_depth_update")


def disable_ask_bid_trade(exchange):
    price_symbols = price_market_ex_symbols.get(exchange, set())
    depth_symbols = price_depth_ex_symbols.get(exchange, set())
    price_symbols = {price_trans_symbols[exchange][i] for i in price_symbols}
    depth_symbols = {price_trans_symbols[exchange][i] for i in depth_symbols}
    disable_symbols = price_symbols | depth_symbols
    for s in disable_symbols:
        if exchange == "okex" and s in okex_except:
            continue
        elif exchange == "hb" and s in hb_except:
            continue
        elif exchange == "bn" and s in bn_except:
            continue
        elif exchange == "gate" and s in gate_except:
            continue
        print(f"{s} is delete process")
        askbid_price_redis_db.hdel(s, f"{exchange}_ask")
        askbid_price_redis_db.hdel(s, f"{exchange}_bid")
        askbid_price_redis_db.hdel(s, f"{exchange}_update")


# --------------------------- 获取redis所有价格 ---------------------------

# 在删除要停机的数据之前，需要检测是否有不同对标渠道价格偏移较大的交易对
def get_symbol_ex_prices(ex):
    attention_symbols = {}
    if ex == "all":
        trade_symbols = all_symbols
    else:
        price_symbols = price_market_ex_symbols.get(ex, set())
        depth_symbols = price_depth_ex_symbols.get(ex, set())
        price_symbols = {price_trans_symbols[ex][i] for i in price_symbols}
        depth_symbols = {price_trans_symbols[ex][i] for i in depth_symbols}
        trade_symbols = price_symbols | depth_symbols
    for s in trade_symbols:
        symbol_prices = price_redis_db.hgetall(s)
        prices = [float(symbol_prices[i]) for i in symbol_prices if "update" not in i]
        max_price = max(prices)
        min_price = min(prices)
        p = max_price / min_price - 1
        if p > 0.005:
            attention_symbols[s] = p
    print("attention_symbols",  attention_symbols)


# --------------------------- 获取redis所有价格 ---------------------------


def only_this_ex_symbols(ex):
    container = {}
    for s in all_symbols:
        if s not in container:
            container[s] = set()
        for _ex in price_market_ex_symbols:
            if s in price_market_ex_symbols[_ex]:
                container[s].add(_ex)
        for _ex in price_depth_ex_symbols:
            if s in price_depth_ex_symbols[_ex]:
                container[s].add(_ex)

    for s in container:
        if len(container[s]) <= 1 and ex in container[s]:
            print(f"{s} 只对标了 {ex} ", set(container[s]))


# --------------------------- 检查redis交易对对标价格是否和配置相同 ---------------------------

def check_trade_price():
    symbol_trades = {}
    symbol_trades_redis = {}
    for symbol in all_symbols:
        symbol_trades_redis[symbol] = set([i for i in price_redis_db.hgetall(symbol).keys() if "update" not in i])

    for exchange in price_market_ex_symbols:
        for s in price_market_ex_symbols[exchange]:
            s = price_trans_symbols[exchange][s]
            if s in symbol_trades:
                symbol_trades[s].add(exchange)
            else:
                symbol_trades[s] = {exchange}

    for p_exchange in price_depth_ex_symbols:
        for s in price_depth_ex_symbols[p_exchange]:
            s = price_trans_symbols[p_exchange][s]
            if s in symbol_trades:
                symbol_trades[s].add("{}_depth".format(p_exchange))
            else:
                symbol_trades[s] = {"{}_depth".format(p_exchange)}

    print("config交易对和交易所对应关系", symbol_trades)
    print("redis交易对和交易所对应关系", symbol_trades_redis)
    diff_keys = set(symbol_trades_redis.keys()) ^ set(symbol_trades.keys())
    if diff_keys:
        print("config和redis中交易对的数量不一致！", diff_keys)
    for s in symbol_trades:
        diff = symbol_trades[s] ^ symbol_trades_redis[s]
        handler_diff = []
        for e in diff:
            if disable_ex not in e:
                handler_diff.append(e)
        if handler_diff:
            print(s, "config和redis中交易所对应关系不一致！", handler_diff)


if __name__ == "__main__":
    disable_ex = ExchangeCode.bn.value
    check_trade_price()
    only_this_ex_symbols(disable_ex)

    get_symbol_ex_prices(disable_ex)

    # 可以disable下面交易所对标 zh hb okex bn bitfinex gate

    # disable_trade(disable_ex)
    # disable_depth_trade(disable_ex)
    # disable_ask_bid_trade(disable_ex)
    print("delete ok!!")
    check_trade_price()
    only_this_ex_symbols(disable_ex)

    get_symbol_ex_prices(disable_ex)
    #
    # dangerous_symbols(disable_ex)


