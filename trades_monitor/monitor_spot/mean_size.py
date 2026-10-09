import json

from libs import libs_config, libs_price_async
import asyncio
from scaffold.mysql import Hedge_MysqlSession
from exchanges.restful_api.gateio import gateio_instance

SPOT_CURRENCY_CONFIG = libs_config.SPOT_CURRENCY_CONFIG
'''
脚本检测"mean_order_size": {"BEAMX-USDT": 250000},超过3000u的，*0.2。 超过1000u的 * 0.3。 其他的 * 0.5. 
'''


async def main():
    results = {}
    for currency, config in SPOT_CURRENCY_CONFIG.items():
        symbol = currency + '-USDT'
        avg_price = await libs_price_async.get_weight_price(symbol)
        price_value = config['mean_order_size'][symbol] * avg_price
        if price_value >= 3000:
            print(
                f"{currency}-USDT => mean_order_size:{config['mean_order_size'][symbol]}, 价格: {avg_price}, 价值: {price_value}, 系数0.2, \n修改值:{config['mean_order_size'][symbol] * 0.2}, 修改后价值：{config['mean_order_size'][symbol] * 0.5 * avg_price}")
            config['mean_order_size'][symbol] = config['mean_order_size'][symbol] * 0.2
            results[currency] = config
        elif price_value >= 1000:
            print(
                f"{currency}-USDT => mean_order_size:{config['mean_order_size'][symbol]}, 价格: {avg_price}, 价值: {price_value}, 系数0.3, \n修改值:{config['mean_order_size'][symbol] * 0.3}, 修改后价值：{config['mean_order_size'][symbol] * 0.5 * avg_price}")
            config['mean_order_size'][symbol] = config['mean_order_size'][symbol] * 0.3
            results[currency] = config
        else:
            print(
                f"{currency}-USDT => mean_order_size:{config['mean_order_size'][symbol]}, 价格: {avg_price}, 价值: {price_value}, 系数0.5, \n修改值:{config['mean_order_size'][symbol] * 0.5}, 修改后价值：{config['mean_order_size'][symbol] * 0.5 * avg_price}")
            config['mean_order_size'][symbol] = config['mean_order_size'][symbol] * 0.5
            results[currency] = config

    print(results)


async def get_hedge_config():
    websea_hedge = {}
    hedge_config = await Hedge_MysqlSession.fetch_all('select * from hedge_config')
    for config in hedge_config:
        config_li = json.loads(config[1])
        datas = []
        for ex, value in config_li['exchanges'].items():
            if float(value['percent']) != 0:
                datas.append(ex)
        websea_hedge[config[0]] = datas
    return websea_hedge


'''
买或卖档前千5的总量小于500u或者买卖一价差大于2%， dangerous_level = 6， hedge_threshold = threshold_6 mean_order_size = 70U
买或卖档前千5的总量小于1000u或者买卖一价差大于1%， dangerous_level = 5， hedge_threshold = threshold_5 mean_order_size = 90U
买或卖档前千5的总量小于1500u， dangerous_level = 4， hedge_threshold = threshold_4 mean_order_size = 150U
买或卖档前千5的总量大于1500u， dangerous_level = 3， hedge_threshold = threshold_4 mean_order_size = 200U

买或卖档前千5的总量小于500u或者买卖一价差大于2%， dangerous_level = 6， hedge_threshold = threshold_6 mean_order_size = 70U self_market_value=20u
买或卖档前千5的总量小于1000u或者买卖一价差大于1%， dangerous_level = 5， hedge_threshold = threshold_5 mean_order_size = 90U  self_market_value=50u
买或卖档前千5的总量小于1500u， dangerous_level = 4， hedge_threshold = threshold_4 mean_order_size = 150U self_market_value=90u
买和和和卖档前千5的总量大于1500u， dangerous_level = 3， hedge_threshold = threshold_4 mean_order_size = 200U self_market_value=150u
'''


async def change_gate():
    gate_hedge = []
    websea_hedge = await get_hedge_config()
    for currency, config in SPOT_CURRENCY_CONFIG.items():
        hedge_li = websea_hedge.get(currency, [])
        if 'gate' in hedge_li:
            gate_hedge.append(currency)
    print(gate_hedge)
    for currency, config in SPOT_CURRENCY_CONFIG.items():
        if currency in gate_hedge:
            symbol = currency + '-USDT'
            avg_price = await libs_price_async.get_weight_price(symbol)
            res = await gateio_instance.depth(symbol=symbol, limit=100, interval=0)
            ask = float(res['asks'][0][0]) * (1 + 0.005)
            bid = float(res['bids'][0][0]) * (1 - 0.005)
            print(currency, ask, bid)
            asks_amount = [float(i[1]) for i in res['asks'] if float(i[0]) <= ask]
            bids_amount = [float(i[1]) for i in res['bids'] if float(i[0]) >= bid]
            total_amount = min(sum(asks_amount), sum(bids_amount)) * avg_price
            ask_bid_p = float(res['asks'][0][0]) / float(res['bids'][0][0]) - 1
            print(currency, total_amount, ask_bid_p)
            if total_amount <= 500 or ask_bid_p >= 0.02:
                config['mean_order_size'] = 70 / avg_price
                config['dangerous_level'] = 6
                config['hedge_threshold'] = "threshold_6"
                print(currency, config['hedge_threshold'], config['dangerous_level'], config['mean_order_size'], 20)
                print('=' * 100)
            elif total_amount <= 1000 or ask_bid_p >= 0.01:
                config['mean_order_size'] = 90 / avg_price
                config['dangerous_level'] = 5
                config['hedge_threshold'] = "threshold_5"
                print(currency, config['hedge_threshold'], config['dangerous_level'], config['mean_order_size'], 50)
                print('=' * 100)
            elif total_amount <= 1500:
                config['mean_order_size'] = 150 / avg_price
                config['dangerous_level'] = 4
                config['hedge_threshold'] = "threshold_4"
                print(currency, config['hedge_threshold'], config['dangerous_level'], config['mean_order_size'], 90)
                print('=' * 100)
            else:
                config['mean_order_size'] = 200 / avg_price
                config['dangerous_level'] = 3
                config['hedge_threshold'] = "threshold_4"
                print(currency, config['hedge_threshold'], config['dangerous_level'], config['mean_order_size'], 150)
                print('=' * 100)


if __name__ == '__main__':
    asyncio.run(change_gate())
