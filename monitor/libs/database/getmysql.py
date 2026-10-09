import asyncio
import json

from aiomysql import utils
from motor.motor_asyncio import AsyncIOMotorClient
import traceback
import aiomysql
import pymysql

# from config.infor_load import DEBUG

# if DEBUG:
#     spot_db = 'fund_test'
#     hedge_db = 'hedge_test'
# else:
#     spot_db = 'fund'
#     hedge_db = 'hedge'
spot_db = 'fund'
hedge_db = 'hedge'
SPOT_MYSQL_CONFIG = {
    "host": "abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
    "port": 3306,
    "user": "admin",
    "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
    "db": spot_db,
}

HEDGE_MYSQL_CONFIG = {
    "host": "abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com",
    "port": 3306,
    "user": "admin",
    "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2",
    "db": hedge_db,
}


def sync_mysql_connect(msql):
    conn = pymysql.connect(host=SPOT_MYSQL_CONFIG['host'], user=SPOT_MYSQL_CONFIG["user"],
                           password=SPOT_MYSQL_CONFIG["password"], database=SPOT_MYSQL_CONFIG["db"],
                           port=SPOT_MYSQL_CONFIG["port"],
                           charset='utf8')
    cursor = conn.cursor()
    cursor.execute(msql)
    res = cursor.fetchall()
    cursor.close()
    conn.close()
    return res


def exception_handler(func):
    async def wrap(*args, **kwargs):
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            print(f"{traceback.format_exc()}")
            return False

    return wrap


class _MPoolAcquireContextManager(utils._ContextManager):
    __slots__ = ('_coro', '_conn', '_pool')

    def __init__(self, coro, pool):
        self._coro = coro
        self._conn = None
        self._pool = pool

    async def __aenter__(self):
        self._conn = await self._coro
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        try:
            await self._pool.release(self._conn)
        finally:
            pass


utils._PoolAcquireContextManager = _MPoolAcquireContextManager


class MysqlSession:
    def __init__(self, mysql_config):
        self.client = None
        self.MYSQL_CONFIG = mysql_config

    async def create_session(self):
        if self.client is None:
            self.client = await aiomysql.create_pool(host=self.MYSQL_CONFIG["host"],
                                                     port=self.MYSQL_CONFIG["port"],
                                                     user=self.MYSQL_CONFIG["user"],
                                                     password=self.MYSQL_CONFIG["password"],
                                                     db=self.MYSQL_CONFIG["db"],
                                                     autocommit=True)
        return self.client

    @exception_handler
    async def fetch_one(self, sql):
        pool = await self.create_session()

        async with pool.acquire() as conn:
            cur = await conn.cursor()
            await cur.execute(sql)
            res = await cur.fetchone()
            print(res)
            return res

    @exception_handler
    async def fetch_all(self, sql):
        pool = await self.create_session()

        async with pool.acquire() as conn:
            cur = await conn.cursor()
            await cur.execute(sql)
            res = await cur.fetchall()
            title = [i[0] for i in cur.description]
            return res, title

    @exception_handler
    async def insert(self, sql):
        pool = await self.create_session()

        async with pool.acquire() as conn:
            cur = await conn.cursor()
            # number of rows that has been produced of affected
            res = await cur.execute(sql)
            return res

    async def insert_sql(self, sql):
        pool = await self.create_session()

        async with pool.acquire() as conn:
            await conn.begin()
            cur = await conn.cursor()
            try:
                await cur.execute(sql)
                await conn.commit()
            except Exception as e:
                await conn.rollback()
                raise e


G_MysqlSession = MysqlSession(SPOT_MYSQL_CONFIG)
Hedge_MysqlSession = MysqlSession(HEDGE_MYSQL_CONFIG)

if __name__ == '__main__':

    sql = "select * from hedge_config "
    a, b = asyncio.run(Hedge_MysqlSession.fetch_all(sql))
    print(a)
    print(b)
