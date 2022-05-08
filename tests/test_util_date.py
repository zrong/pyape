from pyape.util.date import DateRange

def test_parse_month():
    date_text = '202104-202201'
    date_range = DateRange(date_text)
    assert date_range.is_range
    assert len(date_range) == 10
