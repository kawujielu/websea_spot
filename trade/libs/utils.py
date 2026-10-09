from loguru import logger
import traceback
import numpy as np


def transfer_symbols(trans_symbols, symbol):
    try:
        return trans_symbols[symbol]
    except Exception as e:
        logger.error(f"{repr(e)} \n{traceback.format_exc()}")
        return None


def digit_to_string(d):
    return np.format_float_positional(d, trim='-')


