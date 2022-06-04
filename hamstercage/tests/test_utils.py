import io
import unittest
from datetime import datetime, timedelta

from hamstercage.utils import mode_to_str, short_date, print_table


class TestHamstercage(unittest.TestCase):
    def test_mode_to_str_ug_rw(self):
        assert mode_to_str("-", 0o660) == "-rw-rw----"

    def test_mode_to_str_one_each(self):
        assert mode_to_str("-", 0o124) == "---x-w-r--"

    def test_mode_to_str_ug_rw_us(self):
        assert mode_to_str("-", 0o4660) == "-rwSrw----"

    def test_mode_to_str_ug_rwx_gs(self):
        assert mode_to_str("-", 0o2770) == "-rwxrws---"

    def test_mode_to_str_ug_rwx_os(self):
        assert mode_to_str("-", 0o1770) == "-rwxrwx--T"

    def test_print_table_with_tabs(self):
        file = io.StringIO()

        print_table([["1.1", "1.2"], ["2.1", "2.2"]], file=file)

        assert file.getvalue() == "1.1\t1.2\n2.1\t2.2\n"

    def test_print_table_without_tabs(self):
        file = io.StringIO()

        print_table(
            [["1.1 long", "1.2 long"], ["2.1", "2.2"]],
            align=["<", ">"],
            file=file,
            tabs=False,
        )

        assert file.getvalue() == "1.1 long 1.2 long\n2.1      2.2\n"

    def test_short_date_now(self):
        t = datetime.now()
        assert short_date(int(t.timestamp())) == t.strftime("%H:%M")

    def test_short_date_yesterday(self):
        t = datetime.now() + timedelta(days=-1, seconds=-2)
        assert short_date(int(t.timestamp())) == t.strftime("%d.%m.")

    def test_short_date_9_months_ago(self):
        t = datetime.now() + timedelta(days=-9 * 30)
        assert short_date(int(t.timestamp())) == t.strftime("%Y")
