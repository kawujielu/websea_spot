# coding=utf-8
from config.infor_load import python_v
import sys, os
import os

filename = sys.path[0] + '/contract'


def start():
    os.system(f"nohup {python_v} {filename}/con_risk_rate.py &")  # 仓位监控
    os.system(f"nohup {python_v} {filename}/con_gear_depth.py &")  # 深度监测
    os.system(f"nohup {python_v} {filename}/con_capitalrate.py &")  # 资金费率
    os.system(f"nohup {python_v} {filename}/con_precision_price.py &")  # 价格精度监控
    os.system(f"nohup {python_v} {filename}/con_position_user_list.py &")  # 合约用户持仓监控
    os.system(f"nohup {python_v} {filename}/con_get_mongoacc_orders.py &")  # 合约mongo
    os.system(f"nohup {python_v} {filename}/con_high_frequency_trading.py &")  # 合约高频1小时
    os.system(f"nohup {python_v} {filename}/con_orders_profit.py &")  # 合约盈亏较多
    os.system(f"nohup {python_v} {filename}/con_acc_updown.py &")  # 24小时涨跌幅度
    os.system(f"nohup {python_v} {filename}/con_acc_kline.py &")  # 5min kline涨跌幅度
    os.system(f"nohup {python_v} {filename}/con_ex.py &")  # 合约对冲账户信息


def stop():
    print('start kill programe about monitor_contract.py')
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
    # start()
    main()
