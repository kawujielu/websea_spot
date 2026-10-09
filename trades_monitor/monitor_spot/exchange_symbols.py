import os, sys
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
from libs.send_tglegram_msg import send_telegram
from collections import defaultdict
from exchanges.restful_api.okex import okex_instance
from exchanges.restful_api.gateio import gateio_instance
from exchanges.restful_api.huobi import huobi_instance
from exchanges.restful_api.binance import bn_instance
import asyncio
from libs import libs_config
from exchanges.restful_api.abc_spot import AApi
from scaffold.mysql import G_MysqlSession
from libs import heartbeat
from libs.helper import add_retry

limit = ['USDT', 'BTC', 'ETH', 'HUSD', 'BUSD']


# base 交易  quote 计价


@add_retry
async def websea_curr():
    currency = []
    websea_instance = AApi(token='cb95edcac135b5a28ed76233abca5b00', secret_key='t8leukegp3t487kzj9xf')
    re = await websea_instance.symbols()
    res = re['result']
    for i in res:
        currency.append(i['symbol'].split('-')[0])
    return currency


@add_retry
async def bn_ws(abc_currency):
    bn_symbols = await bn_instance.get_symbols()
    symbols = defaultdict(list)
    bn_currency = []
    for currency in abc_currency:
        data = f'1000{currency}'
        bn_currency.append(data)
    for info in bn_symbols['symbols']:
        base = info['baseAsset']
        if base not in abc_currency + bn_currency:
            continue
        if info['isSpotTradingAllowed'] and info['status'] == 'TRADING':
            quote = info['quoteAsset']
            bn_symbol = base + '-' + quote
            if base.startswith('1000'):
                base = base.split('1000')[-1]
            symbol = base
            if bn_symbol not in symbols[symbol] and quote in limit:
                symbols[symbol].append(bn_symbol)
    return symbols


@add_retry
async def okex_w(abc_currency):
    ok_symbols = await okex_instance.get_symbols()
    symbols = defaultdict(list)
    ticker_info = await okex_instance.get_tickers()
    for info in ok_symbols['data']:
        base = info['baseCcy']
        if base not in abc_currency:
            continue
        for ticker in ticker_info['data']:
            t = int(time.time() * 1000)
            timeArray = int(ticker['ts'])
            symbol = ticker['instId'].split('-')[0]
            quote = ticker['instId'].split('-')[1]
            if timeArray > int(round(t)) - 60 * 60 * 1000:
                if quote not in symbols[symbol] and quote in limit:
                    symbols[symbol].append(quote)
    return symbols


@add_retry
async def huobi_w(abc_currency):
    hb_symbols = await huobi_instance.get_symbols()
    symbols = defaultdict(list)
    for info in hb_symbols['data']:
        base = info['bcdn'].upper()
        if base not in abc_currency:
            continue
        if info['state'] == 'online':
            symbol = base
            quote = info['qcdn'].upper()
            if quote not in symbols[symbol] and quote in limit:
                symbols[symbol].append(quote)
    return symbols


@add_retry
async def gate_w(abc_currency):
    gate_symbols = await gateio_instance.get_symbols()
    symbols = defaultdict(list)
    ticker_info = await gateio_instance.get_tickers()
    for info in gate_symbols:
        base = info['currency']
        if base not in abc_currency:
            continue
        for ticker in ticker_info:
            symbol = ticker['currency_pair'].split('_')[0]
            quote = ticker['currency_pair'].split('_')[1]
            if quote not in symbols[symbol] and quote in limit:
                symbols[symbol].append(quote)
    return symbols


async def main():
    abc_currency = await websea_curr()
    bn_market = await bn_ws(abc_currency)
    gate_market = await gate_w(abc_currency)
    okex_market = await okex_w(abc_currency)
    currency = list(bn_market.keys()) + list(gate_market.keys()) + list(okex_market.keys())
    currency = list(set(currency))
    results = defaultdict(list)
    symbol_exchange = defaultdict(list)
    for i in currency:
        if i in abc_currency:
            if bn_market.get(i, None):
                results[i].append({'bn': bn_market.get(i, None)})
                symbol_exchange[i].append('bn')
            if okex_market.get(i, None):
                results[i].append({'okex': okex_market.get(i, None)})
                symbol_exchange[i].append('okex')
            if gate_market.get(i, None):
                results[i].append({'gate': gate_market.get(i, None)})
                symbol_exchange[i].append('gate')
    return symbol_exchange, results


async def websea_pair():
    price_symbol_config = libs_config.PRICE_SYMBOL_CONFIG
    # print(price_symbol_config)
    exchange_symbol = {}
    for k, v in price_symbol_config.items():
        exchange_symbol[k.split('-')[0]] = list(v['price_symbol'].keys())
    for k, v in price_symbol_config.items():
        exchange_symbol[k.split('-')[0]] = exchange_symbol.get(k.split('-')[0], []) + list(v['depth_price'].keys())
    for k, v in price_symbol_config.items():
        exchange_symbol[k.split('-')[0]] = exchange_symbol.get(k.split('-')[0], []) + list(v['dex_price'].keys())
    return exchange_symbol


async def main_excu():
    try:
        symbol_exchange, results = await main()
        pair = await websea_pair()
        result = {}
        for k, v in pair.items():
            try:
                result[k] = {}
                result[k]['exchange'] = v
                result[k]['exchange_other'] = symbol_exchange[k]
                result[k]['market'] = results[k]
            except:
                pass
        col = []
        re, col_list = await G_MysqlSession.fetch_all_and_description(f'''select * from  exchange_symbols_referrence''')
        for i in col_list:
            col.append(i[0])
        datas = {}
        for i in re:
            datas[i[0]] = {'exchange': i[1], 'exchange_other': i[2], 'market': i[3]}
        cu_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        message = f'{cu_time} 参考交易所:\n'
        for k, v in result.items():
            valuse = ''
            for i, j in v.items():
                try:
                    if str(datas[k][i]) != str(j):
                        pass
                    if i == 'exchange_other' and str(datas[k][i]) != str(j):
                        message += f' 币种: {k} 可参考交易所: {str(datas[k][i])} --> {str(j)}  \n'
                except:
                    sql = f'''INSERT ignore INTO exchange_symbols_referrence (currency,exchange,exchange_other,market) VALUES ("{k}","{v['exchange']}","{v.get('exchange_other', [])}","{v.get('market', [])}")'''
                    await G_MysqlSession.insert(sql)
                valuse += f'{i}="{j}",'
            valuse = valuse[:-1]
            update_sql = f'''UPDATE exchange_symbols_referrence SET {valuse} WHERE currency='{k}' '''
            await G_MysqlSession.insert(update_sql)
        if message != f'{cu_time} 参考交易所:\n':
            send_telegram(message, 'dw_info')
        await heartbeat.i_live_well("外部可对标交易所", 60 * 17 * 2, 66)
    except:
        print(f"exchange_symbols: {traceback.format_exc()}")


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main_excu())
