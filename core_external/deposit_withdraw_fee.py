import asyncio
from scaffold.mysql import Hedge_MysqlSession
from many_configs import global_variable
import loguru


class DepositWithdrawFeePosition:
    def __init__(self):
        pass

    async def position(self):
        sql = """SELECT coin,amount from fee_asset_gap """
        res = await Hedge_MysqlSession.fetch_all(sql)
        for i in res:
            global_variable.DEPOSIT_WITHDRAW_POSITIONS[i[0]] = i[1]

    async def init_position(self):
        await self.position()
        loguru.logger.info("withdraw_positions_init_position -- ok")

    async def deposit_withdraw_positions_collector(self):
        await self.position()
        loguru.logger.info(f'WITHDRAW_POSITIONS {global_variable.DEPOSIT_WITHDRAW_POSITIONS}')

    async def run(self):
        while True:
            if not global_variable.DEPOSIT_WITHDRAW_POSITIONS:
                await self.init_position()
            await self.deposit_withdraw_positions_collector()
            loguru.logger.info(f"{global_variable.DEPOSIT_WITHDRAW_POSITIONS}")
            await asyncio.sleep(60 * 5)


deposit_withdraw_positions_instance = DepositWithdrawFeePosition()

if __name__ == '__main__':
    asyncio.run(deposit_withdraw_positions_instance.run())
