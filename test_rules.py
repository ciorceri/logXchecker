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

valid_contest_section = """
[contest]
name=Cupa Nasaud
begindate=20160805
enddate=20160806
beginhour=1200
endhour=1200
bands=2
periods=2
categories=3
"""
valid_log_section = """
[log]
format=edi
"""
valid_band1_section = """
[band1]
band=144
regexp=144|145|2m
"""
valid_band2_section = """
[band2]
band=432
regexp=430|432|70cm
"""
valid_period1_section = """
[period1]
begindate=20160805
enddate=20160805
beginhour=1200
endhour=2359
bands=band1,band2
"""
valid_period2_section = """
[period2]
begindate=20160806
enddate=20160806
beginhour=0000
endhour=1200
bands=band1,band2
"""
valid_category1_section = """
[category1]
name=Single Operator 144
regexp=so|single
bands=band1
"""
valid_category2_section = """
[category2]
name=Single Operator 432
regexp=so|single
bands=band2
"""
valid_category3_section = """
[category3]
name=Multi Operator
regexp=mo|multi
bands=band1,band2
"""

valid_rules = valid_contest_section + \
              valid_log_section + \
              valid_band1_section + \
              valid_band2_section + \
              valid_period1_section + \
              valid_period2_section + \
              valid_category1_section + \
              valid_category2_section + \
              valid_category3_section

valid_rules_sections = ['contest', 'log', 'band1', 'band2', 'period1', 'period2', 'category1', 'category2', 'category3']

missing_contest_section_fields = [
    """
[contest]
""",
    """
[contest]
bands=1
""",
    """
[contest]
bands=1
periods=1
"""
]

invalid_bands_value = [
    """
[contest]
bands=
""",
    """
[contest]
bands=X
"""
]

missing_band_section = [
    """
[contest]
bands=0
periods=1
categories=1
""",
    """
[contest]
bands=1
periods=1
categories=1
"""
]

invalid_periods_value = [
    """
[contest]
bands=1
periods=
categories=1
""",
    """
[contest]
bands=1
periods=X
categories=1
"""
]

missing_period_section = [
    """
[contest]
bands=1
periods=0
categories=1
""" + valid_band1_section,
    """
[contest]
bands=1
periods=1
categories=1
""" + valid_band1_section

]

invalid_rules_categories_syntax = [
    """
[contest]
bands=1
categories=
periods=1
""" +
    valid_band1_section +
    valid_period1_section,
    """
[contest]
bands=1
periods=1
categories=X
""" +
    valid_band1_section +
    valid_period1_section
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
        self.assertEqual(_rules.contest_category(1)['name'], 'Single Operator 144')
        self.assertEqual(_rules.contest_category(1)['regexp'], 'so|single')
        self.assertEqual(_rules.contest_category(1)['bands'], 'band1')
        self.assertEqual(_rules.contest_category(2)['name'], 'Single Operator 432')
        self.assertEqual(_rules.contest_category(2)['regexp'], 'so|single')
        self.assertEqual(_rules.contest_category(2)['bands'], 'band2')
        self.assertEqual(_rules.contest_category(3)['name'], 'Multi Operator')
        self.assertEqual(_rules.contest_category(3)['regexp'], 'mo|multi')
        self.assertEqual(_rules.contest_category(3)['bands'], 'band1,band2')

    def test_init_fail(self):
        # test 'file not found'
        self.assertRaises(FileNotFoundError, rules.Rules, 'some_missing_file.rules')

    @mock.patch('os.path.isfile')
    def test_read_config_file_content(self, mock_isfile):
        mo = mock.mock_open(read_data=valid_rules)
        with patch('builtins.open', mo, create=True):
            _content = rules.Rules.read_config_file_content('some_rule_file.rules')
            self.assertEqual(_content, valid_rules)

    @mock.patch('os.path.isfile')
    def test_missing_contest_section_fields(self, mock_isfile):
        mock_isfile.return_value = True
        for rule_band in missing_contest_section_fields:
            mo = mock.mock_open(read_data=rule_band)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(SystemExit, '^9$', rules.Rules, 'some_rule_file.rules')

    @mock.patch('os.path.isfile')
    def test_invalid_bands_value(self, mock_isfile):
        mock_isfile.return_value = True
        for rule_band in invalid_bands_value:
            mo = mock.mock_open(read_data=rule_band)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(ValueError, "The rules have invalid 'bands' value in \[contest\] section",
                                       rules.Rules, 'some_rule_file.rules')

    @mock.patch('os.path.isfile')
    def test_missing_band_section(self, mock_isfile):
        mock_isfile.return_value = True
        for rule_band in missing_band_section:
            mo = mock.mock_open(read_data=rule_band)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(SystemExit, '^10$', rules.Rules, 'some_rule_file.rules')

    @mock.patch('os.path.isfile')
    def test_periods_value(self, mock_isfile):
        mock_isfile.return_value = True
        for rule_period in invalid_periods_value:
            mo = mock.mock_open(read_data=rule_period)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(ValueError, "The rules have invalid 'periods' value in \[contest\] section",
                                       rules.Rules, 'some_rule_file.rules')

    @mock.patch('os.path.isfile')
    def test_missing_period_section(self, mock_isfile):
        mock_isfile.return_value = True
        for rule_period in missing_period_section:
            mo = mock.mock_open(read_data=rule_period)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(SystemExit, '^11$', rules.Rules, 'some_rule_file.rules')

    @mock.patch('os.path.isfile')
    def test_rules_category_syntax(self, mock_isfile):
        mock_isfile.return_value = True
        for rule_period in invalid_rules_categories_syntax:
            mo = mock.mock_open(read_data=rule_period)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(ValueError, "The rules have invalid 'categories' value in \[contest\] section",
                                       rules.Rules, 'some_rule_file.rules')
