import traceback
import asyncio
import ujson
import loguru
import time
import tokenlib
from sanic import Sanic
from sanic.response import json as sanic_json
from sanic.views import HTTPMethodView
from many_configs import base_config, global_variable
from scaffold.mysql import Hedge_MysqlSession
from pymysql.converters import escape_string
from core_external.order import hedge_symbol, cancel_and_record_order
from importlib import reload
import libs


app = Sanic("spot_paddington")
TOKEN_SECRET = 'MANAGER_SECRET'


async def add_log(user, method, action):
    insert_sql = f"INSERT ignore INTO hedge_log (`user`,method,`action`) VALUES ('{user}','{method}','{action}')"
    await Hedge_MysqlSession.insert(insert_sql)


# 登录中间件
@app.middleware("request")
async def get_request_middleware(request):
    res = {
        "code": 0,
        "msg": "success",
        "data": ""
    }
    auth_token = request.headers.get("Authorization", None)
    if auth_token:
        try:
            # 进行验证
            tokens = auth_token.split(" ")
            user_data = tokenlib.parse_token(tokens[0], secret=TOKEN_SECRET, now=int(time.time()))
            request.args["user"] = user_data['user']
        except Exception as e:
            loguru.logger.info(f"{auth_token} 授权失败")

            res.update(code=0, msg="授权失败")
            return sanic_json(res)
    else:
        res.update(code=0, msg="授权失败")
        return sanic_json(res)

    method = request.method
    # get 请求不记录，防止数据太多
    if method != 'GET':
        action = ujson.loads(request.body.decode("utf-8").replace("'", '"'))
        action = escape_string(ujson.dumps(action))
        await add_log(user_data['user'], f'{method}', f'{action}')


class HedgeView(HTTPMethodView):
    async def get(self, request):
        return sanic_json({
            "code": 0,
            "msg": "success",
            "data": global_variable.SHARE_SYMBOL_HEDGE_CONFIG.data
        })

    async def post(self, request):
        manager_hedge_config = ujson.loads(request.body.decode("utf-8").replace("'", '"'))
        command = []
        for currency, hedge_config in manager_hedge_config.items():
            hedge_config = escape_string(ujson.dumps(hedge_config))
            command.append(f'("{currency}", "{hedge_config}")')
        try:
            insert_sql = "INSERT ignore INTO hedge_config (currency,config) VALUES " + ','.join(command)
            await Hedge_MysqlSession.insert_sql(insert_sql)
        except Exception as e:
            return sanic_json({
                "code": 400,
                "msg": f"insert data failed: {e}",
            })

        for currency, hedge_config in manager_hedge_config.items():
            global_variable.SHARE_SYMBOL_HEDGE_CONFIG[currency] = hedge_config
        reload(libs)
        return sanic_json({
            "code": 0,
            "msg": "success",
        })

    async def patch(self, request):
        """
        1 同post，修改档币种信息整条传过来，global_variable.SYMBOL_HEDGE_CONFIG 赋值
        2 计算出这个币有没有修改对冲交易所，增减订阅档交易对
        """
        manager_hedge_config = ujson.loads(request.body.decode("utf-8").replace("'", '"'))
        command = []
        for currency, hedge_config in manager_hedge_config.items():
            hedge_config = escape_string(ujson.dumps(hedge_config))
            command.append(f"SET config='{hedge_config}' WHERE currency='{currency}'")
        try:
            update_sql = f"UPDATE hedge_config " + ','.join(command)
            await Hedge_MysqlSession.insert_sql(update_sql)
        except Exception as e:
            return sanic_json({
                "code": 400,
                "msg": f"update sql failed:'{e}'",
            })

        for currency, hedge_config in manager_hedge_config.items():
            global_variable.SHARE_SYMBOL_HEDGE_CONFIG[currency] = hedge_config
        return sanic_json({
            "code": 0,
            "msg": "success",
            "data": global_variable.SHARE_SYMBOL_HEDGE_CONFIG.data
        })

    async def delete(self, request):
        '''
        request : {'currency':['BTC']}
        '''
        manager_hedge_config = ujson.loads(request.body.decode("utf-8").replace("'", '"'))
        delete_currency = manager_hedge_config['currency']
        delete_currency = [f"currency='{currency}'" for currency in delete_currency]
        if delete_currency:
            try:
                delete_sql = "DELETE FROM hedge_config WHERE " + ' or '.join(delete_currency)
                await Hedge_MysqlSession.insert_sql(delete_sql)
            except Exception as e:
                return sanic_json({
                    "code": 400,
                    "msg": f"delete sql failed:'{e}'",
                })

        for currency in manager_hedge_config['currency']:
            global_variable.SHARE_SYMBOL_HEDGE_CONFIG.pop(currency)
        return sanic_json({
            "code": 0,
            "msg": "success",
            "data": global_variable.SHARE_SYMBOL_HEDGE_CONFIG
        })


app.add_route(HedgeView.as_view(), "/api/config")


@app.post("/service")
async def service_status(request):
    service_status = ujson.loads(request.body.decode("utf-8").replace("'", '"'))
    global_variable.SERVICE_STATUS = service_status['status']
    return sanic_json({
        "code": 0,
        "msg": "success",
        "data": global_variable.SERVICE_STATUS,
    })


@app.post("/dex_service")
async def dex_service(request):
    service_status = ujson.loads(request.body.decode("utf-8").replace("'", '"'))
    global_variable.DEX_ACCOUNT_OR_CURRENCY_STATUS = service_status
    return sanic_json({
        "code": 0,
        "msg": "success",
        "data": global_variable.DEX_ACCOUNT_OR_CURRENCY_STATUS,
    })


@app.get("/service")
async def service_status(request):
    return sanic_json({
        "code": 0,
        "msg": "success",
        "data": global_variable.SERVICE_STATUS
    })


@app.post("/service/faster")
async def faster_hedge_status(request):
    faster_status = ujson.loads(request.body.decode("utf-8").replace("'", '"'))
    global_variable.FASTER_HEDGE = faster_status['faster_hedge']
    return sanic_json({
        "code": 0,
        "msg": "success",
        "data": global_variable.FASTER_HEDGE,
    })


@app.get("/service/faster")
async def faster_hedge_status(request):
    return sanic_json({
        "code": 0,
        "msg": "success",
        "data": global_variable.FASTER_HEDGE
    })


@app.get("/dex_service")
async def dex_service(request):
    return sanic_json({
        "code": 0,
        "msg": "success",
        "data": global_variable.DEX_ACCOUNT_OR_CURRENCY_STATUS
    })


@app.post("/create_order")
async def create_order(request):
    order_config = ujson.loads(request.body.decode("utf-8").replace("'", '"'))
    symbol = order_config['symbol']
    side = order_config['side']
    amount = float(order_config['amount'])
    price = float(order_config['price'])
    exchange = order_config['exchange']
    currency = order_config['currency']
    print(symbol, side, amount, price, exchange, currency)
    try:
        order_id = await hedge_symbol(symbol=symbol, side=side, amount=amount, price=price, exchange=exchange,
                                      currency=currency, is_api=False)
        print('create order', order_id)
        if order_id is None:
            return sanic_json({
                "code": 400,
                "msg": "下单失败",
                "data": {'orderId': '', 'exchange': '', 'symbol': '', 'currency': ''}
            })
        else:
            return sanic_json({
                "code": 0,
                "msg": "下单成功",
                "data": {'orderId': order_id, 'exchange': exchange, 'symbol': symbol, 'currency': currency}
            })
    except Exception as e:
        return sanic_json({
            "code": 400,
            "msg": "下单接口异常",
            "data": {'orderId': '', 'exchange': '', 'symbol': '', 'currency': ''}
        })


@app.post("/cancel_order")
async def cancel_order(request):
    order_config = ujson.loads(request.body.decode("utf-8").replace("'", '"'))
    symbol = order_config['symbol']
    currency = order_config['currency']
    exchange = order_config['exchange']
    orderId = order_config['order_id']
    print(symbol, currency, exchange, orderId)
    try:
        res = await cancel_and_record_order(symbol=symbol, orderId=orderId, exchange=exchange, currency=currency)
        print('cancel order', res)
        if res is None:
            return sanic_json({
                "code": 0,
                "msg": "撤单正常"
            })
        else:
            return sanic_json({
                "code": 400,
                "msg": "撤单异常"
            })
    except Exception as e:
        loguru.logger.error(f"{traceback.format_exc()}")
        return sanic_json({
            "code": 400,
            "msg": "撤单接口异常错误"
        })


sanic_app = app.create_server(host=base_config.SANIC_HOST, port=8004,
                              return_asyncio_server=True, debug=True)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(sanic_app)
    loop.run_forever()
