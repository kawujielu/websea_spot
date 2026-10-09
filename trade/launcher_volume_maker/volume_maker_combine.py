import asyncio
from many_configs import global_variable, initializer
import loguru
from volume_maker_center import main_maker
from volume_maker_ws_source import main_maker_ws_source


def init_share_fake_memory():
    """
        recurse=False  只能使用 {"key1": []} 或者 {"key1": ""} 结构
        buffer_size 由2000个key value为float 估算

    """
    if not global_variable.SHARE_VOLUME_MAKER_SYMBOLS:
        global_variable.SHARE_VOLUME_MAKER_SYMBOLS = {}
        loguru.logger.info("init_share_fake_memory -- ok")


async def main():
    zone = "USDT"
    initializer.init_share_memory = init_share_fake_memory

    tasks = [asyncio.create_task(main_maker_ws_source()),
             asyncio.create_task(main_maker(zone)),
             ]
    for i in tasks:
        await i


if __name__ == '__main__':
    asyncio.run(main())
