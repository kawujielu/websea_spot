# -- 不能注释，此导入为初始化
import initialization
# ---
import asyncio
import traceback
from engine.initializer import init_for_ws
from many_configs import global_variable
from exchanges.spot_ws import ws_depth
from core_external.market import subscribe_ws
from many_configs.global_variable import WS_EXCHANGE_ACTIVE


async def main(symbols):
    try:
        # 初始化多进程内存空间
        await init_for_ws()

        # 启动数据服务
        tasks = []
        for ex in WS_EXCHANGE_ACTIVE:
            # 防止重启初始化清空内存块
            if not global_variable.SHARE_MEMORY_WS_INSTANCE.get(ex):
                global_variable.SHARE_MEMORY_WS_INSTANCE[ex] = {}

            thread_name = f"{ex}Thread"
            depth_function = getattr(ws_depth, f"get_{ex}_depth")
            tasks.append(
                asyncio.create_task(depth_function({thread_name: {}}, symbols,
                                                   is_subscribe="subscribe", thread_name=thread_name)))

        tasks.append(asyncio.create_task(subscribe_ws()))

        for t in tasks:
            await t
    except Exception as e:
        print(f"{traceback.format_exc()}")
    finally:
        pass


if __name__ == "__main__":
    asyncio.run(main(['BTC-USDT']))
