import loguru

from many_configs import global_variable
from libs.senddd import send_telegram_async, send_telegram_important_msg_async, send_telegram_msg_async
import libs
import asyncio
import traceback

SEND_MSG_INTERVAL_TIME = 60
# tg 限制消息长度为4096字符
MSG_LENGTH_MAX = 3000
MSG_LENGTH_MAX_LAST = 4000


async def send_tg(msg_content, ser):
    loguru.logger.info(f'send tg msg {ser=},{msg_content=}')
    if ser == 'send_telegram_important_msg_url':
        await send_telegram_important_msg_async(msg_content, debug=libs.libs_config.DEBUG)
    elif ser == 'send_telegram_msg_url':
        await send_telegram_msg_async(msg_content, debug=libs.libs_config.DEBUG)
    else:
        await send_telegram_async(msg_content, ser, libs.libs_config.DEBUG)


async def send_error_msg():
    while True:
        try:
            loguru.logger.info(f'send error msg {global_variable.SHARE_ERROR_MESSAGES=}')
            for ser, message in global_variable.SHARE_ERROR_MESSAGES.items():
                msg_content = ''
                if not message:
                    continue
                if len('\n'.join(message)) <= MSG_LENGTH_MAX:
                    msg_content += '\n' + '\n'.join(message)
                    await send_tg(msg_content, ser)
                    global_variable.SHARE_ERROR_MESSAGES[ser] = []
                else:
                    for index, msg in enumerate(message):
                        msg_content += '\n' + msg
                        if len(msg_content) >= MSG_LENGTH_MAX:
                            msg_content = msg_content[:MSG_LENGTH_MAX_LAST]
                            await send_tg(msg_content, ser)
                            global_variable.SHARE_ERROR_MESSAGES[ser] = global_variable.SHARE_ERROR_MESSAGES[ser][
                                                                        index + 1:]
                            msg_content = ''
        except Exception as e:
            loguru.logger.info(f'send tg msg {traceback.format_exc()}')
        finally:
            await asyncio.sleep(SEND_MSG_INTERVAL_TIME)


async def recode_error_msg(msg, server):
    loguru.logger.error(msg)
    return recode_error_msg_sync(msg, server)


def recode_error_msg_sync(msg, server):
    try:
        error_msg_list = global_variable.SHARE_ERROR_MESSAGES.get(server, [])
        msg = msg[:1000]
        if msg not in error_msg_list:
            error_msg_list.append(f"{msg}")
            if len(error_msg_list) > 1000:
                global_variable.SHARE_ERROR_MESSAGES[server] = error_msg_list[-1000:]
            else:
                global_variable.SHARE_ERROR_MESSAGES[server] = error_msg_list
    except BaseException as e:
        print(f"recode_error_msg_sync {traceback.format_exc()}")
