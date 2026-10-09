import datetime, time, asyncio

from libs.database.getmysql import G_MysqlSession

spot_db = 'fund'

SPOT_MYSQL_CONFIG = {
    "host": "abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
    "port": 3306,
    "user": "admin",
    "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
    "db": spot_db,
}

async def get_start_amount():
    # 现货转现货 、现货转合约、合约转合约、合约转现货
    t1_dict = {}
    t2_dict = {}
    sql = "SELECT * from hedge where time='2024-08-27 18:00:15'"
    res, title = await G_MysqlSession.fetch_all(sql)
    for r in res:
        t1_dict[r[2]] = r[15] * r[21]

    sql = "SELECT * from hedge where time='2024-08-27 21:00:14'"
    res, title = await G_MysqlSession.fetch_all(sql)
    for r in res:
        t2_dict[r[2]] = r[15] * r[21]
    t1_keys = t1_dict.keys()
    for k in t1_keys:
        if abs(t1_dict[k] - t2_dict.get(k, 0)) > 100:
            print(k, t1_dict[k], t2_dict[k])


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(get_start_amount())

