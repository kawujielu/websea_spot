import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
from libs.send_tglegram_msg import send_telegram
from collections import defaultdict
from exchanges.restful_api.okex import okex_instance
from exchanges.restful_api.gateio import gateio_instance
from exchanges.restful_api.binance import bn_instance
import asyncio
from libs import libs_config
from exchanges.restful_api.abc_contract import AbcApi
from scaffold.mysql import G_MysqlSession
from libs import heartbeat
from libs.helper import add_retry

limit = ['USDT', 'BTC', 'ETH', 'HUSD', 'BUSD']


@add_retry
async def websea_contract_symbols():
    symbols = []
    currencies = []
    websea_instance = AbcApi(token='cb95edcac135b5a28ed76233abca5b00', secret_key='t8leukegp3t487kzj9xf')
    precision = await websea_instance.precision()
    result = dict(precision['result'])
    for symbol, _ in result.items():
        currency = symbol.split('-')[0]
        symbols.append(symbol)
        if currency not in currencies:
            currencies.append(symbol.split('-')[0])
    return symbols, currencies


@add_retry
async def bn_w(abc_currencies):
    bn_symbols = await bn_instance.get_contract_symbols()
    symbols = defaultdict(list)
    bn_currency = []
    for currency in abc_currencies:
        data = f'1000{currency}'
        bn_currency.append(data)
    for info in bn_symbols['symbols']:
        base = info['baseAsset']
        quote = info['quoteAsset']
        if base not in abc_currencies + bn_currency:
            continue
        if info['status'] == 'TRADING':
            bn_symbol = base + '-' + quote
            if base.startswith('1000'):
                base = base.split('1000')[-1]
            symbol = base + '-' + quote
            if bn_symbol not in symbols[symbol] and quote in limit:
                symbols[symbol].append(bn_symbol)
    return symbols


@add_retry
async def okex_w(abc_currencies):
    ok_symbols = await okex_instance.get_symbols(instType='SWAP')
    symbols = defaultdict(list)
    for info in ok_symbols['data']:
        symbol = info['instFamily']
        if not symbol:
            continue
        base = symbol.split('-')[0]
        quote = symbol.split('-')[1]
        if base not in abc_currencies:
            continue
        if info['state'] == 'live':
            symbol = base + '-' + quote
            if quote not in symbols[symbol] and quote in limit:
                symbols[symbol].append(quote)
    return symbols


@add_retry
async def gate_w(abc_currencies):
    gate_symbols = await gateio_instance.get_contract_symbols()
    symbols = defaultdict(list)
    for info in gate_symbols:
        symbol = info['name']
        base = symbol.split('_')[0]
        quote = symbol.split('_')[1]
        if base not in abc_currencies:
            continue
        if not info['in_delisting']:
            symbol = base + '-' + quote
            if quote not in symbols[symbol] and quote in limit:
                symbols[symbol].append(quote)
    return symbols


async def main():
    abc_symbols, abc_currencies = await websea_contract_symbols()
    bn_market = await bn_w(abc_currencies)
    gate_market = await gate_w(abc_currencies)
    okex_market = await okex_w(abc_currencies)
    symbols = list(bn_market.keys()) + list(gate_market.keys()) + list(okex_market.keys())
    symbols = list(set(symbols))
    results = defaultdict(list)
    symbol_exchange = defaultdict(list)
    for i in symbols:
        if i in abc_symbols:
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
    price_symbol_config = libs_config.CONTRACT_PRICE_SYMBOL_CONFIG
    contract_exchange_symbol, exchange_symbol = {}, {}
    for k, v in price_symbol_config.items():
        exchange_symbol[k] = list(v['price_symbol'].keys())
    for k, v in price_symbol_config.items():
        contract_exchange_symbol[k] = list(v['contract_price_symbol'].keys())
    return exchange_symbol, contract_exchange_symbol


async def main_excu():
    symbol_exchange, results = await main()
    exchange_symbol, contract_exchange_symbol = await websea_pair()
    result = {}
    for k, v in contract_exchange_symbol.items():
        try:
            result[k] = {}
            result[k]['contract_exchange'] = v
            result[k]['exchange'] = exchange_symbol.get(k, [])
            result[k]['exchange_other'] = symbol_exchange[k]
            result[k]['market'] = results[k]
        except:
            pass
    col = []
    re, col_list = await G_MysqlSession.fetch_all_and_description(
        f'''select * from  exchange_symbols_contract_referrence''')
    for i in col_list:
        col.append(i[0])
    datas = {}
    for i in re:
        datas[i[0]] = {'exchange': i[1], 'contract_exchange': i[2], 'exchange_other': i[3], 'market': i[4]}
    cu_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    message = f'{cu_time} 合约参考交易所:\n'
    for k, v in result.items():
        valuse = ''
        for i, j in v.items():
            try:
                if str(datas[k][i]) != str(j):
                    pass
                if i == 'exchange_other' and str(datas[k][i]) != str(j):
                    message += f' 交易对: {k} 可参考交易所: {str(datas[k][i])} --> {str(j)}  \n'
            except:
                sql = f'''INSERT ignore INTO exchange_symbols_contract_referrence (symbol,exchange,contract_exchange,exchange_other,market) VALUES ("{k}","{v['exchange']}","{v['contract_exchange']}","{v.get('exchange_other', [])}","{v.get('market', [])}")'''
                await G_MysqlSession.insert(sql)
            valuse += f'{i}="{j}",'
        valuse = valuse[:-1]
        update_sql = f'''UPDATE exchange_symbols_contract_referrence SET {valuse} WHERE symbol='{k}' '''
        await G_MysqlSession.insert(update_sql)
    if message != f'{cu_time} 合约参考交易所:\n':
        send_telegram(message, 'dw_info')
    await heartbeat.i_live_well("合约外部可对标交易所", 60 * 17 * 2, 66)


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main_excu())
