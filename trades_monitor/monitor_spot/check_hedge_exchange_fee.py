import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scaffold.mysql import G_MysqlSession
import asyncio
from libs.send_tglegram_msg import send_telegram_async, push_msg


# 检测websea交易所与外部交易所差值
async def check_hedge_fee():
    msg = 'websea手续费相比对冲交易所手续费差值超过50u, 请注意(1hour/次): \n'
    sql = f' select * from withdraw_deposit_fee'
    result = await G_MysqlSession.fetch_all(sql)
    exchange_fee = {}
    for info in result:
        if info[0] in ['ETH']:
            continue
        hedge_ex = eval(info[1])
        bn_fee = eval(info[3]) if '[' in info[3] else []
        okex_fee = eval(info[4]) if '[' in info[4] else []
        gate_fee = eval(info[5]) if '[' in info[5] else []
        mxc_fee = eval(info[6]) if '[' in info[6] else []
        websea_fee = eval(info[7]) if '[' in info[7] else []
        bitget_fee = eval(info[8]) if '[' in info[8] else []
        exchange_fee[info[0]] = {'hedge_ex': hedge_ex, 'bn': bn_fee, 'okex': okex_fee, 'gate': gate_fee, 'mxc': mxc_fee,
                                 'websea': websea_fee, 'bitget': bitget_fee}
    for k, fee_info in exchange_fee.items():
        hedge_ex = fee_info['hedge_ex']
        websea_fee = fee_info['websea']
        for ex in hedge_ex:
            hedge_chain = fee_info[ex]
            for h_chain in hedge_chain:
                h_chain_name = h_chain.split(':')[0]
                h_fee = h_chain.split(':')[1]
                for i in websea_fee:
                    if '暂停' in i:
                        continue
                    w_chain_name = i.split(':')[0]
                    w_fee = i.split(':')[1]
                    if h_chain_name == w_chain_name:
                        w_fee = float(w_fee.split('(')[1].split('u')[0])
                        h_fee = float(h_fee.split('(')[1].split('u')[0])
                        diff = round(h_fee - w_fee, 2)
                        if diff >= 50:
                            msg += f'【{k}】websea手续费: {i}, {ex}手续费: {h_chain},【差值{diff}u】\n'
    print(msg)
    if msg != 'websea手续费相比对冲交易所手续费差值超过50u, 请注意(1hour/次): \n':
        msg_li = [msg[i:i + 4000] for i in range(0, len(msg), 4000)]
        for send_msg in msg_li:
            await send_telegram_async(send_msg, 'warning')
        await push_msg('w_d_fee', msg)
    else:
        await push_msg('w_d_fee', '')


if __name__ == '__main__':
    asyncio.run(check_hedge_fee())
