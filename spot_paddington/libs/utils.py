import numpy as np


def digit_to_string(d):
    return np.format_float_positional(d, trim='-')


def round_down(number, precision):
    return round(int(number * 10 ** precision) / 10 ** precision, precision)


def round_up(number, precision):
    return round(int(number * 10 ** precision + 1) / 10 ** precision, precision)


