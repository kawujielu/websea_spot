import os
import sys
import libs
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
import asyncio
import traceback
import aiomysql
from aiomysql import utils
from scaffold.decorator import exception_handler
from loguru import logger

if not libs.libs_config.DEBUG:
    SPOT_MYSQL_CONFIG = {
        "host": "abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
        "port": 3306,
        "user": "admin",
        "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
        "db": "fund",
    }

    HEDGE_MYSQL_CONFIG = {
        "host": "abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
        "port": 3306,
        "user": "admin",
        "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
        "db": "hedge",
    }
    # HEDGE_MYSQL_CONFIG = {
    #     "host": "localhost",
    #     "port": 3306,
    #     "user": "root",
    #     "password": "dh981aj92*&2AM",
    #     "db": "hedge"
    # }
else:
    SPOT_MYSQL_CONFIG = {
        "host": "abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
        "port": 3306,
        "user": "admin",
        "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
        "db": "fund_test",
    }

    HEDGE_MYSQL_CONFIG = {
        "host": "abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
        "port": 3306,
        "user": "admin",
        "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
        "db": "hedge_test",
    }


# 本地
# HEDGE_MYSQL_CONFIG = {
#     mysql://root:dh981aj92*&2AM@127.0.0.1:3306
# "host": "localhost",
# "port": 3306,
# "user": "root",
# "password": "dh981aj92*&2AM",
# "db": "hedge"
# }


# class _MPoolAcquireContextManager(utils._ContextManager):
#     __slots__ = ('_coro', '_conn', '_pool')
#
#     def __init__(self, coro, pool):
#         self._coro = coro
#         self._conn = None
#         self._pool = pool
#
#     async def __aenter__(self):
#         self._conn = await self._coro
#         return self._conn
#
#     async def __aexit__(self, exc_type, exc, tb):
#         try:
#             await self._pool.release(self._conn)
#         finally:
#             pass
#
#
# utils._PoolAcquireContextManager = _MPoolAcquireContextManager

mysql_lock = asyncio.Lock()

class MysqlSession:
    def __init__(self, mysql_config):
        self.client = None
        self.MYSQL_CONFIG = mysql_config

    async def create_session(self):
        if self.client is None:
            async with mysql_lock:
                if self.client is None:
                    self.client = await aiomysql.create_pool(host=self.MYSQL_CONFIG["host"],
                                                             port=self.MYSQL_CONFIG["port"],
                                                             user=self.MYSQL_CONFIG["user"],
                                                             password=self.MYSQL_CONFIG["password"],
                                                             db=self.MYSQL_CONFIG["db"],
                                                             connect_timeout=1,
                                                             autocommit=True)
        return self.client

    @exception_handler
    async def fetch_one(self, sql):
        pool = await self.create_session()

        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # cur = await conn.cursor()
                await cur.execute(sql)
                res = await cur.fetchone()
                logger.info(res)
                return res

    @exception_handler
    async def fetch_one_column(self, sql):
        pool = await self.create_session()

        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # cur = await conn.cursor()
                await cur.execute(sql)
                res = await cur.fetchone()
                if not res:
                    return
                keys = [i[0] for i in cur.description]
                res_column = dict(zip(keys, res))
                return res_column

    @exception_handler
    async def fetch_all(self, sql):
        pool = await self.create_session()

        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # cur = await conn.cursor()
                await cur.execute(sql)
                res = await cur.fetchall()
                return res

    @exception_handler
    async def fetch_all_column(self, sql):
        pool = await self.create_session()

        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # cur = await conn.cursor()
                await cur.execute(sql)
                res = await cur.fetchall()
                keys = [i[0] for i in cur.description]
                res_column = []
                for r in res:
                    res_column.append(dict(zip(keys, r)))
                return res_column

    @exception_handler
    async def insert(self, sql, value=None):
        pool = await self.create_session()

        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # cur = await conn.cursor()
                # number of rows that has been produced of affected
                if value:
                    res = await cur.execute(sql, value)
                else:
                    res = await cur.execute(sql)
                await conn.commit()
                return res

    async def insert_sql(self, sql):
        pool = await self.create_session()

        async with pool.acquire() as conn:
            await conn.begin()
            async with conn.cursor() as cur:
                # cur = await conn.cursor()
                try:
                    await cur.execute(sql)
                    await conn.commit()
                except Exception as e:
                    await conn.rollback()
                    raise e


G_MysqlSession = MysqlSession(SPOT_MYSQL_CONFIG)
Hedge_MysqlSession = MysqlSession(HEDGE_MYSQL_CONFIG)

if __name__ == "__main__":
    async def fetch_mysql_data():
        b = await Hedge_MysqlSession.fetch_one_column("SELECT * FROM dex_orders")


    asyncio.run(fetch_mysql_data())
