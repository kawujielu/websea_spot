import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.send_tglegram_msg import send_telegram_async
from libs import libs_config
import asyncio
from collections import Counter

'''
我们的远程库配置文件， 需要有一个检测， 
1 现货合约刷量对标只需要一个配置了就可以 
2 检测前天说的那个重复配置的问题 
3 检测新增加交易对的时候复制之前的过程中是否有漏改的 主要针对币种
'''
spot_price_symbol = libs_config.PRICE_SYMBOL_CONFIG
spot_config = libs_config.SPOT_CURRENCY_CONFIG
contract_price_symbol = libs_config.CONTRACT_PRICE_SYMBOL_CONFIG
contract_config = libs_config.CONTRACT_CURRENCY_CONFIG


# 现货合约刷量对标只需要一个配置了就可以
async def check_spot_contract_only():
    msg = '！！！紧急, 远程库中合约币种现货已上线，不需重新配置, 请联系相关人员进行修改:\n'
    error_contract_currency = []
    all_spot_currency = list(spot_config.keys())
    for currency, config in contract_config.items():
        if currency in all_spot_currency:
            if config['exchange']:
                error_contract_currency.append(currency)
    if error_contract_currency:
        msg += '合约currency配置: ' + ', '.join(error_contract_currency)
    print(msg)
    if msg != '！！！紧急, 远程库中合约币种现货已上线，不需重新配置, 请联系相关人员进行修改:\n':
        await send_telegram_async(msg, 'warning')


# 检测前天说的那个重复配置的问题
async def check_trades_config():
    msg = '！！！紧急, 远程库交易对配置中存在重复, 请联系相关人员进行修改:\n'
    # 合约
    contract_diff_symbol = Counter(list(contract_config.keys()))
    contract_price_diff_symbol = Counter(list(contract_price_symbol.keys()))
    error_contract_symbols, error_contract_price_symbols = [], []
    for symbol, num in contract_diff_symbol.items():
        if num >= 2:
            error_contract_symbols.append(symbol)
    for symbol, num in contract_price_diff_symbol.items():
        if num >= 2:
            error_contract_price_symbols.append(symbol)
    if error_contract_price_symbols:
        msg += '合约价格服务: ' + ', '.join(error_contract_price_symbols)
    if error_contract_symbols:
        msg += '合约currency配置: ' + ', '.join(error_contract_symbols)
    # 现货
    spot_diff_symbol = Counter(list(spot_config.keys()))
    spot_price_diff_symbol = Counter(list(spot_price_symbol.keys()))
    error_spot_symbols, error_spot_price_symbols = [], []
    for symbol, num in spot_diff_symbol.items():
        if num >= 2:
            error_spot_symbols.append(symbol)
    for symbol, num in spot_price_diff_symbol.items():
        if num >= 2:
            error_spot_price_symbols.append(symbol)
    if error_spot_price_symbols:
        msg += '现货价格服务: ' + ', '.join(error_spot_price_symbols)
    if error_spot_symbols:
        msg += '现货currency配置: ' + ', '.join(error_spot_symbols)
    print(msg)
    if msg != '！！！紧急, 远程库交易对配置中存在重复, 请联系相关人员进行修改:\n':
        await send_telegram_async(msg, 'warning')


# 检测新增加交易对的时候复制之前的过程中是否有漏改的 主要针对币种
async def check_config_error():
    msg = '！！！紧急, 远程库交易对配置存在漏改, 请联系相关人员进行修改:\n'
    # 合约
    error_contract_currency = set()
    for currency, config in contract_config.items():
        for symbol in list(config['ask_bid_percent_spec'].keys()):
            if currency not in symbol:
                error_contract_currency.add(currency)
        for ex, symbol in config['exchange']:
            if currency not in symbol:
                error_contract_currency.add(currency)
    if error_contract_currency:
        msg += '合约currency配置: ' + ', '.join(list(error_contract_currency))
    # 现货
    error_spot_currency = set()
    for currency, config in spot_config.items():
        for symbol in list(config['ask_bid_percent_spec'].keys()):
            if currency not in symbol:
                error_contract_currency.add(currency)
        for symbol in list(config['mean_order_size'].keys()):
            if currency not in symbol:
                error_spot_currency.add(currency)
        for ex, symbol in config['exchange']:
            if currency not in symbol:
                error_spot_currency.add(currency)
    if error_spot_currency:
        msg += '现货currency配置: ' + ', '.join(list(error_spot_currency))
    print(msg)
    if msg != '！！！紧急, 远程库交易对配置存在漏改, 请联系相关人员进行修改:\n':
        await send_telegram_async(msg, 'warning')


async def main():
    await check_spot_contract_only()
    await check_trades_config()
    await check_config_error()


if __name__ == '__main__':
    asyncio.run(main())
