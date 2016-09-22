from unittest import TestCase
from unittest import mock
from unittest.mock import mock_open, patch

import logXchecker

valid_rules = """
[contest]
name=Cupa Nasaud
begindate=20160805
enddate=20160806
beginhour=1200
endhour=1200
bands=2
periods=2
categories=3

[log]
format=edi

[band1]
band=144
regexp=(144|145|2m)

[band2]
band=432
regexp=(430|432|70cm)

[period1]
begindate=20160805
enddate=20160805
beginhour=1200
endhour=2359
bands=band1,band2

[period2]
begindate=20160806
enddate=201608086
beginhour=0000
endhour=1200
bands=band1,band2

[category1]
name=Single Operator 144
regexp=(so|single)
bands=band1

[category2]
name=Single Operator 432
regexp=(so|single)
bands=band2

[category3]
name=Multi Operator
regexp=(mo|multi)
bands=band1,band2
"""

valid_rules_sections = ['contest', 'log', 'band1', 'band2', 'period1', 'period2', 'category1', 'category2', 'category3']


class TestRules(TestCase):
    @mock.patch('os.path.isfile')
    def test_init(self, mock_isfile):
        mock_isfile.return_value = True
        mo = mock.mock_open(read_data=valid_rules)
        with patch('builtins.open', mo, create=True):
            rules = logXchecker.Rules('some_rule_file.rules')

        self.assertEqual(rules.config.sections(), valid_rules_sections)
        self.assertEqual(rules.contest_begin_date, '20160805')

        self.assertEqual(rules.contest_end_date, '20160806')
        self.assertEqual(rules.contest_begin_hour, '1200')
        self.assertEqual(rules.contest_end_hour, '1200')

        self.assertEqual(rules.contest_bands_nr, 2)
        self.assertEqual(rules.contest_band(1)['band'], '144')
        self.assertEqual(rules.contest_band(2)['band'], '432')

        self.assertEqual(rules.contest_periods_nr, 2)
        self.assertEqual(rules.contest_period(1)['begindate'], '20160805')
        self.assertEqual(rules.contest_period(1)['enddate'], '20160805')
        self.assertEqual(rules.contest_period(1)['beginhour'], '1200')
        self.assertEqual(rules.contest_period(1)['endhour'], '2359')
        self.assertEqual(rules.contest_period(1)['bands'], 'band1,band2')
        self.assertEqual(list(rules.contest_period_bands(1)), ['band1', 'band2'])

        self.assertEqual(rules.contest_categories_nr, 3)
