import traceback


def exception_handler(func):
    async def wrap(*args, **kwargs):
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            print(f"{traceback.format_exc()}")
            return False
    return wrap
