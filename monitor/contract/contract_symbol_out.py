import asyncio
from exchange.restful_api.abc_contract import AApi
from config.infor_contract import contract_account
from loguru import logger
from contract.contract_setting import get_trade


async def get_out_symbols():
    # 撤销订单
    # 查询当前委托
    # 查询仓位
    # 下单
    symbol = 'RNDR-USDT'
    for s, v in contract_account.items():
        apikey = v['apikey']
        ao = AApi(**{'token': apikey['token'], 'secret_key': apikey['sk']})

        currentlist = await ao.currentList(symbol, )
        # logger.info(f"{symbol}|{s} {currentlist=}")
        status = [i['status'] for i in currentlist['result']]
        order_ids = [i['order_id'] for i in currentlist['result']]
        logger.info(f"{symbol}|{s} {len(order_ids)}{status=}{order_ids=}")
        if order_ids:
            cancel_orders = await ao.cancel(symbol, order_ids)
            logger.info(f"{symbol}|{s} {cancel_orders=}")
            currentlist = await ao.currentList(symbol, )
            logger.info(f"{symbol}|{s} {currentlist=}")
            if currentlist['result']:
                break

    price = get_trade([symbol])[symbol]

    for s, v in contract_account.items():
        apikey = v['apikey']
        ao = AApi(**{'token': apikey['token'], 'secret_key': apikey['sk']})
        position = await ao.position_contract(symbol, )
        # logger.info(f"{symbol}|{s} {position=}")
        for i in position['result']:
            _type = i["type"]  # "type": 1多仓 2空仓
            amount = int(i['amount'])
            lever_rate = i['lever_rate']
            is_full = i['is_full']
            side = 'sell-limit' if i["type"] == 1 else 'buy-limit'
            logger.info(f"{symbol}|{s} {i} ")

            res = await ao.contract_add(symbol, side=side, amount=amount, price=price, lever_rate=lever_rate, contract_type="close", is_full=is_full)
            logger.info(f"{symbol}|{s} {res=} ")


if __name__ == "__main__":
    asyncio.run(get_out_symbols())
