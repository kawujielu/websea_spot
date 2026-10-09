import traceback
from libs.recode_msg import recode_error_msg


def exception_handler(func):
    async def wrap(*args, **kwargs):
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            sql = kwargs.get("sql") or (args[1] if len(args) > 1 else "")
            await recode_error_msg(f"sql_error:{sql}\n{traceback.format_exc()}", server="spot_hedge")
            return False
    return wrap
