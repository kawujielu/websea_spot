# -- 不能注释，此导入为初始化
import initialization
# ---
import asyncio
import traceback
from scaffold.mysql import Hedge_MysqlSession
from engine.initializer import init
from engine.sanic_ser import sanic_app
from engine.position_hedge import exposure_detection_and_hedge, dex_order_control_hub
from engine.position_collector import abc_position_collector, deposit_withdraw_position_collector
from exchanges.spot_ws import ws_wallet, ws_order
from libs.recode_msg import send_error_msg


async def main():
    try:
        await init()
        # 保证初始化工作都完成再进行以下任务
        tasks = [
            asyncio.create_task(sanic_app),
            asyncio.create_task(exposure_detection_and_hedge()),    # 对冲
            # abc对冲缺口collector ，外部交易所collector是在创建撤销等订单的时候自动触发更新
            asyncio.create_task(abc_position_collector()),
            # asyncio.create_task(dex_order_control_hub()),
            asyncio.create_task(deposit_withdraw_position_collector()),
            asyncio.create_task(send_error_msg()),

            # order trade ws数据服务
            asyncio.create_task(ws_order.get_gate_order()),
            asyncio.create_task(ws_order.get_bn_order()),
            # asyncio.create_task(ws_order.get_okex_order()),
            # asyncio.create_task(ws_order.get_mxc_order()),
            asyncio.create_task(ws_order.get_bitget_order()),
            asyncio.create_task(ws_order.get_kraken_wallet()),
            # TODO Kraken
            asyncio.create_task(ws_order.put_ex_listen_key()),
        ]

        for t in tasks:
            await t
    except BaseException as e:
        print(f"{traceback.format_exc()}")
    finally:
        Hedge_MysqlSession.client.close()
        await Hedge_MysqlSession.client.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
