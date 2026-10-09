from load import load_remote

# 加载远程价格服务和账号信息
SERVER_REMOTE_IP = "10.0.209.181"

libs_price_async = load_remote.urllib_model(f"server@{SERVER_REMOTE_IP}", f"/home/server/abclibs/price_async.py")
libs_price = load_remote.urllib_model(f"server@{SERVER_REMOTE_IP}", f"/home/server/abclibs/price.py")
libs_account = load_remote.urllib_model(f"server@{SERVER_REMOTE_IP}", f"/home/server/abclibs/account.py")
libs_config = load_remote.urllib_model(f"server@{SERVER_REMOTE_IP}", f"/home/server/abclibs/config.py")
if libs_config.DEBUG:
    libs_account = libs_account.account_test
else:
    libs_account = libs_account.account

# from abclibs import price_async as libs_price_async
# from abclibs import account as libs_account
# from abclibs import config as libs_config
# libs_account = libs_account.account