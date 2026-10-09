import asyncio
import datetime

from many_configs.account_config import DEX_ACCOUNT
from scaffold.mysql import Hedge_MysqlSession
from many_configs import global_variable
import loguru
import libs


class ExternalAssetPosition:
    def __init__(self):
        pass

    async def init_position(self):
        sql = "SELECT coin,amount from external_asset_gap ;"
        res = await Hedge_MysqlSession.fetch_all(sql)
        if res:
            for i in res:
                global_variable.EXTERNAL_POSITIONS[i[0]] = i[1]
        loguru.logger.info(f'打印外部敞口 {global_variable.EXTERNAL_POSITIONS}')
        loguru.logger.info("abc_asset_init_position -- ok")

    async def init_wallet(self):
        # 初始化外部钱包-冻结
        tasks = {k: asyncio.create_task(v.wallet_free()) for k, v in
                 global_variable.EXTERNAL_EXCHANGE_INSTANCES.items()}
        # TODO hyy logru
        loguru.logger.info(f'打印外部交易所对象实例{global_variable.EXTERNAL_EXCHANGE_INSTANCES}')
        global_variable.WALLET_EXCHANGE_CURRENCY = {k: await v for k, v in tasks.items()}

    async def asset_position_collector(self, trades_info, exchange, currency):
        # todo 此处相关的exchange全部修改链名称
        async with global_variable.ASYNC_LOCK["external_position"]:
            trades = []
            # ex_name = exchange.split('_')[0]
            for i in trades_info:
                base, quote = i['symbol'].split('-')
                if i['exchange'] in DEX_ACCOUNT:
                    base_amount = float(i['amount']) if i['side'].lower() in ['buy'] else float(i['amount']) * (-1)
                    quote_amount = float(i['quote_amount']) * (-1) if i['side'].lower() in ['buy'] \
                        else float(i['quote_amount'])

                else:
                    base_amount = float(i['amount']) if i['side'].lower() in ['buy'] else float(i['amount']) * (-1)
                    quote_amount = float(i['amount']) * float(i['price']) * (-1) if i['side'].lower() in ['buy'] \
                        else float(i['amount']) * float(i['price'])

                currency_hedge_config = global_variable.SHARE_SYMBOL_HEDGE_CONFIG[currency]['exchanges'][exchange]
                # TODO hyy
                baseAmount, quoteAmount, feeAmount = 0, 0, 0
                pr_amount = libs.spec_symbol_rate_mapping.get(exchange, {}).get(i['symbol'], 1)
                loguru.logger.info(f"{libs.spec_symbol_rate_mapping} -- spec_symbol_rate_mapping")

                # xbo-eth
                # currency_hedge_config['hedge_currency'] 表示外部对冲币的名字，可能跟abc交易所名字不一样
                if currency_hedge_config['hedge_currency'] == base:
                    base_amount = base_amount / pr_amount
                    global_variable.EXTERNAL_POSITIONS[currency] = global_variable.EXTERNAL_POSITIONS.get(currency,
                                                                                                          0) + base_amount
                    global_variable.EXTERNAL_POSITIONS[quote] = global_variable.EXTERNAL_POSITIONS.get(quote,
                                                                                                       0) + quote_amount
                    baseAmount = global_variable.EXTERNAL_POSITIONS[currency]
                    quoteAmount = global_variable.EXTERNAL_POSITIONS[quote]
                # eth-xno
                if currency_hedge_config['hedge_currency'] == quote:
                    quote_amount = quote_amount / pr_amount
                    global_variable.EXTERNAL_POSITIONS[base] = global_variable.EXTERNAL_POSITIONS.get(base,
                                                                                                      0) + base_amount
                    global_variable.EXTERNAL_POSITIONS[currency] = global_variable.EXTERNAL_POSITIONS.get(currency,
                                                                                                          0) + quote_amount
                    baseAmount = global_variable.EXTERNAL_POSITIONS[base]
                    quoteAmount = global_variable.EXTERNAL_POSITIONS[currency]

                if i['feecoin'] == currency_hedge_config['hedge_currency']:
                    fee = float(i['fee']) / pr_amount
                    global_variable.EXTERNAL_POSITIONS[currency] = \
                        global_variable.EXTERNAL_POSITIONS.get(currency, 0) - fee
                    feeAmount = global_variable.EXTERNAL_POSITIONS[currency]
                else:
                    global_variable.EXTERNAL_POSITIONS[i['feecoin']] = \
                        global_variable.EXTERNAL_POSITIONS.get(i['feecoin'], 0) - float(i['fee'])
                    feeAmount = global_variable.EXTERNAL_POSITIONS[i['feecoin']]

                trades.append(
                    f"('{i['tradeId']}','{i['orderId']}','{i['exchange']}','{currency}','{i['symbol']}','{i['side']}',{i['price']},{i['amount']},{i['fee']},'{i['feecoin']}',{baseAmount},{quoteAmount},{feeAmount})")

            loguru.logger.info(f'EXTERNAL_POSITIONS {global_variable.EXTERNAL_POSITIONS}')
            if trades_info:
                # 更新成交订单
                insert_sql = "INSERT ignore INTO trades (tradeId,orderId,exchange,currency,symbol,side,price,amount,fee,feecoin,base_amount,quote_amount,fee_amount) VALUES " + ','.join(
                    trades)
                # TODO hyy 异常处理
                await Hedge_MysqlSession.insert(insert_sql)
                values = ','.join([str((k, v)) for k, v in global_variable.EXTERNAL_POSITIONS.items()])
                sql = f'INSERT ignore INTO external_asset_gap(coin,amount) VALUES {values} on duplicate key update amount = values(amount)'
                await Hedge_MysqlSession.insert(sql)
                sql_all = f'INSERT ignore INTO external_asset_gap_all(coin,amount) VALUES {values}'
                await Hedge_MysqlSession.insert(sql_all)

    # async def run(self):
    #     while True:
    #         if not global_variable.EXTERNAL_POSITIONS:
    #             await self.init_position()
    #         await asyncio.sleep(10)


external_asset_position_instance = ExternalAssetPosition()
