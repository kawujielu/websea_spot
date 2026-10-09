from config import SPOT_CURRENCY_CONFIG


def update_adj_args(symbol):
    currency = symbol.split("-")[0]
    base = symbol.split("-")[1]
    dangerous_level = SPOT_CURRENCY_CONFIG[currency]["dangerous_level"]

    if base in ["BTC", "ETH"]:
        near_price_percent = 0.001
        near_price_amount = 50
        defense_price_percent = 0.008
        defense_price_amount = 50
        depth_price_percent = 0.02
        depth_price_amount = 30
    elif base in ["USDT", ]:
        near_price_percent = 0.0003
        near_price_amount = 20
        defense_price_percent = 0.001
        defense_price_amount = 30
        depth_price_percent = 0.003
        depth_price_amount = 10
    else:
        near_price_percent = 0.0001
        near_price_amount = 20
        defense_price_percent = 0.001
        defense_price_amount = 30
        depth_price_percent = 0.003
        depth_price_amount = 10

    if dangerous_level == 1:
        near_price_percent = 0.00003
        near_price_amount = 20
        defense_price_percent = 0.0001
        defense_price_amount = 30
        depth_price_percent = 0.002
        depth_price_amount = 30
    elif dangerous_level == 2:
        near_price_percent = 0.0002
        near_price_amount = 20
        defense_price_percent = 0.0005
        defense_price_amount = 30
        depth_price_percent = 0.002
        depth_price_amount = 20
    elif 4 < dangerous_level < 11:
        near_price_percent = 0.0012
        near_price_amount = 450
        defense_price_percent = 0.003
        defense_price_amount = 150
        depth_price_percent = 0.03
        depth_price_amount = 30

    if currency in ["EURQ", "USDQ"]:
        near_price_percent = 0.0002
        near_price_amount = 5
        defense_price_percent = 0.0005
        defense_price_amount = 30
        depth_price_percent = 0.002
        depth_price_amount = 20

    return {
        "near_price_percent": near_price_percent,
        "near_price_amount": near_price_amount,
        "defense_price_percent": defense_price_percent,
        "defense_price_amount": defense_price_amount,
        "depth_price_percent": depth_price_percent,
        "depth_price_amount": depth_price_amount,
    }
