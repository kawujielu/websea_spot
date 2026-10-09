import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
import asyncio
import aiomysql
from aiomysql import utils
from scaffold.decorator import exception_handler

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

    @exception_handler
    async def fetch_all(self, sql):
        pool = await self.create_session()

        async with pool.acquire() as conn:
            cur = await conn.cursor()
            await cur.execute(sql)
            res = await cur.fetchall()
            return res

    @exception_handler
    async def fetch_all_and_description(self, sql):
        pool = await self.create_session()

        async with pool.acquire() as conn:
            cur = await conn.cursor()
            await cur.execute(sql)
            res = await cur.fetchall()
            description = cur.description
            return res, description

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

if __name__ == "__main__":
    async def fetch_mysql_data():
        pass


    asyncio.run(fetch_mysql_data())
