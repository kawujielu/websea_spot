import ccxt
import asyncio
import os, sys
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.infor_hedge_contract import config_con_exchange
from libs import heartbeat, sendmessage

PRO = 0.5
fetch_timeout = 5 * 60


async def get_position():

    # await heartbeat.i_live_well(server='合约对冲账户信息', frequency=fetch_timeout * 2.1, index=33)
    # asyncio.sleep(60)
    message = ""
    for ex, v in config_con_exchange['hedge'].items():
        msg = ""
        ccxtname = v['ccxtname']
        apikey = v['apikey']
        res = getattr(ccxt, ccxtname)(apikey).fapiPrivateV2GetAccount()
        marginBalance = 0
        maintMargin = []
        for i in res['assets']:
            if i['asset'] == 'USDT':
                marginBalance += float(i['marginBalance'])  # 保证金余额
        for i in res['positions']:
            if float(i['positionAmt']):
                # 保证金比率 ＝ 维持保证金 / 保证金余额。你的持仓将在保证金比率达到 100% 时遭到强平。
                # "symbol": "BTCUSDT",  // 交易对
                # "initialMargin": "0",   // 当前所需起始保证金(基于最新标记价格)
                # "maintMargin": "0", //维持保证金
                # "unrealizedProfit": "0.00000000",  // 持仓未实现盈亏
                # "positionInitialMargin": "0",  // 持仓所需起始保证金(基于最新标记价格)
                # "openOrderInitialMargin": "0",  // 当前挂单所需起始保证金(基于最新标记价格)
                # "leverage": "100",  // 杠杆倍率
                # "isolated": true,  // 是否是逐仓模式
                # "entryPrice": "0.00000",  // 持仓成本价
                # "maxNotional": "250000",  // 当前杠杆下用户可用的最大名义价值
                # "bidNotional": "0",  // 买单净值，忽略
                # "askNotional": "0",  // 卖单净值，忽略
                # "positionSide": "BOTH",  // 持仓方向
                # "positionAmt": "0",      // 持仓数量
                # "updateTime": 0         // 更新时间
                symbol = i['symbol']
                positionSide = i['positionSide']  # 持仓方向
                positionAmt = i['positionAmt']  # 持仓数量
                unrealizedProfit = i['unrealizedProfit']  # 持仓未实现盈亏
                maintmargin = float(i['maintMargin'])  # 维持保证金
                maintMargin.append(maintmargin)
                msg += f"         ●  {symbol} 数量:{positionAmt} 未实现盈亏:{unrealizedProfit}\n"

        # marginpro = sum(maintMargin) / marginBalance  # 保证金比率 ＝ 维持保证金 / 保证金余额。你的持仓将在保证金比率达到 100% 时遭到强平。
        if maintMargin and marginBalance:
            marginpro = sum(maintMargin) / marginBalance
            if marginpro < PRO:
                message_marginpro = f"*{ex}*  保证金比率:{round(marginpro * 100, 2)}%\n"
            else:
                message_marginpro = f"*{ex}*  🩸🩸🩸保证金比率:{round(marginpro * 100, 2)}%\n"
        else:
            message_marginpro = ""
        if msg or message_marginpro:
            message += f"{message_marginpro}{msg}\n"

    if message:
        sendmessage.send_telegram_msg_mdv2(message=f"*合约对冲信息({int(fetch_timeout / 60)}min/次)*\n{message}", ser='hedge_contract')

    await heartbeat.i_live_well(server='合约对冲账户信息', frequency=fetch_timeout * 2.1, index=33)


async def run():
    while True:
        try:
            await get_position()
        except:
            mm = traceback.format_exc()
            sendmessage.send_telegram_msg(f'合约对冲账户信息\n{mm}', ser='Alarm')
        finally:
            await asyncio.sleep(fetch_timeout)


if __name__ == '__main__':
    asyncio.run(run())
