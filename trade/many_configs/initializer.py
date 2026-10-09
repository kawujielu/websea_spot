from UltraDict import UltraDict
from many_configs import global_variable
import loguru


def init_share_memory():
    """
        recurse=False  只能使用 {"key1": []} 或者 {"key1": ""} 结构
        buffer_size 由2000个key value为float 估算

    """
    global_variable.SHARE_VOLUME_MAKER_SYMBOLS = UltraDict(name=global_variable.SHARE_VOLUME_MAKER_SYMBOLS_KEY,
                                                           buffer_size=200_000,
                                                           auto_unlink=False,
                                                           shared_lock=True,
                                                           # recurse=True,
                                                           )
    loguru.logger.info("init_share_memory -- ok")


def init_share_error_msg_memory():
    """
        recurse=False  只能使用 {"key1": []} 或者 {"key1": ""} 结构

    """
    global_variable.SHARE_ERROR_MESSAGES = UltraDict(name=global_variable.SHARE_ERROR_MESSAGES_KEY,
                                                     buffer_size=300_000,
                                                     auto_unlink=False,
                                                     shared_lock=True,
                                                     # recurse=True,
                                                     )
    loguru.logger.info("init_share_error_msg_memory -- ok")

