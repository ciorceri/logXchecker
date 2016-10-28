"""
Copyright 2016 Ciorceri Petru Sorin

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from unittest import TestCase
from unittest import mock
from unittest.mock import mock_open, patch

import rules

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
enddate=20160806
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

invalid_rules_band_syntax = [
"""
[contest]
bands=
""" ,
"""
[contest]
bands=X
"""
]

invalid_rules_band = [
"""
[contest]
bands=0
""" ,
"""
[contest]
bands=1
"""
]

invalid_rules_period_syntax = [
"""
[contest]
periods=
""" ,
"""
[contest]
periods=X
""",

]


invalid_rules_period = [
"""
[contest]
bands=1
periods=1

[band1]
band=144
regexp=(144|145|2m)
""",
]


class TestRules(TestCase):
    @mock.patch('os.path.isfile')
    def test_init(self, mock_isfile):
        mock_isfile.return_value = True
        mo = mock.mock_open(read_data=valid_rules)
        with patch('builtins.open', mo, create=True):
            _rules = rules.Rules('some_rule_file.rules')

        self.assertEqual(_rules.config.sections(), valid_rules_sections)
        self.assertEqual(_rules.contest_begin_date, '20160805')

        self.assertEqual(_rules.contest_end_date, '20160806')
        self.assertEqual(_rules.contest_begin_hour, '1200')
        self.assertEqual(_rules.contest_end_hour, '1200')

        self.assertEqual(_rules.contest_bands_nr, 2)
        self.assertEqual(_rules.contest_band(1)['band'], '144')
        self.assertEqual(_rules.contest_band(2)['band'], '432')

        self.assertEqual(_rules.contest_periods_nr, 2)
        self.assertEqual(_rules.contest_period(1)['begindate'], '20160805')
        self.assertEqual(_rules.contest_period(1)['enddate'], '20160805')
        self.assertEqual(_rules.contest_period(1)['beginhour'], '1200')
        self.assertEqual(_rules.contest_period(1)['endhour'], '2359')
        self.assertEqual(_rules.contest_period(1)['bands'], 'band1,band2')
        self.assertEqual(list(_rules.contest_period_bands(1)), ['band1', 'band2'])

        self.assertEqual(_rules.contest_categories_nr, 3)

    def test_init_fail(self):
        # test 'file not found'
        self.assertRaises(FileNotFoundError, rules.Rules, 'some_missing_file.rules')

    @mock.patch('os.path.isfile')
    def test_rules_band_syntax_validation(self, mock_isfile):
        mock_isfile.return_value = True
        for rule_band in invalid_rules_band_syntax:
            mo = mock.mock_open(read_data=rule_band)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(ValueError, 'The bands value is not valid', rules.Rules, 'some_rule_file.rules')

    @mock.patch('os.path.isfile')
    def test_rules_band_validation(self, mock_isfile):
        mock_isfile.return_value = True
        for rule_band in invalid_rules_band:
            mo = mock.mock_open(read_data=rule_band)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(SystemExit, '^10$', rules.Rules, 'some_rule_file.rules')

    @mock.patch('os.path.isfile')
    def test_rules_period_syntax_validation(self, mock_isfile):
        mock_isfile.return_value = True
        for rule_period in invalid_rules_period_syntax:
            mo = mock.mock_open(read_data=rule_period)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(ValueError, 'The bands value is not valid', rules.Rules, 'some_rule_file.rules')

    @mock.patch('os.path.isfile')
    def test_rules_period_validation(self, mock_isfile):
        mock_isfile.return_value = True
        for rule_period in invalid_rules_period:
            mo = mock.mock_open(read_data=rule_period)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(SystemExit, '^11$', rules.Rules, 'some_rule_file.rules')
