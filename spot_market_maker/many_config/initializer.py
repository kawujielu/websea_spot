import traceback
from UltraDict import UltraDict
from many_config import global_variable
import loguru


def init_share_memory():
    try:
        """
            recurse=False  只能使用 {"key1": []} 或者 {"key1": ""} 结构

        """
        global_variable.SHARE_ERROR_MESSAGES = UltraDict(name=global_variable.SHARE_ERROR_MESSAGES_KEY,
                                                         buffer_size=300_000,
                                                         auto_unlink=False,
                                                         shared_lock=True,
                                                         )
    except BaseException as e:
        loguru.logger.info(f"init_share_memory {traceback.format_exc()} -- ")
    loguru.logger.info("init_share_memory -- ok")