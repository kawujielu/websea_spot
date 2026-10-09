import traceback

import requests
from libs import sendmessage

events = [
    'bb_market', 'hy_market',
    'one_user_position', 'price_range', 'risk_rate', 'zabbix', 'price', 'kline', 'user_deposit_withdrawal',
    'strategy_monitor',
    'bb_transfer', 'bb_freeze', 'bb_depth',
    'hy_transfer', 'hy_freeze', 'hy_depth', 'hb_open_close_amount', 'hy_hedge_position_diff',
    # 'bb5to10min', 'bb1to2h', 'hy1h', 'hy1d',
    'bb10min', 'bb1h', 'hy2h', 'hy1d', 'hy10m',
    'hedge', 'threshold', 'profit_loss', 'hy_profit_loss',

]

event_names = [
    '币币做市', '合约做市',
    '单用户持仓', '调整价格区间', '合约风险率', 'zabbix', '对标价格', ' k线', '用户充提',
    '策略成交量',
    '币币划转', '币币冻结', '币币深度',
    '合约划转', '合约冻结', '合约深度', '合约对冲持仓差值', '合约对冲持仓差值',
    # '高频币币5分钟检测最近10分钟', '高频币币1小时检测最近2小时', '高频合约检测最近1小时', '高频合约检测最近1天',
    '高频币币10分钟', '高频币币1小时', '高频合约检测最近1小时', '高频合约检测最近1天', '高频合约检测最近10分钟',
    '对冲订单', '对冲阈值', '盈亏', '合约盈亏',
]
d = {'bb_market': '币币做市',
     'hy_market': '合约做市',
     'one_user_position': '单用户持仓',
     'price_range': '调整价格区间',
     'risk_rate': '合约风险率',
     'zabbix': 'zabbix',
     'price': '对标价格',
     'kline': 'k线',
     # 'hy_kline': '合约k线',
     # 'hy_funding_rate': '合约资金费率',
     'user_deposit_withdrawal': '用户充提',
     'strategy_monitor': '策略成交量',
     'bb_transfer': '币币划转',
     'bb_freeze': '币币冻结', 'bb_depth': '币币深度',
     'hy_transfer': '合约划转', 'hy_freeze': '合约冻结', 'hy_depth': '合约深度',
     'hb_open_close_amount': '合约对冲持仓差值',
     'hy_hedge_position_diff': '合约对冲持仓差值',
     'bb10min': '高频币币10分钟', 'bb1h': '高频币币1小时',
     'hy10m': '高频合约检测最近10分钟', 'hy2h': '高频合约检测最近1小时', 'hy1d': '高频合约检测最近1天',
     'hedge': '对冲订单',
     'threshold': '对冲阈值',
     'threshold_order': '对冲阈值_订单',
     'profit_loss': '盈亏', 'hy_profit_loss': '合约盈亏',
     'redis_price': 'redis价格',
     'hy_liquidate': '爆仓',

     }

a = {
    'hb_open_close_amount': 'hb合约开平仓数量',
    'hy_hedge_position_diff': '合约对冲持仓差值',
    'user_deposit_withdrawal': '用户充提',
}


# 补充两个
# bb_hedge_chart  币币对冲盈亏图
# hy_hedge_chart 合约对冲盈亏图

def get_a_monitor(event_name, msg):
    try:
        msg = msg.replace('\n', '<br>')
        requests.post('http://52.74.21.180:8813/push', {'event_name': event_name, 'msg': msg}, timeout=5)
    except:
        mm = traceback.format_exc()
        message = f'error: Quant_web {event_name} {mm}'
        print(message)
        sendmessage.send_telegram_msg(message, ser='Alarm')


# get_a_monitor(event_name='risk_rate', msg='mess_quant_web')

if __name__ == '__main__':
    # d = dict(zip(events, event_names))
    # print(d)
    for k, v in d.items():
        event_name = v
        event = k
        msg = f"{event=} {event_name=}"
        get_a_monitor(event, msg)
        print(msg)
