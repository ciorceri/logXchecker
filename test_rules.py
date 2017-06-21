"""
Copyright 2016-2017 Ciorceri Petru Sorin

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
begindate=20130803
enddate=20130804
beginhour=1200
endhour=1159
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
begindate=20130803
enddate=20130803
beginhour=1200
endhour=1759
bands=band1,band2
"""
valid_period2_section = """
[period2]
begindate=20130804
enddate=20130804
beginhour=0600
endhour=1159
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
name=Single Operator Multi Band
regexp=somb
bands=band1,band2
"""
valid_category4_section = """
[category4]
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
              valid_category3_section + \
              valid_category4_section

valid_rules_sections = ['contest', 'log', 'band1', 'band2', 'period1', 'period2', 'category1', 'category2',
                        'category3', 'category4']

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
    ("""
[contest]
bands=0
periods=1
categories=1
""", 10),
    ("""
[contest]
bands=1
periods=1
categories=1
""", 11)
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
    ("""
[contest]
bands=1
periods=0
categories=1
""" + valid_band1_section, 10),
    ("""
[contest]
bands=1
periods=1
categories=1
""" + valid_band1_section, 12)

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

valid_minimal_contest_section = """
[contest]
name=Cupa Nasaud
begindate=20130803
enddate=20130804
beginhour=1200
endhour=1200
bands=1
periods=1
categories=1
"""

missing_band_section_in_period = [
    valid_minimal_contest_section +
    valid_band1_section +
    valid_category1_section +
    """
[period1]
begindate=20130803
enddate=20130804
beginhour=1200
endhour=2359
bands=band10
"""
]

missing_band_section_in_category = [
    valid_minimal_contest_section +
    valid_band1_section +
    valid_period1_section +
    """
[category1]
name=Single Operator 144
regexp=so|single
bands=band10
"""
]


class TestRules(TestCase):

    @mock.patch('os.path.isfile')
    def test_init(self, mock_isfile):
        mock_isfile.return_value = True
        mo = mock.mock_open(read_data=valid_rules)
        with patch('builtins.open', mo, create=True):
            _rules = rules.Rules('some_rule_file.rules')

        self.assertEqual(_rules.config.sections(), valid_rules_sections)
        self.assertEqual(_rules.contest_begin_date, '20130803')

        self.assertEqual(_rules.contest_end_date, '20130804')
        self.assertEqual(_rules.contest_begin_hour, '1200')
        self.assertEqual(_rules.contest_end_hour, '1159')

        self.assertEqual(_rules.contest_bands_nr, 2)
        self.assertEqual(_rules.contest_band(1)['band'], '144')
        self.assertEqual(_rules.contest_band(2)['band'], '432')

        self.assertEqual(_rules.contest_periods_nr, 2)
        self.assertEqual(_rules.contest_period(1)['begindate'], '20130803')
        self.assertEqual(_rules.contest_period(1)['enddate'], '20130803')
        self.assertEqual(_rules.contest_period(1)['beginhour'], '1200')
        self.assertEqual(_rules.contest_period(1)['endhour'], '1759')
        self.assertEqual(_rules.contest_period(1)['bands'], 'band1,band2')
        self.assertEqual(list(_rules.contest_period_bands(1)), ['band1', 'band2'])

        self.assertEqual(_rules.contest_categories_nr, 3)
        self.assertEqual(_rules.contest_category(1)['name'], 'Single Operator 144')
        self.assertEqual(_rules.contest_category(1)['regexp'], 'so|single')
        self.assertEqual(_rules.contest_category(1)['bands'], 'band1')
        self.assertEqual(_rules.contest_category(2)['name'], 'Single Operator 432')
        self.assertEqual(_rules.contest_category(2)['regexp'], 'so|single')
        self.assertEqual(_rules.contest_category(2)['bands'], 'band2')
        self.assertEqual(_rules.contest_category(3)['name'], 'Single Operator Multi Band')
        self.assertEqual(_rules.contest_category(3)['regexp'], 'somb')
        self.assertEqual(_rules.contest_category(3)['bands'], 'band1,band2')
        self.assertEqual(_rules.contest_category(4)['name'], 'Multi Operator')
        self.assertEqual(_rules.contest_category(4)['regexp'], 'mo|multi')
        self.assertEqual(_rules.contest_category(4)['bands'], 'band1,band2')

    def test_init_fail(self):
        # test 'file not found'
        self.assertRaises(FileNotFoundError, rules.Rules, 'some_missing_file.rules')

    @mock.patch('os.path.isfile')
    def test_read_config_file_content(self, mock_isfile):
        mock_isfile.return_value = True
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
                self.assertRaisesRegex(SystemExit, '^10$', rules.Rules, 'some_rule_file.rules')

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
        for rule_band, exit_code in missing_band_section:
            mo = mock.mock_open(read_data=rule_band)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(SystemExit, str(exit_code), rules.Rules, 'some_rule_file.rules')

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
        for rule_period, exit_code in missing_period_section:
            mo = mock.mock_open(read_data=rule_period)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(SystemExit, str(exit_code), rules.Rules, 'some_rule_file.rules')

    @mock.patch('os.path.isfile')
    def test_rules_category_syntax(self, mock_isfile):
        mock_isfile.return_value = True
        for rule_period in invalid_rules_categories_syntax:
            mo = mock.mock_open(read_data=rule_period)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(ValueError, "The rules have invalid 'categories' value in \[contest\] section",
                                       rules.Rules, 'some_rule_file.rules')

    @mock.patch('os.path.isfile')
    def test_missing_band_section_in_period(self, mock_isfile):
        mock_isfile.return_value = True
        for rule_period in missing_band_section_in_period:
            mo = mock.mock_open(read_data=rule_period)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(SystemExit, '^12$',
                                       rules.Rules, 'some_rule_file.rules')

    @mock.patch('os.path.isfile')
    def test_missing_band_section_in_category(self, mock_isfile):
        mock_isfile.return_value = True
        for rule_period in missing_band_section_in_category:
            mo = mock.mock_open(read_data=rule_period)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(SystemExit, '^12$',
                                       rules.Rules, 'some_rule_file.rules')
