import traceback
import asyncio
import json
import time
import sys
import ujson
from decimal import Decimal
from typing import Tuple
import loguru
from libs.recode_msg import recode_error_msg
from scaffold.mysql import Hedge_MysqlSession
from many_configs import global_variable
from core_external.external_asset import external_asset_position_instance
from many_configs.base_config import SwapCode

G_approved_status = {}


async def cancel_and_record_order(symbol, orderId, exchange, currency=None):
    # 取消并且记录订单信息到数据库  todo hyy

    # 撤销订单
    cancel_order_info = await global_variable.EXTERNAL_EXCHANGE_INSTANCES[exchange].cancel_order(symbol=symbol,
                                                                                                 orderId=orderId)
    loguru.logger.info(f'cancel_order_info: {exchange} {symbol} {cancel_order_info}')
    await asyncio.sleep(2)
    # 查询订单
    order_info = await global_variable.EXTERNAL_EXCHANGE_INSTANCES[exchange].get_orders(symbol=symbol,
                                                                                        orderId=orderId)
    loguru.logger.info(f'order_info: {exchange} {symbol} {order_info}')
    # bn code=400 and status:'FILLED','CANCELED'{'content': '{"code":-2011,"msg":"Unknown order sent."}', 'code': 400}
    if order_info.get('status', '') not in ['FILLED', 'CANCELED'] and 'code' in cancel_order_info.keys():
        await recode_error_msg(f"{exchange}-{symbol}-{orderId} {cancel_order_info} 撤单异常", server="spot_hedge")
        return "撤单异常"

    # 更新订单状态
    if order_info:
        # insert_sql = "INSERT INTO orders (exchange,orderId,symbol,status,fillsz) VALUES ('{}','{}','{}','{}','{}') " \
        #              "on duplicate key update " \
        #              "status = values(status)," \
        #              "fillsz = values(fillsz)" \
        #     .format(exchange, orderId, symbol, order_info['status'], order_info['fillsz'])
        insert_sql = f"UPDATE orders SET status = '{order_info['status']}', fillsz = {order_info['fillsz']} " \
                     f"WHERE exchange='{exchange}' and symbol='{symbol}' and orderId = '{orderId}'"
        loguru.logger.info(insert_sql)
        await Hedge_MysqlSession.insert(insert_sql)

    # 查询成交信息
    trades_info = await global_variable.EXTERNAL_EXCHANGE_INSTANCES[exchange].get_trades(symbol=symbol,
                                                                                         orderId=orderId)
    loguru.logger.info(f'trades_info: {exchange} {symbol} {trades_info}')
    if not isinstance(trades_info, list):
        await recode_error_msg(f'{exchange}|{symbol}|{orderId} restful获取成交信息失败 {trades_info}', server="spot_hedge")
    if len(trades_info) >= 1000 or (exchange == "kraken" and len(trades_info) > 30):
        loguru.logger.error(f"{symbol}-{orderId} 获取trades数量超过1000条，可能出现数据不全的问题，请检查！！！！！！！！！！！！！！！")
        await recode_error_msg(f"{exchange}-{symbol}-{orderId} 订单数量{len(trades_info)}超过最大可获取数量， 校验数据", server="send_telegram_important_msg_url")

    if trades_info:
        await external_asset_position_instance.asset_position_collector(trades_info, exchange, currency)
    else:
        ws_sql_name = ['tradeId', 'orderId', 'exchange', 'time', 'currency', 'symbol', 'side', 'price', 'amount', 'fee',
                       'feecoin']
        select_sql = f"select {','.join(ws_sql_name)} from trades_ws where orderId='{orderId}'"
        res = await Hedge_MysqlSession.fetch_all(select_sql)
        if res:
            trades_info = [dict(zip(ws_sql_name, i)) for i in res]
            loguru.logger.info(f'trades_info {trades_info}')
            await external_asset_position_instance.asset_position_collector(trades_info, exchange, currency)


async def cancel_and_create_order(symbol, orderId, side, amount, price, currency, exchange='bn'):
    # 撤单 下单  todo hyy
    # 该接口暂时不使用
    loguru.logger.info(
        f'【{symbol}】cancel and create order {symbol=}, {orderId=}, {side=}, {amount=}, {price=}, {exchange=}')
    order_info, order_id, cancel_status = await global_variable.EXTERNAL_EXCHANGE_INSTANCES[exchange].cancelReplace \
        (symbol=symbol, side=side, amount=amount, price=price, orderId=orderId)

    # 查询订单信息
    loguru.logger.info(f'【{symbol}】get order details')
    for i in range(len(order_info)):
        Id = order_info[i]['orderId']
        order_info_1 = await global_variable.EXTERNAL_EXCHANGE_INSTANCES[exchange].get_orders(symbol=symbol,
                                                                                              orderId=Id)
        order_info[i]['time'] = order_info_1['time']
        order_info[i]['status'] = order_info_1['status']
        order_info[i]['fillsz'] = order_info_1['fillsz']

    # 下单失败，存入数据库
    if not order_id:
        loguru.logger.info(f'【{symbol}】create order failed')
        order_info.append(
            {'exchange': exchange, 'orderId': f'error{exchange}{symbol}{int(time.time())}'.replace('-', ''),
             'symbol': symbol, 'side': side, 'amount': amount, 'price': price, 'status': 'FAILED',
             'time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())), 'fillsz': 0})

    loguru.logger.info(f'【{symbol}】update order status')
    # 更新数据库状态
    insert_sql = "INSERT ignore INTO orders (orderId,exchange,`time`,symbol,side,price,amount,status,fillsz) VALUES " + ','.join(
        f"('{i['orderId']}','{i['exchange']}','{i['time']}','{i['symbol']}','{i['side']}',{i['price']},{i['amount']},'{i['status']}','{i['fillsz']}')"
        for i in order_info) + " on duplicate key update status = values(status), fillsz = values(fillsz)"
    await Hedge_MysqlSession.insert(insert_sql)

    # 查询成交记录
    trades_info = await global_variable.EXTERNAL_EXCHANGE_INSTANCES[exchange].get_trades(symbol=symbol,
                                                                                         orderId=orderId)
    if trades_info:
        await external_asset_position_instance.asset_position_collector(trades_info, exchange, currency)
    else:
        ws_sql_name = ['tradeId', 'orderId', 'exchange', 'time', 'currency', 'symbol', 'side', 'price', 'amount', 'fee',
                       'feecoin']
        select_sql = f"select {','.join(ws_sql_name)} from trades_ws where orderId='{orderId}'"
        res = await Hedge_MysqlSession.fetch_all(select_sql)
        if res:
            trades_info = [dict(zip(ws_sql_name, i)) for i in res]
            await external_asset_position_instance.asset_position_collector(trades_info, exchange, currency)

    return order_id, cancel_status


async def hedge_symbol(symbol, side, amount, price, exchange, currency=None, avg_price=None, is_api=True):
    """
        在这里测试调用各个交易所下单接口，并把数据写到mysql，直接用原生sql语句
        hb,gate 没有模拟盘
    """
    try:
        loguru.logger.info(f'hedge_symbol_before: {exchange} {symbol} ')

        order_info = await global_variable.EXTERNAL_EXCHANGE_INSTANCES[exchange].create_order(symbol=symbol, side=side,
                                                                                              amount=amount, price=price)
        loguru.logger.info(f'hedge_symbol: {exchange} {symbol} {order_info=}')
        msg = f"{exchange} {symbol} {side} {amount=} {price=} 下单结果：{order_info.get('orderId', order_info)}"
        await recode_error_msg(msg, server="spot_hedge_order")

        order = {'exchange': exchange, 'currency': currency, 'symbol': symbol,
                 'side': side, 'amount': amount, 'price': price, 'is_api': is_api, 'avg_price': avg_price}
        if order_info.get('orderId', ''):
            order["orderId"] = order_info['orderId']
            order["status"] = "NEW"
            res = await create_hedge_order(order)
            return order_info['orderId']
        else:
            order["orderId"] = f'error{exchange}{symbol}{int(time.time())}'.replace('-', '')
            order["status"] = "FAILED"
            msg = f"{exchange}-{symbol}-side:{side} amount:{amount} price:{price} 订单信息{order_info} 下单失败",
            res = await create_hedge_order(order)

            await recode_error_msg(msg, server="spot_hedge")
    except Exception as e:
        msg = f"{exchange} {symbol} - {traceback.format_exc()}"
        loguru.logger.error(msg)
        await recode_error_msg(msg, server="spot_hedge")


async def create_hedge_order(order):
    insert_sql = f"""
        INSERT ignore INTO orders (exchange,orderId,currency,symbol,price, side, amount, fillsz, is_api,status,avg_price) 
        VALUES ('{order['exchange']}','{order['orderId']}','{order['currency']}','{order['symbol']}',
                '{order['price']}','{order['side']}','{order['amount']}', '{order.get('fillsz', 0)}', '{order['is_api']}','{order['status']}','{order['avg_price']}')
    """
    await Hedge_MysqlSession.insert(insert_sql)


async def get_dex_currency_hedge_config(currency, chain) -> Tuple[bool, dict]:
    query_sql = "SELECT * from dex_currency_hedge_config WHERE currency='{}' AND chain='{}'".format(currency, chain)
    # coin_infos = await Hedge_MysqlSession.fetch_all(query_sql)
    coin_infos = await Hedge_MysqlSession.fetch_one_column(query_sql)
    if not coin_infos:
        return False, {}
    else:
        return True, coin_infos