import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from exchanges.restful_api.abc_spot import AApi
from exchanges.restful_api.abc_contract import AbcApi
from libs import libs_account, libs_config
import asyncio

libs_account = libs_account.account


async def get_symbols():
    websea_instance = AApi(token='cb95edcac135b5a28ed76233abca5b00', secret_key='t8leukegp3t487kzj9xf')
    re = await websea_instance.symbols()
    res = re['result']
    symbols = [i['symbol'] for i in res]
    return symbols


async def spot_order_list_error():
    symbols_config = libs_config.SPOT_CURRENCY_CONFIG
    symbols = []
    for k, v in symbols_config.items():
        for i in v['zone']:
            symbols.append(k + '-' + i)
    for symbol in symbols:
        near_strategy_account = [
            {'token': libs_account["maker_near"]["token"], 'secret_key': libs_account["maker_near"]["sk"]},
            {'token': libs_account["maker_near_second"]["token"],
             'secret_key': libs_account["maker_near_second"]["sk"]}, ]  # maker_near
        depth_strategy_account = [
            {"token": libs_account["maker_depth"]["token"], "secret_key": libs_account["maker_depth"]["sk"]},
            {"token": libs_account["maker_depth_second"]["token"],
             "secret_key": libs_account["maker_depth_second"]["sk"]},
        ]  # maker_depth
        defense_strategy_account = [
            {'token': libs_account["maker_defense"]["token"], 'secret_key': libs_account["maker_defense"]["sk"]},
            {'token': libs_account["maker_defense_second"]["token"],
             'secret_key': libs_account["maker_defense_second"]["sk"]},

        ]  # maker_defense
        for i in near_strategy_account + depth_strategy_account + defense_strategy_account:
            if i['token'] and i['secret_key']:
                websea_instance = AApi(token=i['token'], secret_key=i['secret_key'])
                re = await websea_instance.current_list_status_cancel(symbol=symbol, number=1000)
                print(re)


async def contract_order_list_error():
    symbols_config = libs_config.CONTRACT_CURRENCY_CONFIG
    symbols = []
    for k, v in symbols_config.items():
        for i in v['zone']:
            symbols.append(k + '-' + i)
    for symbol in symbols:
        near_strategy_account = [
            {
                'token': libs_account["contract_near"]["token"],
                'secret_key': libs_account["contract_near"]["sk"]
            },
            {
                'token': libs_account["contract_near"]["token"],
                'secret_key': libs_account["contract_near"]["sk"]
            },
            {
                'token': libs_account["contract_near_second"]["token"],
                'secret_key': libs_account["contract_near_second"]["sk"]
            },
            {
                'token': libs_account["aq_contract_near"]["token"],
                'secret_key': libs_account["aq_contract_near"]["sk"]
            },
            {
                'token': libs_account["aq_contract_near_second"]["token"],
                'secret_key': libs_account["aq_contract_near_second"]["sk"]
            },

        ]  # maker_near
        depth_strategy_account = [
            {
                "token": libs_account["contract_depth"]["token"],
                "secret_key": libs_account["contract_depth"]["sk"]
            },
            {
                "token": libs_account["contract_depth"]["token"],
                "secret_key": libs_account["contract_depth"]["sk"]
            },
            {
                "token": libs_account["contract_depth_second"]["token"],
                "secret_key": libs_account["contract_depth_second"]["sk"]
            },
            {
                "token": libs_account["aq_contract_depth"]["token"],
                "secret_key": libs_account["aq_contract_depth"]["sk"]
            },
            {
                "token": libs_account["aq_contract_depth_second"]["token"],
                "secret_key": libs_account["aq_contract_depth_second"]["sk"]
            },
        ]  # maker_depth
        defense_strategy_account = [
            {
                'token': libs_account["contract_defense"]["token"],
                'secret_key': libs_account["contract_defense"]["sk"]
            },
            {
                'token': libs_account["contract_defense"]["token"],
                'secret_key': libs_account["contract_defense"]["sk"]
            },
            {
                'token': libs_account["contract_defense_second"]["token"],
                'secret_key': libs_account["contract_defense_second"]["sk"]
            },
            {
                'token': libs_account["aq_contract_defense"]["token"],
                'secret_key': libs_account["aq_contract_defense"]["sk"]
            },
            {
                'token': libs_account["aq_contract_defense_second"]["token"],
                'secret_key': libs_account["aq_contract_defense_second"]["sk"]
            },

        ]  # maker_defense
        for i in near_strategy_account + depth_strategy_account + defense_strategy_account:
            if i['token'] and i['secret_key']:
                websea_instance = AbcApi(token=i['token'], secret_key=i['secret_key'])
                re = await websea_instance.contract_current_cancel(symbol=symbol, number=1000)
                print(re)


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(contract_order_list_error())
