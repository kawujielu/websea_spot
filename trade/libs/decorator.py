import traceback
from many_configs import global_variable
from libs.heartbeat import register_monitor
import asyncio
from loguru import logger


def monitor_handler(func):
    async def wrap(*args, **kwargs):
        try:
            task_name = kwargs["monitor"]
            register_monitor(task_name)

            result = await func(*args)
            return result
        except Exception as e:
            logger.error(f"{traceback.format_exc()}")
            return False

    def sync_wrap(*args, **kwargs):
        try:
            task_name = kwargs.get("monitor")
            register_monitor(task_name)

            result = func(*args)
            return result
        except Exception as e:
            logger.error(f"{traceback.format_exc()}")
            return False

    if asyncio.iscoroutinefunction(func):
        return wrap
    else:
        return sync_wrap

