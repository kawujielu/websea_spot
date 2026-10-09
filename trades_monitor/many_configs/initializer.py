from UltraDict import UltraDict
from many_configs import global_variable
import loguru
import traceback


def init_share_memory():
    """
        recurse=False  只能使用 {"key1": []} 或者 {"key1": ""} 结构
        buffer_size 由2000个key value为float 估算
    """
    try:
        global_variable.SHARE_NOTICE = UltraDict(name=global_variable.SHARE_NOTICE_KEY,
                                                 buffer_size=10_000_000,
                                                 auto_unlink=False,
                                                 shared_lock=True,
                                                 # recurse=True
                                                 )
    except BaseException as e:
        loguru.logger.info(f"init_share_memory {traceback.format_exc()} -- ")
    loguru.logger.info("init_share_memory -- ok")


def init_exchange_share_memory():
    try:
        global_variable.SHARE_EXCHANGE = UltraDict(name=global_variable.SHARE_EXCHANGE_KEY,
                                                   buffer_size=10_000_000,
                                                   auto_unlink=False,
                                                   shared_lock=True,
                                                   # recurse=True
                                                   )
    except BaseException as e:
        loguru.logger.info(f"init_share_memory {traceback.format_exc()} -- ")
    loguru.logger.info("init_share_memory -- ok")
