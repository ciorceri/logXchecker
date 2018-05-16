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

VALID_CONTEST_SECTION = r"""
[contest]
name=Cupa Nasaud
begindate=20130803
enddate=20130806
beginhour=1200
endhour=1159
bands=2
periods=2
categories=4
modes=1,2,6
"""
VALID_LOG_SECTION = r"""
[log]
format=edi
"""
VALID_BAND1_SECTION = r"""
[band1]
band=144
regexp=144|145|2m
"""
VALID_BAND2_SECTION = r"""
[band2]
band=432
regexp=430|432|70cm
"""
VALID_PERIOD1_SECTION = r"""
[period1]
begindate=20130803
enddate=20130803
beginhour=1200
endhour=1759
bands=band1,band2
"""
VALID_PERIOD2_SECTION = r"""
[period2]
begindate=20130804
enddate=20130806
beginhour=0600
endhour=1159
bands=band1,band2
"""
VALID_CATEGORY1_SECTION = r"""
[category1]
name=Single Operator 144
regexp=so|single
bands=band1
"""
VALID_CATEGORY2_SECTION = r"""
[category2]
name=Single Operator 432
regexp=so|single
bands=band2
"""
VALID_CATEGORY3_SECTION = r"""
[category3]
name=Single Operator Multi Band
regexp=somb
bands=band1,band2
"""
VALID_CATEGORY4_SECTION = """
[category4]
name=Multi Operator
regexp=mo|multi
bands=band1,band2
"""
VALID_EXTRA_FIELD = """
[extra]
name=yes
email=yes
address=no
"""

VALID_RULES = VALID_CONTEST_SECTION + \
              VALID_LOG_SECTION + \
              VALID_BAND1_SECTION + \
              VALID_BAND2_SECTION + \
              VALID_PERIOD1_SECTION + \
              VALID_PERIOD2_SECTION + \
              VALID_CATEGORY1_SECTION + \
              VALID_CATEGORY2_SECTION + \
              VALID_CATEGORY3_SECTION + \
              VALID_CATEGORY4_SECTION + \
              VALID_EXTRA_FIELD

VALID_RULES_SECTIONS = ['contest', 'log', 'band1', 'band2', 'period1', 'period2', 'category1', 'category2',
                        'category3', 'category4', 'extra']

MISSING_CONTEST_SECTION_FIELDS = [
    """
[contest]
""",
    """
[contest]
bands=1
periods=1
categories=1
""",
    """
[contest]
bands=1
periods=1
modes=1
""",
    """
[contest]
bands=1
categories=1
modes=1
""",
    """
[contest]
periods=1
categories=1
modes=1
"""
]

INVALID_MODES_VALUE = [
    """
[contest]
bands=1
periods=1
categories=1
modes=
""",
    """
[contest]
bands=1
periods=1
categories=1
modes=X
"""
]

INVALID_BANDS_VALUE = [
    """
[contest]
bands=
""",
    """
[contest]
bands=X
"""
]

MISSING_BAND_SECTION = [
    ("""
[contest]
bands=0
periods=1
categories=1
modes=1
""", 10),
    ("""
[contest]
bands=1
periods=1
categories=1
modes=1
""", 11)
]

INVALID_PERIODS_VALUE = [
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

MISSING_PERIOD_SECTION = [
    ("""
[contest]
bands=1
periods=0
categories=1
modes=1
""" + VALID_BAND1_SECTION, 10),
    ("""
[contest]
bands=1
periods=1
categories=1
modes=1
""" + VALID_BAND1_SECTION, 12)

]

INVALID_RULES_CATEGORIES_SYNTAX = [
    """
[contest]
bands=1
categories=
periods=1
""" +
    VALID_BAND1_SECTION +
    VALID_PERIOD1_SECTION,
    """
[contest]
bands=1
periods=1
categories=X
""" +
    VALID_BAND1_SECTION +
    VALID_PERIOD1_SECTION
]

VALID_MINIMAL_CONTEST_SECTION = """
[contest]
name=Cupa Nasaud
begindate=20130803
enddate=20130804
beginhour=1200
endhour=1200
bands=1
periods=1
categories=1
modes=1
"""

MISSING_BAND_SECTION_IN_PERIOD = [
    VALID_MINIMAL_CONTEST_SECTION +
    VALID_BAND1_SECTION +
    VALID_CATEGORY1_SECTION +
    """
[period1]
begindate=20130803
enddate=20130804
beginhour=1200
endhour=2359
bands=band10
"""
]

MISSING_BAND_SECTION_IN_CATEGORY = [
    VALID_MINIMAL_CONTEST_SECTION +
    VALID_BAND1_SECTION +
    VALID_PERIOD1_SECTION +
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
        mo = mock.mock_open(read_data=VALID_RULES)
        with patch('builtins.open', mo, create=True):
            _rules = rules.Rules('some_rule_file.rules')

        self.assertEqual(_rules.config.sections(), VALID_RULES_SECTIONS)
        self.assertEqual(_rules.contest_begin_date, '20130803')

        self.assertEqual(_rules.contest_end_date, '20130806')
        self.assertEqual(_rules.contest_begin_hour, '1200')
        self.assertEqual(_rules.contest_end_hour, '1159')

        self.assertEqual(_rules.contest_bands_nr, 2)
        self.assertEqual(_rules.contest_band(1)['band'], '144')
        self.assertEqual(_rules.contest_band(2)['band'], '432')

        self.assertEqual(_rules.contest_qso_modes, [1, 2, 6])

        self.assertEqual(_rules.contest_periods_nr, 2)
        self.assertEqual(_rules.contest_period(1)['begindate'], '20130803')
        self.assertEqual(_rules.contest_period(1)['enddate'], '20130803')
        self.assertEqual(_rules.contest_period(1)['beginhour'], '1200')
        self.assertEqual(_rules.contest_period(1)['endhour'], '1759')
        self.assertEqual(_rules.contest_period(1)['bands'], 'band1,band2')
        self.assertEqual(list(_rules.contest_period_bands(1)), ['band1', 'band2'])

        self.assertEqual(_rules.contest_categories_nr, 4)
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
        self.assertEqual(_rules.contest_extra_field, ['name', 'email'])

    def test_init_fail(self):
        # test 'file not found'
        self.assertRaises(FileNotFoundError, rules.Rules, 'some_missing_file.rules')

    @mock.patch('os.path.isfile')
    def test_read_config_file_content(self, mock_isfile):
        mock_isfile.return_value = True
        mo = mock.mock_open(read_data=VALID_RULES)
        with patch('builtins.open', mo, create=True):
            _content = rules.Rules.read_config_file_content('some_rule_file.rules')
            self.assertEqual(_content, VALID_RULES)

    @mock.patch('os.path.isfile')
    def test_missing_contest_section_fields(self, mock_isfile):
        mock_isfile.return_value = True
        for rule_band in MISSING_CONTEST_SECTION_FIELDS:
            mo = mock.mock_open(read_data=rule_band)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(SystemExit, '^10$', rules.Rules, 'some_rule_file.rules')

    @mock.patch('os.path.isfile')
    def test_invalid_modes_value(self, mock_isfile):
        mock_isfile.return_value = True
        for mode_value in INVALID_MODES_VALUE:
            mo = mock.mock_open(read_data=mode_value)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(ValueError, "The rules have invalid 'modes' value in \[contest\] section", rules.Rules, 'some_rule_file.rules')

    @mock.patch('os.path.isfile')
    def test_invalid_bands_value(self, mock_isfile):
        mock_isfile.return_value = True
        for rule_band in INVALID_BANDS_VALUE:
            mo = mock.mock_open(read_data=rule_band)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(ValueError, "The rules have invalid 'bands' value in \[contest\] section",
                                       rules.Rules, 'some_rule_file.rules')

    @mock.patch('os.path.isfile')
    def test_missing_band_section(self, mock_isfile):
        mock_isfile.return_value = True
        for rule_band, exit_code in MISSING_BAND_SECTION:
            mo = mock.mock_open(read_data=rule_band)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(SystemExit, str(exit_code), rules.Rules, 'some_rule_file.rules')

    @mock.patch('os.path.isfile')
    def test_periods_value(self, mock_isfile):
        mock_isfile.return_value = True
        for rule_period in INVALID_PERIODS_VALUE:
            mo = mock.mock_open(read_data=rule_period)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(ValueError, "The rules have invalid 'periods' value in \[contest\] section",
                                       rules.Rules, 'some_rule_file.rules')

    @mock.patch('os.path.isfile')
    def test_missing_period_section(self, mock_isfile):
        mock_isfile.return_value = True
        for rule_period, exit_code in MISSING_PERIOD_SECTION:
            mo = mock.mock_open(read_data=rule_period)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(SystemExit, str(exit_code), rules.Rules, 'some_rule_file.rules')

    @mock.patch('os.path.isfile')
    def test_rules_category_syntax(self, mock_isfile):
        mock_isfile.return_value = True
        for rule_period in INVALID_RULES_CATEGORIES_SYNTAX:
            mo = mock.mock_open(read_data=rule_period)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(ValueError, "The rules have invalid 'categories' value in \[contest\] section",
                                       rules.Rules, 'some_rule_file.rules')

    @mock.patch('os.path.isfile')
    def test_missing_band_section_in_period(self, mock_isfile):
        mock_isfile.return_value = True
        for rule_period in MISSING_BAND_SECTION_IN_PERIOD:
            mo = mock.mock_open(read_data=rule_period)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(SystemExit, '^12$',
                                       rules.Rules, 'some_rule_file.rules')

    @mock.patch('os.path.isfile')
    def test_missing_band_section_in_category(self, mock_isfile):
        mock_isfile.return_value = True
        for rule_period in MISSING_BAND_SECTION_IN_CATEGORY:
            mo = mock.mock_open(read_data=rule_period)
            with patch('builtins.open', mo, create=True):
                self.assertRaisesRegex(SystemExit, '^12$',
                                       rules.Rules, 'some_rule_file.rules')
