from load import load_remote

REMOTE_INTERNAL_IP = "10.0.209.181"
REMOTE_IP = "10.0.209.181"

libs_config = load_remote.urllib_model("server@{}".format(REMOTE_IP), "/home/server/abclibs/config.py")
libs_price = load_remote.urllib_model("server@{}".format(REMOTE_IP, ), "/home/server/abclibs/price.py")
libs_price_async = load_remote.urllib_model("server@{}".format(REMOTE_IP, ), "/home/server/abclibs/price_async.py")
libs_account = load_remote.urllib_model("server@{}".format(REMOTE_IP, ), "/home/server/abclibs/account.py")
libs_dex_config = load_remote.urllib_model("server@{}".format(REMOTE_IP, ), "/home/server/abclibs/dex_config.py")