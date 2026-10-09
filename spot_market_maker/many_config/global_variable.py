import copy
from . import risk_control_c
from config import symbols

"""
new
根据对冲缺口对应CNY值的大小，调整买卖一价差  
理解为 当缺口达到threshold_1时取对应值，当缺口达到threshold_2时取对应值，当缺口达到threshold_3时取对应值
threshold_S threshold_0 threshold_1 threshold_2 threshold_3 顺序不可乱 值的大小按照大到小
hedge_cny:对冲缺口阈值折合人民币
scaled_percent：买卖一价差单边偏移量百分比
spread_percent：档位价差倍数
amount_percent：近盘口深度倍数
defense_amount_percent： 防御盘口深度倍数
"""
currency_hedge_scaled_percent = risk_control_c.currency_hedge_scaled_percent_mappings
currency_hedge_scaled_percent["last_time_hedge_data"] = {}  # 保存对冲缺口数据

currency_hangqing_scaled_percent = {
    x.split("-")[0]: {'scaled_percent': 0.1, 'spread_percent': 6, 'amount_percent': 0.001,
                      'defense_amount_percent': 0.001}
    for x in symbols
}
currency_hangqing_scaled_percent["last_time_hangqing_config"] = {}  # 保存行情数据

# 错误消息共享内存
SHARE_ERROR_MESSAGES = {}
SHARE_ERROR_MESSAGES_KEY = "share_e_m"

# 价格波动触发更新
PRICE_UPDATE_SIGNAL = {}

VOLUME_AJD_PERCENT = {}