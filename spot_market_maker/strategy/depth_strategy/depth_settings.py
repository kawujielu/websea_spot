import config

NAME = "DEPTH"

sleepTime = 18
cancel_order_time = sleepTime * 0.9


"""
orders_num：档位起止数量 【初始档位，终止档位】
"""
orders_num = [21, 50]


"""
PRICE_SPREAD_WEIGHT：调整档位价差系数 
    理解为调整为估算价差的几倍。 大于1为价差变大 ，变的更稀疏；小于1为价差变小，变的更密集
"""

account = config.depth_strategy_account

# 拆分下单撤单数，0为不拆分 如果设置为0.5, 15单 会拆分为7+7+1
percent_order = 0.6

RESET_TIMES = 50
