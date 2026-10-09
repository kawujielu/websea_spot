import asyncio
import time
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.database.getmysql import G_MysqlSession
from libs import heartbeat, sendmessage
from libs import get_time

GAP_THRESHOLD_AMOUNT = {
    "BTC": 0.000326 * 1.2,
    "ORDI": 1.23 * 1.2,
    "POL": 156 * 1.2,
    "APT": 12,
    "BNB": 10,
}

async def get_currency_gap(ts):
    tm = get_time.ATime().timestamp_to_timearray(ts)
    cur_err_currency_list = []
    get_latest_time_sql = f"select time from hedge where `time` < '{tm}' order by `time` desc limit 1;"
    print(get_latest_time_sql)
    res = await G_MysqlSession.fetch_one(get_latest_time_sql)
    print(res)
    get_latest_time = res[0]
    get_gap_sql = f"SELECT id, currency, (`对冲头寸` - `对冲池`) * `rate|U` AS gap_usdt, (`对冲头寸` - `对冲池`) AS gap FROM hedge where time = '{get_latest_time}';"
    print(get_gap_sql)
    res, _ = await G_MysqlSession.fetch_all(get_gap_sql)
    print(res)
    for r in res:
        gap_u = r[2]
        gap = r[3]
        currency = r[1]
        if currency in ["USDT"]:
            continue
        if currency in GAP_THRESHOLD_AMOUNT:
            if abs(gap_u) > 5 and abs(gap) > GAP_THRESHOLD_AMOUNT[currency]:
                cur_err_currency_list.append(currency)
        else:
            if abs(gap_u) > 5:
                cur_err_currency_list.append(currency)

    return cur_err_currency_list


async def main():

    cur_gap_res = await get_currency_gap(time.time())
    latest_gap_res = await get_currency_gap(time.time()-3600*8)
    err_currency_list = list(set(cur_gap_res) & set(latest_gap_res))
    if err_currency_list:
        sendmessage.send_telegram_msg(f"对冲敞口对冲&钱包统计监控 {str(err_currency_list)[:500]}", ser='Alarm')

    await heartbeat.i_live_well(server='对冲敞口对冲&钱包统计监控', frequency=60 * 60, index=33)


if __name__ == "__main__":
    asyncio.run(main())