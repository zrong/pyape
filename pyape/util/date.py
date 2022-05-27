"""
pyape.util.date
~~~~~~~~~~~~~~~~~~~

日期相关的小工具

@author zrong
@created 2022-05-08
"""
from datetime import date, datetime, timedelta
from typing import Any, Union, Callable
from collections.abc import Iterable, Iterator


class DateRange(Iterable):
    """ 根据提供的字符串获取日期列表。

    :param date_text: 月份字符串
        单年：2020
        多年：2019,2020
        年范围：2019-2020
        单月：202012
        多月：202012,202103
        月范围：202009-20210
        单日： 20200724
        多日： 20200724,20210103,20220321
        日范围： 20200724-20220301
        
    :param last_month: 停止在提供的这个月，仅当提供的是年或者月的时候有效。
    :raise ValueError: 如果月份检测不合格抛出 ValueError。
    """

    DATE_FMT: str = '%Y%m%d'
    MONTH_FMT: str = '%Y%m'

    date_type: str = None
    """ 日期类型，值可以是 year/month/date。"""

    date_text: str = None
    """ 输入的日期字符串。"""

    last_month: int = None
    """ 当提供的是年数据时，默认行为是生成这一年的所有月。但有时需要部分月，提供这个参数可以让月份停止在 last_month。"""

    is_range: bool = False
    """ 日期是否为 range 类型，输入字符串中使用 - 分隔两个日期的为 range 类型。"""

    parsed_date: list[str] = None

    def __init__(self, date_text: str, last_month: int = None) -> None:
        if not isinstance(date_text, str) or not date_text.strip():
            raise ValueError(f'提供的日期 {date_text} 不正确！')

        self.date_text = date_text
        self.last_month = last_month

        if date_text.find(',') > 0:
            # 删除重复值，int 为了确保日期是合法整数，str 是方便后面使用 strptime
            parsed_date: list[str] = self.__check_dupli(date_text.split(','))
            self.parsed_date = parsed_date
            self.is_range = False
        # 提供的是范围
        elif date_text.find('-') > 0:
            # 删除重复值，int 为了确保日期是合法整数，str 是方便后面使用 strptime
            parsed_date: list[str] = self.__check_dupli(date_text.split('-'))
            # 不允许的范围表达
            if len(parsed_date) > 2:
                raise ValueError(f'提供的日期 {date_text} 不正确！')
            self.parsed_date = parsed_date
            self.is_range = len(parsed_date) == 2
            if self.is_range:
                if int(self.parsed_date[0]) > int(self.parsed_date[1]):
                    self.parsed_date = [self.parsed_date[1], self.parsed_date[0]]
        else:
            self.is_range = False
            self.parsed_date = [date_text]

        date_len: set[int] = {len(d) for d in self.parsed_date}
        if len(date_len) > 1:
            raise ValueError(f'提供的日期 {date_text} 长度不一致！')

        check_date_len: int = date_len.pop()
        # 使用的是日期
        if check_date_len == 8:
            self.date_type = 'date'
        elif check_date_len == 6:
            self.date_type = 'month'
        elif check_date_len == 4:
            self.date_type = 'year'
        else:
            raise ValueError(f'提供的日期 {date_text} 长度不正确，仅支持 8/6/4 三种日期长度。')

    def __iter__(self) -> Iterator:
        return iter(self.to_list())

    def __len__(self) -> int:
        return len(self.to_list())

    def __check_dupli(self, parsed_date: list[str]) -> list[str]:
        """ 删除重复值，int 为了确保日期是合法整数，str 是方便后面使用 strptime。"""
        return [str(dl) for dl in {int(d) for d in parsed_date}]

    def __range_star_or_end(
        self, index: int, type_: Callable = str
    ) -> Union[int, datetime, str]:
        if not self.is_range:
            return None
        s = self.parsed_date[index]
        if type_ == datetime:
            if self.date_type == 'date':
                return datetime.strptime(s, self.DATE_FMT)
            elif self.date_type == 'month':
                return datetime.strptime(s, self.MONTH_FMT)
            return datetime(int(s), 1, 1)
        return type_(s)

    def range_start(self, type_: Callable = str) -> Union[int, datetime, str]:
        return self.__range_star_or_end(0, type_)

    def range_end(self, type_: Callable = str) -> Union[int, datetime, str]:
        return self.__range_star_or_end(1, type_)

    def to_list(self) -> list[int]:
        """ 根据当前 date_type 导出不同的 list。"""
        if self.date_type == 'date':
            return self.to_date_list()
        return self.to_month_list()

    def to_date_list(self) -> list[int]:
        """ 导出一个 8 位 date 列表。

        :return list[int]: 返回 %Y%m%d 的整数形式列表。
        """
        if self.date_type != 'date':
            raise TypeError('请确保 date_type 为 date！')
        if self.is_range:
            # 小值在前
            start: datetime = self.range_start(datetime)
            end: datetime = self.range_end(datetime)
            date_list: list[int] = []
            # 构建日期列表
            for i in range((end - start).days + 1):
                day = start + timedelta(days=i)
                date_list.append(int(day.strftime(self.DATE_FMT)))
            return date_list
        return [
            int(datetime.strptime(date_str, self.DATE_FMT).strftime(self.DATE_FMT))
            for date_str in self.parsed_date
        ]

    def to_month_list(self) -> list[int]:
        """ 导出一个 6 位 month 列表。

        :return list[int]: 返回 %Y%m 的整数形式列表。
        """
        if not self.date_type in ('month', 'year'):
            raise TypeError('请确保 date_type 为 month 或 year！')

        year2monthlist = lambda y: [int(f'{y}{m:0>2d}') for m in range(1, 13)]
        month = []
        if self.is_range:
            # 使用的是月份
            if self.date_type == 'month':
                start = self.range_start(datetime)
                end = self.range_end(datetime)
                y_start = start.year
                m_start = start.month
                y_end = end.year
                m_end = end.month
                y = y_start
                while y <= y_end:
                    for m in range(1, 13):
                        # 开始年份要判断 y_start
                        if y == y_start and m < m_start:
                            continue
                        # 结束年份要判断 y_end
                        if y == y_end and m > m_end:
                            continue
                        month.append(int(f'{y}{m:0>2d}'))
                    y += 1
            # 使用的年份
            else:
                y_start = int(self.parsed_date[0])
                y_end = int(self.parsed_date[1])
                y = y_start
                while y <= y_end:
                    month.extend(year2monthlist(y))
                    y += 1
        # 提供的是列表
        else:
            # 使用的是月份
            if self.date_type == 'month':
                month = [int(m) for m in self.parsed_date]
            # 使用的年份
            else:
                for y in self.parsed_date:
                    month.extend(year2monthlist(y))
        # 检测月份是否正规
        [datetime.strptime(str(m), self.MONTH_FMT) for m in month]
        if self.last_month is not None:
            return [m for m in month if m <= self.last_month]
        return month

    def to_year_list(self) -> list[int]:
        """ 导出一个 4 为的 year 列表。

        :return list[int]: 返回 %Y 的整数形式列表。
        """
        month_list = self.to_month_list()
        year_list = [int(month/100) for month in month_list]
        # 去重
        return list(set(year_list))



def date_interval(
    date1: Union[int, datetime], date2: Union[int, datetime], fmt: str = '%Y%m%d'
) -> int:
    d1: datetime = datetime.strptime(str(date1), fmt) if isinstance(
        date1, int
    ) else date1
    d2: datetime = datetime.strptime(str(date2), fmt) if isinstance(
        date2, int
    ) else date2
    d: timedelta = d1 - d2
    return abs(d.days)


def get_years(start: int = 2017, end: int = None) -> list[int]:
    """ 获取年份列表。
    
    :param start: 开始的年份。
    :param end: 结束的年份。若值为 None 代表今年。
    """
    if end is None:
        now = date.today()
        return range(start, now.year + 1)
    return range(start, end + 1)


def get_last_month(month: int = None) -> int:
    """ 获取上一个月的 %Y%m 表达。

    :param month: 获取 month 的上一个月。若 month 为 None，则使用 today。
    """
    if month is None:
        today = date.today()
    else:
        today = datetime.strptime(str(month), '%Y%m')
    last_month = today - timedelta(days=today.day)
    return int(last_month.strftime('%Y%m'))


def get_last_12month(month: int = None) -> str:
    """ 获取最近 12 个月的 %Y%m 表达，形如 202104-202203。

    :param month: 获取 month 的上一个月。若 month 为 None，则使用 today。
    """
    year_month = get_last_month(month)
    dt = datetime.strptime(str(year_month), '%Y%m')
    last_12month = dt - timedelta(days=365)
    return last_12month.strftime('%Y%m') + '-' + dt.strftime('%Y%m')


def gen_month(year: int, start: int = 1, end: int = 12, type_: Callable = int) -> list:
    """ 生成月份列表。"""
    return [type_(f'{year}{md:02}') for md in range(start, end + 1)]


def from_month(month_text: str, last_month: int = None, use_year: bool=False) -> list[int]:
    """ 根据提供的字符串获取日期列表。

    :param month_text: 月份字符串
        单年：2020
        多年：2019,2020
        年范围：2019-2020
        单月：202012
        多月：202012,202103
        月范围：202009-20210
    :param last_month: 停止在提供的这个月。
    :param year_list: 返回年份列表而不是月份列表。
    :raise ValueError: 如果月份检测不合格抛出 ValueError。
    :return list[int]: 返回 %Y%m 的整数形式列表。
    """
    dr = DateRange(month_text, last_month)
    if use_year:
        return dr.to_year_list()
    return dr.to_month_list()


def month2date(month_text: str, last: bool = False) -> int:
    """ 将一个 month_text 转换成一个日期
    如果提供的年，则转换为当年的一个日期
    如果提供的是月，则转换为当月的一个日期
    若提供的是日期，则直接转换为整数

    :param month_text: 见 from_month
    :param last: 若为 True 转换为最后日期，否则转换为首日
    """
    if len(month_text) == 8:
        return int(month_text)
    mlist = from_month(month_text)
    m = mlist[-1] if last else mlist[0]
    # 找到该月的最后一天
    if last:
        next_month = date(int(str(m)[:4]), int(str(m)[4:6]), 28) + timedelta(days=4)
        d = next_month - timedelta(days=next_month.day)
        return int(d.strftime('%Y%m%d'))
    return int(f'{m}01')
