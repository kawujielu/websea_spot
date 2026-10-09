# coding=utf-8
import os, sys, requests, time, re, asyncio
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs import heartbeat, sendmessage
from libs.database.getmysql import Hedge_MysqlSession


async def delete_hegde_gap():
    fetch_timeout = 60 * 60 * 1
    try:
        # sql = f"""DELETE FROM abc_asset_gap_all1_copy1 WHERE create_time < NOW() - INTERVAL 1 DAY;"""
        sql = f"""DELETE FROM abc_asset_gap_all WHERE create_time < NOW() - INTERVAL 1 DAY;"""
        await Hedge_MysqlSession.insert_sql(sql)

        sql = f"""DELETE FROM external_asset_gap_all WHERE create_time < NOW() - INTERVAL 3 DAY;"""
        await Hedge_MysqlSession.insert_sql(sql)

        await heartbeat.i_live_well(server='删除mysql数据', frequency=fetch_timeout * 2.1, index=38)
    except:
        sendmessage.send_telegram_msg(f'删除mysql数据\n{traceback.format_exc()}', ser='Alarm')
    finally:

        Hedge_MysqlSession.client.close()
        await Hedge_MysqlSession.client.wait_closed()


if __name__ == '__main__':
    asyncio.run(delete_hegde_gap())
