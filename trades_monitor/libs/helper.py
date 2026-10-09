import time


def add_retry(func):
    def wrapper(*args, **kwargs):
        max_retries = kwargs.pop('max_retries', 5)  # 默认最大重试次数为3次

        for i in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                print("发生了错误：", str(e))

                if i < max_retries:
                    print("正在第 {} 次重试...".format(i + 1))
                    time.sleep(10)  # 等待2秒后再进行重试
                else:
                    raise ValueError("达到最大重试次数") from None

    return wrapper
