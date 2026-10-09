from libs import libs_config, libs_price
from many_configs.base_config import ExchangeCode

all_symbols = libs_config.contract_price_all_symbols
price_redis_db = libs_price.redis_db_contract_price
market_config_redis_db = libs_price.redis_db_control

# --------------------------- 剔除redis中某个交易所价格 ---------------------------

okex_except = []
hb_except = []
bn_except = ["LEVER-USDT", "HIFI-USDT", "QNT-USDT", "COMBO-USDT", "NTRN-USDT", "DASH-USDT", "RIF-USDT", "MANTA-USDT", "HOOK-USDT", "ONG-USDT", "GTC-USDT", "GLMR-USDT"]
gate_except = []


def disable_ex_price(exchange):
    disable_symbols = libs_config.contract_price_ex_abc_symbols.get(exchange, set())
    for s in disable_symbols:
        s = libs_config.contract_price_trans_symbols[exchange][s]

        if exchange == "okex" and s in okex_except:
            continue
        elif exchange == "hb" and s in hb_except:
            continue
        elif exchange == "bn" and s in bn_except:
            continue
        elif exchange == "gate" and s in gate_except:
            continue
        print(f"{s} is delete process")
        price_redis_db.hdel(s, f"{exchange}_price")
        price_redis_db.hdel(s, f"{exchange}_update")

    disable_symbols = libs_config.contract_price_ex_symbols_from_contract.get(exchange, set())
    for s in disable_symbols:
        s = libs_config.contract_price_trans_symbols_from_contract[exchange][s]
        if exchange == "okex" and s in okex_except:
            continue
        elif exchange == "hb" and s in hb_except:
            continue
        elif exchange == "bn" and s in bn_except:
            continue
        elif exchange == "gate" and s in gate_except:
            continue
        print(f"{s} is delete process")
        price_redis_db.hdel(s, f"c-{exchange}_price")
        price_redis_db.hdel(s, f"c-{exchange}_update")


# --------------------------- 获取redis所有价格 ---------------------------

# 在删除要停机的数据之前，需要检测是否有不同对标渠道价格偏移较大的交易对
def get_symbol_ex_prices(ex):
    attention_symbols = {}

    price_symbols = libs_config.contract_price_ex_abc_symbols.get(ex, set())
    trade_symbols = price_symbols
    for s in trade_symbols:
        s = libs_config.contract_price_trans_symbols[ex][s]
        symbol_prices = price_redis_db.hgetall(s)
        prices = [float(symbol_prices[i]) for i in symbol_prices if "update" not in i]
        max_price = max(prices)
        min_price = min(prices)
        p = max_price / min_price - 1
        if p > 0.005:
            attention_symbols[s] = p

    price_symbols = libs_config.contract_price_ex_symbols_from_contract.get(ex, set())
    trade_symbols = price_symbols
    for s in trade_symbols:
        s = libs_config.contract_price_trans_symbols_from_contract[ex][s]
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
        for _ex in libs_config.contract_price_ex_abc_symbols:
            if s in libs_config.contract_price_ex_abc_symbols[_ex]:
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

    for exchange in libs_config.contract_price_ex_abc_symbols:
        for s in libs_config.contract_price_ex_abc_symbols[exchange]:
            s = libs_config.contract_price_trans_symbols[exchange][s]
            new_exchange = f"{exchange}_price"
            if s in symbol_trades:
                symbol_trades[s].add(new_exchange)
            else:
                symbol_trades[s] = {new_exchange}

    for exchange in libs_config.contract_price_ex_symbols_from_contract:
        for s in libs_config.contract_price_ex_symbols_from_contract[exchange]:
            s = libs_config.contract_price_trans_symbols_from_contract[exchange][s]
            new_exchange = f"c-{exchange}_price"
            if s in symbol_trades:
                symbol_trades[s].add(new_exchange)
            else:
                symbol_trades[s] = {new_exchange}

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

    disable_ex_price(disable_ex)

    check_trade_price()
    only_this_ex_symbols(disable_ex)

    get_symbol_ex_prices(disable_ex)


