import asyncio

from libs.database.getmysql import G_MysqlSession

OUT_UID = ['1']


async def get_start_amount():
    # 现货转现货 、现货转合约、合约转合约、合约转现货
    sql = "SELECT from_uid,from_symbol,to_uid,to_symbol,operator_name,sum(amount) amount from account_info GROUP BY from_uid,from_symbol,to_uid,to_symbol,operator_name ;"
    res, title = await G_MysqlSession.fetch_all(sql)

    START_AMOUNT_SPOT, START_AMOUNT_CONTRACT = {}, {}
    for i in res:
        from_uid = i[0]
        from_symbol = i[1]
        to_uid = i[2]
        to_symbol = i[3]
        operator_name = i[4]
        amount = i[5]
        operator = operator_name.split('转')

        if from_uid not in OUT_UID:
            if operator[0] == '现货':
                START_AMOUNT_SPOT[from_uid] = START_AMOUNT_SPOT.get(from_uid, {})
                START_AMOUNT_SPOT[from_uid][from_symbol] = START_AMOUNT_SPOT[from_uid].get(from_symbol, 0) - amount
            if operator[0] == '合约':
                START_AMOUNT_CONTRACT[from_uid] = START_AMOUNT_CONTRACT.get(from_uid, {})
                START_AMOUNT_CONTRACT[from_uid][from_symbol] = START_AMOUNT_CONTRACT[from_uid].get(from_symbol, 0) - amount

        if to_uid not in OUT_UID:
            if operator[1] == '现货':
                START_AMOUNT_SPOT[to_uid] = START_AMOUNT_SPOT.get(to_uid, {})
                START_AMOUNT_SPOT[to_uid][to_symbol] = START_AMOUNT_SPOT[to_uid].get(to_symbol, 0) + amount
            if operator[1] == '合约':
                START_AMOUNT_CONTRACT[to_uid] = START_AMOUNT_CONTRACT.get(to_uid, {})
                START_AMOUNT_CONTRACT[to_uid][to_symbol] = START_AMOUNT_CONTRACT[to_uid].get(to_symbol, 0) + amount
    return START_AMOUNT_SPOT, START_AMOUNT_CONTRACT


if __name__ == '__main__':
    asyncio.run(get_start_amount())
