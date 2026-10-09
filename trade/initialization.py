import time
import traceback
from UltraDict import UltraDict
import asyncio
import uvloop
import gc


asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

background_tasks = set()
create_task_reference = asyncio.create_task
latest_send_tg_time = 0


def create_task(fun, name=None):
    """
    弱引用导致未完成的task可能被gc释放，导致task异常
    Save a reference to the result of this function, to avoid a task disappearing mid-execution.
    The event loop only keeps weak references to tasks.
    A task that isn't referenced elsewhere may get garbage collected at any time, even before it's done.
    For reliable "fire-and-forget" background tasks, gather them in a collection:
    background_tasks = set()

    for i in range(10):
        task = asyncio.create_task(some_coro(param=i))

        # Add task to the set. This creates a strong reference.
        background_tasks.add(task)

        # To prevent keeping references to finished tasks forever,
        # make each task remove its own reference from the set after
        # completion:
        task.add_done_callback(background_tasks.discard)

    """
    try:
        t = create_task_reference(fun, name=name)
        background_tasks.add(t)
        t.add_done_callback(background_tasks.discard)
        return t
    except BaseException:
        print(f"create_task -- except {traceback.format_exc()}")


asyncio.create_task = create_task

# ------------------------------------------------------共享内存---------------------------------------------------------

from libs import senddd

_setitem = UltraDict.__setitem__
_getitem = UltraDict.__getitem__


def __setitem__(self, key, item):
    try:
        _setitem(self, key, item)
    except Exception:
        msg = f"{traceback.format_exc()}"
        print(f"共享内存写入错误{msg} {key} {item}")
        global latest_send_tg_time
        if time.time() - latest_send_tg_time > 5:
            latest_send_tg_time = time.time()
            senddd.send_telegram_important_msg(f"共享内存写入发生错误!{key} {msg[:100]}")


def __getitem__(self, key):
    try:
        return _getitem(self, key)
    except KeyError:
        raise KeyError
    except Exception:
        msg = f"{traceback.format_exc()}"
        print(f"共享内存读取错误{msg} {key}")
        global latest_send_tg_time
        if time.time() - latest_send_tg_time > 5:
            latest_send_tg_time = time.time()
            senddd.send_telegram_important_msg(f"共享内存读取发生错误!{key} {msg[:100]}")


UltraDict.__setitem__ = __setitem__
UltraDict.__getitem__ = __getitem__

# ------------------------------------------------------错误信息共享内存初始化---------------------------------------------

from many_configs.initializer import init_share_error_msg_memory
init_share_error_msg_memory()


if __name__ == '__main__':
    async def test():
        while 1:
            print("---")
            await asyncio.sleep(1)  # return 1 / 1


    async def test1():
        t = asyncio.create_task(test())
        # x = await t
        # print(x)
        print("3", background_tasks)
        print("4", background_tasks)


    async def test2():
        while 1:
            await asyncio.sleep(1)


    async def main():
        asyncio.create_task(test1())
        print("5", background_tasks)
        while 1:
            gc.collect()
            await asyncio.sleep(0.02)

    asyncio.run(main())
