import time, datetime, calendar


class ATime:

    # 获取当前年份每个月的首天和最后一天，本月最后一天取本日数据
    def getYearMonthsDay(self):
        result = {}
        # 获取当前年份
        thisYear = datetime.date.today().year
        # 获取当前月份
        thisMonth = datetime.date.today().month
        # 获取当前天
        thisDay = datetime.date.today().day
        for x in range(1, thisMonth + 1):
            monthRange = calendar.monthrange(thisYear, x)[1]
            startDay = str(thisYear) + "-" + str(x).zfill(2) + "-01" + ' 00:00:00'
            endDay = str(thisYear) + "-" + str(x).zfill(2) + "-"
            # 如果不想本月取最后一天取当前日期，可不做判断，直接用endDay = endDay + str(monthRange).zfill(2)
            if x == thisMonth:
                endDay = endDay + str(thisDay).zfill(2) + ' 00:00:00'
            else:
                endDay = endDay + str(monthRange).zfill(2) + ' 00:00:00'
            result[str(x)] = [startDay, endDay]
        return result

    # 时间格式转化为时间戳
    def timearray_to_timestamp(self, dt):
        # 转换为时间数组
        timeArray = time.strptime(dt, "%Y-%m-%d %H:%M:%S")
        # 转换为时间戳
        timestamp = time.mktime(timeArray).__int__()
        return timestamp

    # 实践戳转化为时间格式
    def timestamp_to_timearray(self, timestamp):
        # timestamp = 1462451334
        # 转换为localtime
        time_local = time.localtime(timestamp)
        # 转换为新的时间格式
        dt = time.strftime("%Y-%m-%d %H:%M:%S", time_local)
        return dt

    # 每天凌晨的数据
    def today_zero(self):
        today_data = datetime.datetime.now().date()
        date_zero_time = int(time.mktime(today_data.timetuple()))
        print('--', date_zero_time)
        day_time = time.localtime(date_zero_time)
        time_zero = time.strftime('%Y-%m-%d %H:%M:%S', day_time)
        return time_zero, date_zero_time


if __name__ == '__main__':
    time_zero, date_zero_time = ATime().today_zero()
    print(time_zero, date_zero_time)
    mm = ATime().getYearMonthsDay()
    print(mm)
