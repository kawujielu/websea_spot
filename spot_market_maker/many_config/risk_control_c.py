w = 10 ** 4

"""
根据对冲缺口对应CNY值的大小，调整买卖一价差  
理解为 当缺口达到threshold_1时取对应值，当缺口达到threshold_2时取对应值，当缺口达到threshold_3时取对应值
threshold_S threshold_0 threshold_1 threshold_2 threshold_3 顺序不可乱 值的大小按照大到小
hedge_cny:对冲缺口阈值折合人民币
scaled_percent：买卖一价差单边偏移量百分比
spread_percent：档位价差倍数
amount_percent：近盘口深度倍数
defense_amount_percent： 防御盘口深度倍数
"""

currency_hedge_scaled_percent_mappings = {

    'last_time_hedge_config': {}, 'last_update_time': 0,
    # 稳定币
    'threshold_u': [{
        'hedge_cny': 0, 'scaled_percent': 0, 'spread_percent': 1, 'amount_percent': 1, 'defense_amount_percent': 1
    }, {
        'hedge_cny': 0, 'scaled_percent': 0, 'spread_percent': 1, 'amount_percent': 1, 'defense_amount_percent': 1
    }, {
        'hedge_cny': 0, 'scaled_percent': 0, 'spread_percent': 1, 'amount_percent': 1, 'defense_amount_percent': 1
    }, {
        'hedge_cny': 0, 'scaled_percent': 0, 'spread_percent': 1, 'amount_percent': 1, 'defense_amount_percent': 1
    }, {
        'hedge_cny': 0, 'scaled_percent': 0, 'spread_percent': 1, 'amount_percent': 1, 'defense_amount_percent': 1
    }],
    # 平台币
    'threshold_ot': [{
        'hedge_cny': 20 * w, 'scaled_percent': 0.015, 'spread_percent': 3, 'amount_percent': 0.4,
        'defense_amount_percent': 0.8
    }, {
        'hedge_cny': 10 * w, 'scaled_percent': 0.012, 'spread_percent': 2, 'amount_percent': 0.5,
        'defense_amount_percent': 0.8
    }, {
        'hedge_cny': 8 * w, 'scaled_percent': 0.01, 'spread_percent': 1.5, 'amount_percent': 0.6,
        'defense_amount_percent': 1
    }, {
        'hedge_cny': 5 * w, 'scaled_percent': 0.007, 'spread_percent': 1.2, 'amount_percent': 0.7,
        'defense_amount_percent': 1
    }, {
        'hedge_cny': 2 * w, 'scaled_percent': 0.005, 'spread_percent': 1, 'amount_percent': 0.8,
        'defense_amount_percent': 1
    }],

    # BTC ETH
    'threshold_1': [{
        'hedge_cny': 300 * w, 'scaled_percent': 0.0005, 'spread_percent': 2, 'amount_percent': 0.6,
        'defense_amount_percent': 0.8
    }, {
        'hedge_cny': 100 * w, 'scaled_percent': 0, 'spread_percent': 2, 'amount_percent': 0.6,
        'defense_amount_percent': 0.8
    }, {
        'hedge_cny': 80 * w, 'scaled_percent': 0, 'spread_percent': 1.5, 'amount_percent': 0.6,
        'defense_amount_percent': 1
    }, {
        'hedge_cny': 50 * w, 'scaled_percent': 0, 'spread_percent': 1.2, 'amount_percent': 0.7,
        'defense_amount_percent': 1
    }, {
        'hedge_cny': 20 * w, 'scaled_percent': 0, 'spread_percent': 1, 'amount_percent': 0.8,
        'defense_amount_percent': 1
    }],
    # 正常交易对
    'threshold_2': [{
        'hedge_cny': 500 * w, 'scaled_percent': 0.006, 'spread_percent': 4, 'amount_percent': 0.5,
        'defense_amount_percent': 0.8
    }, {
        'hedge_cny': 100 * w, 'scaled_percent': 0.004, 'spread_percent': 3, 'amount_percent': 0.6,
        'defense_amount_percent': 0.8
    }, {
        'hedge_cny': 30 * w, 'scaled_percent': 0.003, 'spread_percent': 2, 'amount_percent': 0.6,
        'defense_amount_percent': 1
    }, {
        'hedge_cny': 20 * w, 'scaled_percent': 0.002, 'spread_percent': 1.2, 'amount_percent': 0.7,
        'defense_amount_percent': 1
    }, {
        'hedge_cny': 10 * w, 'scaled_percent': 0.001, 'spread_percent': 1, 'amount_percent': 0.8,
        'defense_amount_percent': 1
    }],
    # 只对标了mcx 或者 gate
    'threshold_3': [{
        'hedge_cny': 25 * w, 'scaled_percent': 0.02, 'spread_percent': 6, 'amount_percent': 0.4,
        'defense_amount_percent': 0.8
    }, {
        'hedge_cny': 10 * w, 'scaled_percent': 0.01, 'spread_percent': 4, 'amount_percent': 0.5,
        'defense_amount_percent': 0.8
    }, {
        'hedge_cny': 5 * w, 'scaled_percent': 0.005, 'spread_percent': 1.5, 'amount_percent': 0.6,
        'defense_amount_percent': 1
    }, {
        'hedge_cny': 3 * w, 'scaled_percent': 0.002, 'spread_percent': 1.3, 'amount_percent': 0.7,
        'defense_amount_percent': 1
    }, {
        'hedge_cny': 1 * w, 'scaled_percent': 0.001, 'spread_percent': 1.2, 'amount_percent': 0.8,
        'defense_amount_percent': 1
    }],
    # 对标盘口比较差的币种-1
    'threshold_4': [{
        'hedge_cny': 25 * w, 'scaled_percent': 0.03, 'spread_percent': 6, 'amount_percent': 0.4,
        'defense_amount_percent': 0.8
    }, {
        'hedge_cny': 10 * w, 'scaled_percent': 0.02, 'spread_percent': 5, 'amount_percent': 0.5,
        'defense_amount_percent': 0.8
    }, {
        'hedge_cny': 5 * w, 'scaled_percent': 0.015, 'spread_percent': 4, 'amount_percent': 0.5,
        'defense_amount_percent': 1
    }, {
        'hedge_cny': 3 * w, 'scaled_percent': 0.01, 'spread_percent': 3, 'amount_percent': 0.6,
        'defense_amount_percent': 1
    }, {
        'hedge_cny': 0.7 * w, 'scaled_percent': 0.005, 'spread_percent': 2, 'amount_percent': 0.7,
        'defense_amount_percent': 1
    }],

    # 对标盘口比较差的币种-2
    'threshold_5': [{
        'hedge_cny': 10 * w, 'scaled_percent': 0.05, 'spread_percent': 4, 'amount_percent': 0.1,
        'defense_amount_percent': 0.5
    }, {
        'hedge_cny': 6 * w, 'scaled_percent': 0.025, 'spread_percent': 2, 'amount_percent': 0.2,
        'defense_amount_percent': 0.8
    }, {
        'hedge_cny': 5 * w, 'scaled_percent': 0.02, 'spread_percent': 1.8, 'amount_percent': 0.3,
        'defense_amount_percent': 1
    }, {
        'hedge_cny': 1 * w, 'scaled_percent': 0.008, 'spread_percent': 1.5, 'amount_percent': 0.4,
        'defense_amount_percent': 1
    }, {
        'hedge_cny': 0.5 * w, 'scaled_percent': 0.005, 'spread_percent': 1.3, 'amount_percent': 0.5,
        'defense_amount_percent': 1
    }],
    # 对标盘口比较差的币种-3

    'threshold_6': [{
        'hedge_cny': 5 * w, 'scaled_percent': 0.03, 'spread_percent': 4, 'amount_percent': 0.1,
        'defense_amount_percent': 0.5
    }, {
        'hedge_cny': 4 * w, 'scaled_percent': 0.025, 'spread_percent': 2, 'amount_percent': 0.2,
        'defense_amount_percent': 0.8
    }, {
        'hedge_cny': 2 * w, 'scaled_percent': 0.02, 'spread_percent': 1.5, 'amount_percent': 0.3,
        'defense_amount_percent': 1
    }, {
        'hedge_cny': 1 * w, 'scaled_percent': 0.015, 'spread_percent': 1.2, 'amount_percent': 0.4,
        'defense_amount_percent': 1
    }, {
        'hedge_cny': 0.4 * w, 'scaled_percent': 0.01, 'spread_percent': 1, 'amount_percent': 0.5,
        'defense_amount_percent': 1
    }],

    'threshold_7': [{
        'hedge_cny': 3 * w, 'scaled_percent': 0.03, 'spread_percent': 4, 'amount_percent': 0.1,
        'defense_amount_percent': 0.5
    }, {
        'hedge_cny': 1 * w, 'scaled_percent': 0.025, 'spread_percent': 2, 'amount_percent': 0.2,
        'defense_amount_percent': 0.8
    }, {
        'hedge_cny': 4000, 'scaled_percent': 0.02, 'spread_percent': 1.5, 'amount_percent': 0.3,
        'defense_amount_percent': 1
    }, {
        'hedge_cny': 1200, 'scaled_percent': 0.015, 'spread_percent': 1.2, 'amount_percent': 0.4,
        'defense_amount_percent': 1
    }, {
        'hedge_cny': 600, 'scaled_percent': 0.01, 'spread_percent': 1, 'amount_percent': 0.5,
        'defense_amount_percent': 1
    }],

    'threshold_8': [{
        'hedge_cny': 3 * w, 'scaled_percent': 0.03, 'spread_percent': 4, 'amount_percent': 0.1,
        'defense_amount_percent': 0.5
    }, {
        'hedge_cny': 2 * w, 'scaled_percent': 0.025, 'spread_percent': 2, 'amount_percent': 0.2,
        'defense_amount_percent': 0.8
    }, {
        'hedge_cny': 2000, 'scaled_percent': 0.02, 'spread_percent': 1.5, 'amount_percent': 0.3,
        'defense_amount_percent': 1
    }, {
        'hedge_cny': 1000, 'scaled_percent': 0.015, 'spread_percent': 1.2, 'amount_percent': 0.4,
        'defense_amount_percent': 1
    }, {
        'hedge_cny': 500, 'scaled_percent': 0.01, 'spread_percent': 1, 'amount_percent': 0.5,
        'defense_amount_percent': 1
    }],

    'threshold_9': [{
        'hedge_cny': 3 * w, 'scaled_percent': 0.04, 'spread_percent': 4, 'amount_percent': 0.1,
        'defense_amount_percent': 0.5
    }, {
        'hedge_cny': 2 * w, 'scaled_percent': 0.03, 'spread_percent': 2, 'amount_percent': 0.2,
        'defense_amount_percent': 0.8
    }, {
        'hedge_cny': 2000, 'scaled_percent': 0.025, 'spread_percent': 1.5, 'amount_percent': 0.3,
        'defense_amount_percent': 1
    }, {
        'hedge_cny': 1000, 'scaled_percent': 0.02, 'spread_percent': 1.2, 'amount_percent': 0.4,
        'defense_amount_percent': 1
    }, {
        'hedge_cny': 400, 'scaled_percent': 0.01, 'spread_percent': 1, 'amount_percent': 0.5,
        'defense_amount_percent': 1
    }],

    'threshold_10': [{
        'hedge_cny': 3 * w, 'scaled_percent': 0.045, 'spread_percent': 4, 'amount_percent': 0.1,
        'defense_amount_percent': 0.5
    }, {
        'hedge_cny': 2 * w, 'scaled_percent': 0.035, 'spread_percent': 2, 'amount_percent': 0.2,
        'defense_amount_percent': 0.8
    }, {
        'hedge_cny': 1500, 'scaled_percent': 0.025, 'spread_percent': 1.5, 'amount_percent': 0.3,
        'defense_amount_percent': 1
    }, {
        'hedge_cny': 800, 'scaled_percent': 0.025, 'spread_percent': 1.2, 'amount_percent': 0.4,
        'defense_amount_percent': 1
    }, {
        'hedge_cny': 300, 'scaled_percent': 0.015, 'spread_percent': 1, 'amount_percent': 0.5,
        'defense_amount_percent': 1
    }],
}

dangerous_scaled_percent = {
    0: {"near": 0.2, "defense": 0.8, "depth": 0.5},   # 稳定币
    1: {"near": 0.03, "defense": 0.3, "depth": 0.5},  # 友好
    2: {"near": 0.15, "defense": 0.5, "depth": 0.5},  # 紧凑
    3: {"near": 0.8, "defense": 1, "depth": 1},   # 普通
    4: {"near": 1, "defense": 1.2, "depth": 1.3},         # 稀疏， 观察区
    5: {"near": 1.3, "defense": 1.5, "depth": 1.5},
    6: {"near": 3, "defense": 3, "depth": 3},
    7: {"near": 5, "defense": 5, "depth": 5},
    8: {"near": 7, "defense": 7, "depth": 7},
    9: {"near": 9, "defense": 9, "depth": 9},
    10: {"near": 10, "defense": 10, "depth": 10},

}
