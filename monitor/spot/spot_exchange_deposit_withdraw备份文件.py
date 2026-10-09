import os, sys, asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import infor_load
from libs.database.getmysql import G_MysqlSession, Hedge_MysqlSession
from spot.spot_setting import getRateUsdt

# AGIX 头寸:sell 62.33543 (价值27FET,1AGIX=0.433350FET），bn当前值：294（127FET）
# OCEAN ： 头寸0.9190793928564176 (价值0.4FET ,1OCEAN=0.433226FET）。bn当前值：220 （95.3FET)
# 因为AGIX对冲没有平掉，所以把头寸转移到手续费统计，避免修改成交数以及对冲头寸等数据
REDUCE = {'FET': 27}


async def get_fee_asset_gap():
    ts = []
    asset_gap = {}
    sql = """SELECT coin,amount,generation_time from fee_asset_gap """
    res, title = await Hedge_MysqlSession.fetch_all(sql=sql)

    for i in res:
        coin, amount, time = i
        asset_gap[coin] = asset_gap.get(coin, 0) + amount
        ts.append(time)

    start_time = max(ts) if ts else None
    return start_time, asset_gap


async def get_deposit_withdraw_fee():
    # start_ts, asset_gap = await get_fee_asset_gap()
    # now_time = (datetime.now() + timedelta(minutes=-10)).strftime('%Y-%m-%d %H:%M:%S')
    # # now_time = (datetime.now() + timedelta(days=-1)).strftime('%Y-%m-%d %H:%M:%S')
    # ts = []
    # if start_ts:
    #     time_sql = f"""'{now_time}'>`time` and `time`>'{start_ts}' """
    #     ts.append(str(start_ts))
    # else:
    #     time_sql = f"""'{now_time}'>`time` """
    rate = await getRateUsdt()

    # sql = f"""SELECT currency ,sum(fee) fee,time,exchange from exchange_deposit_withdraw WHERE `status1` in ("已确认","已通过","提现完成","成功","完成","入账成功","提现成功") GROUP BY currency,time,exchange ORDER BY time ASC"""
    sql = f"""SELECT currency ,sum(fee) fee,time,exchange from exchange_deposit_withdraw WHERE (`status1` in ("已确认","已通过","提现完成","成功","完成","入账成功","提现成功")) or (`status1` in ("打包中") and LENGTH(`hash`)>0) GROUP BY currency,time,exchange ORDER BY time ASC"""
    results, title = await G_MysqlSession.fetch_all(sql=sql)
    spec_symbol_rate_mapping_currency_ex = {}
    for ex, i in infor_load.spec_symbol_rate_mapping_currency.items():
        spec_symbol_rate_mapping_currency_ex[ex] = {}
        for curr, v in i.items():
            spec_symbol_rate_mapping_currency_ex[ex][v['name']] = {'name': curr, 'pr': 1 / v['pr']}
    asset_gap = {}
    ts = []
    if results:
        for i in results:
            curr, amount, time, ex = i
            d = spec_symbol_rate_mapping_currency_ex.get(ex, {}).get(curr, {})
            coin = d.get('name', curr)
            pr = d.get('pr', 1)
            asset_gap[coin] = asset_gap.get(coin, 0) + amount * pr * (-1)
            ts.append(str(time))
        generation_time = max(ts)
        for coin, v in REDUCE.items():
            asset_gap[coin] = asset_gap.get(coin, 0) + v

        title = ",".join(['coin', 'amount', 'generation_time', 'rate', 'coin_u'])
        values = ",".join([str(tuple([coin, amount, generation_time, rate.get(coin, 0), amount * rate.get(coin, 0)])) for coin, amount in asset_gap.items()])

        sql = f"insert ignore into fee_asset_gap ({title}) " \
              f"values {values}" \
              f"on duplicate key update " \
              f"coin = values (coin)," \
              f"amount = values (amount)," \
              f"rate = values (rate)," \
              f"coin_u = values (coin_u)," \
              f"generation_time = values (generation_time)"
        await Hedge_MysqlSession.insert_sql(sql=sql)


if __name__ == "__main__":
    asyncio.run(get_deposit_withdraw_fee())
