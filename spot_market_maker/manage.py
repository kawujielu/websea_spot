# -- 不能注释，此导入为初始化
import initialization
# ---
from strategy.near_strategy.near_main import run as near_run
from strategy.defense_strategy.defense_main import run as defense_run
from strategy.depth_strategy.depth_main import run as depth_run
from multiprocessing import Process
from libs.recode_msg import send_error_msg
import asyncio
from many_config import initializer


def start():
    initializer.init_share_memory()

    p_near_run = Process(target=near_run)
    p_near_run.name = "near_run"

    p_defense_run = Process(target=defense_run)
    p_defense_run.name = "defense_run"

    p_depth_run = Process(target=depth_run)
    p_depth_run.name = "depth_run"

    p_near_run.start()
    p_defense_run.start()
    p_depth_run.start()

    asyncio.run(send_error_msg())

    p_near_run.join()
    p_defense_run.join()
    p_depth_run.join()


if __name__ == '__main__':
    start()
