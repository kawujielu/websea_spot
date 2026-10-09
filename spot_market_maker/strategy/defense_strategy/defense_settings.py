import config

NAME = "DEFENSE"

sleepTime = 3
# 撤销的频率
cancel_order_time = sleepTime * 0.98

"""
orders_num：档位起止数量 【初始档位，终止档位】
"""
orders_num = [9, 20]

# 档位的数量不能少于重采样的数量10
assert orders_num[1] - orders_num[0] + 1 > 10

account = config.defense_strategy_account

# 拆分下单撤单数，0为不拆分, 如果设置为0.5, 15单 会拆分为7+7+1
percent_order = 0.6

RESET_TIMES = 80
