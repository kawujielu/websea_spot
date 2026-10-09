# coding=utf-8
from config.infor_load import python_v
import sys, os
import os

filename = sys.path[0] + '/spot'


def start():
    os.system(f"nohup {python_v} {filename}/spot_acc_precision.py &")  # 精度监控、价格区间
    os.system(f"nohup {python_v} {filename}/spot_acc_gear_depth.py &")  # 深度监测
    os.system(f"nohup {python_v} {filename}/spot_acc_kline.py &")  # 5minK线
    os.system(f"nohup {python_v} {filename}/spot_acc_updown.py &")  # 涨跌服务监控
    os.system(f"nohup {python_v} {filename}/abc_user_deposit_withdraw_list.py &")  # abc充值监控
    os.system(f"nohup {python_v} {filename}/spot_acc_precision_price.py &")  # 界面精度与默认精度
    os.system(f"nohup {python_v} {filename}/spot_redis_price.py &")  # redis 1、2 号库价格监控
    os.system(f"nohup {python_v} {filename}/spot_get_mongoacc_orders.py &")  # MongoOrders mongodb转存
    os.system(f"nohup {python_v} {filename}/spot_high_frequency_trading.py &")  # 高频交易
    os.system(f"nohup {python_v} {filename}/spot_acc_avg_amount_orders.py &")  # 成交量监控
    os.system(f"nohup {python_v} {filename}/spot_get_mongo_user.py &")  # 现货 交易账户与用户成交


def stop():
    print('start kill programe about manage_quant.py')
    os.system("kill -9 $(ps -ef|grep %s/ |gawk '$0 !~/grep/ {print $2}' |tr -s '\n' ' ')" % filename)
    print('----------- kill programe completed------------')


def restart():
    stop()
    start()
    print("---------restart completed---------")


def main():
    import sys
    try:
        sys.argv[1]
    except:
        start()
    else:
        if sys.argv[1] == "stop":
            stop()
        elif sys.argv[1] == "restart":
            restart()
        elif sys.argv[1] == "start" or "run":
            start()
        else:
            raise KeyError


if __name__ == '__main__':
    main()
    # stop()
