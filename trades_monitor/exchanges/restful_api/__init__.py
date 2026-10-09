"""
币安下单限制：
        { # 每10秒50单
            "rateLimitType": "ORDERS",
            "interval": "SECOND",
            "intervalNum": 10,
            "limit": 50
        },
        {# 每1天160000单
            "rateLimitType": "ORDERS",
            "interval": "DAY",
            "intervalNum": 1,
            "limit": 160000
        },


"""