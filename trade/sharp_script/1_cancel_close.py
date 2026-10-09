from many_configs.abc_config import contract_delisting_accounts, contract_close_accounts
import asyncio
import sys
import requests
import json
import traceback
from libs import libs_price


# 获取交易对价格精度
def get_contract_precision(contract_host="https://coqv.websea.work"):
    condition_url = contract_host + "/qapi-v1/symbol/precision"

    try:
        res = requests.get(condition_url, timeout=2, verify=False)
        if res.status_code == 200:
            symbols_contract_condition = json.loads(res.text)["result"]
            return symbols_contract_condition
        else:
            print("获取失败，contract precision 将使用默认值", res)
    except BaseException as e:
        print("合约精度获取失败! contract precision 将使用默认值: precision error", e, traceback.format_exc())
    try:
        default_contract_precision = libs_price.get_precision_config(name='contract_redis_precision')
        symbols_contract_condition = default_contract_precision
    except BaseException as e:
        print("合约精度从redis获取失败！precision error", e, traceback.format_exc())
        symbols_contract_condition = {}

    return symbols_contract_condition


SYMBOLS_CONTRACT_CONDITION = get_contract_precision()

'''
下架时间后台开启下架交易对不展示
关闭做市和盘口 不开仓不挂单； 
量化撤单； 
查询当前的持仓；根据持仓挂对手盘，价格和数量一致；
检查多空平仓完毕
关闭交易 后台下架合约交易对
'''


async def get_position(account, symbol):
    res = await account.contract_position(symbol)
    positions = res.get("result", [])
    long, short = 0, 0
    for position in positions:
        position_type = position["type"]
        print(position)
        position_amount = float(float(position["avail_amount"]))
        if position_type == 2:  # 空仓
            short += position_amount
        elif position_type == 1:  # 多仓
            long += position_amount
    return short, long


async def cancel_orders(symbol):
    for account in contract_delisting_accounts:
        cur_token = account._token_
        r = await account.contract_cancel(symbol=symbol)
        print("cancel_orders >>>>>>>>>>>>>", r, symbol)
    for account in contract_delisting_accounts:
        res = await account.contract_current_list(symbol=symbol)
        if res['result']:
            print('撤单异常', res)
            return


async def contract_delisting(symbol, price):
    # 撤销订单
    await cancel_orders(symbol)
    return 
    # 平仓
    face_value = float(SYMBOLS_CONTRACT_CONDITION[symbol].get("faceValue"))
    for account in contract_delisting_accounts:
        cur_token = account._token_
        short, long = await get_position(account, symbol)
        r = 5
        short = short / r
        long = long / r
        if short:  # 平空
            res = await account.contract_add(symbol, 'buy-limit', amount=short * face_value, price=price,
                                       contract_type='close')
            print('-----------short ', cur_token, short, res)
        if long:  # 平多
            res = await account.contract_add(symbol, 'sell-limit', amount=long * face_value, price=price,
                                       contract_type='close')
            print('-----------long', cur_token, long, res)
    # check 仓位是否全平
    total_long, total_short = 0, 0
    for account in contract_close_accounts: #contract_delisting_accounts:
        cur_token = account._token_
        short, long = await get_position(account, symbol)
        if short or long:
            print(account._token_, short, long)
        total_long += long
        total_short += short
    if total_short + total_long == 0:
        print(symbol, '平仓完成')
    else:
        print(symbol, '平仓出错', total_long, total_short)

async def abc_delisting(symbols_info):
    for symbol, price in symbols_info:
        await contract_delisting(symbol, price)

if __name__ == '__main__':
    symbols_info = [('BTC-USDT', None), ('ETH-USDT', None), ('ADA-USDT', None)]
    asyncio.run(abc_delisting(symbols_info))

