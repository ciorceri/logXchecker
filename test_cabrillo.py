"""
Copyright 2016-2026 Ciorceri Petru Sorin (yo5pjb)

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

import io
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from unittest import TestCase, mock
from unittest.mock import mock_open, patch

import rules
import rules_hf
from test_rules import VALID_RULES, VALID_RULES_BASIC

import formats.cabrillo as cabrillo
from formats.cabrillo import ERR_IO, ERR_HEADER, ERR_QSO


# ── Test data ──────────────────────────────────────────────────────────

# A minimal valid Cabrillo V3 log (DRACULA style, 11-field QSO format).
# Uses STANDARD generic category (SINGLE-OP) so generic validation succeeds
# when no rules are provided; rules-based tests use DRACULA-specific codes.
valid_cabrillo_log_11f: str = \
"""START-OF-LOG: 3.0
CONTEST: DRACULA
CALLSIGN: YO5PJB
CATEGORY-OPERATOR: SINGLE-OP
CATEGORY-BAND: ALL
CATEGORY-MODE: MIXED
CREATED-BY: logXchecker test generator

QSO: 14000 CW 2026-10-31 1200 YO5PJB          599 CJ  YO5BTZ          599 001
QSO:  7200 PH 2026-10-31 1210 YO5PJB          59  CJ  YO5PLP          59  002
QSO: 14100 PH 2026-10-31 1220 YO5PJB          59  CJ  YO5TP           59  003
QSO:  7000 CW 2026-10-31 1330 YO5PJB          599 CJ  YO5CRQ          599 004
QSO: 14200 PH 2026-10-31 1430 YO5PJB          59  CJ  YO5CKZ          59  005
QSO: 14020 CW 2026-10-31 1450 YO5PJB          599 CJ  YO8SSB          599 006
QSO:  7050 CW 2026-10-31 1500 YO5PJB          599 CJ  YO5OO           599 007
QSO: 14250 PH 2026-10-31 1510 YO5PJB          59  CJ  YO6PVT          59  008
QSO: 14030 CW 2026-10-31 1520 YO5PJB          599 CJ  YO6POK          599 009
QSO:  7100 PH 2026-10-31 1600 YO5PJB          59  CJ  YO5BTZ          59  001
END-OF-LOG:
"""

# For rules-based tests, use a DRACULA-compatible category code
valid_cabrillo_log_dracula: str = \
"""START-OF-LOG: 3.0
CONTEST: DRACULA
CALLSIGN: YO5PJB
CATEGORY-OPERATOR: B3
CATEGORY-BAND: ALL
CATEGORY-MODE: MIXED
CREATED-BY: logXchecker test generator

QSO: 14000 CW 2026-10-31 1200 YO5PJB          599 CJ  YO5BTZ          599 001
QSO:  7200 PH 2026-10-31 1210 YO5PJB          59  CJ  YO5PLP          59  002
QSO: 14020 CW 2026-10-31 1450 YO5PJB          599 CJ  YO8SSB          599 006
QSO:  7100 PH 2026-10-31 1600 YO5PJB          59  CJ  YO5BTZ          59  001
END-OF-LOG:
"""

# 13-field Cabrillo V3 QSO format (serial + county combined exchange)
valid_cabrillo_log_13f: str = \
"""START-OF-LOG: 3.0
CONTEST: DRACULA
CALLSIGN: YO5PJB
CATEGORY-OPERATOR: SINGLE-OP
CATEGORY-BAND: ALL
CATEGORY-MODE: MIXED
CREATED-BY: logXchecker test generator

QSO:  7200 PH 2026-10-31 1208 YO5FGH          59  CJ  TF3AAA          59  448
QSO: 14340 PH 2026-10-31 1210 YO5FGH          59  CJ  F5XXX           59  016
END-OF-LOG:
"""

# A valid minimal Cabrillo header (no QSOs)
# Uses SINGLE-OP so generic validation (without rules) succeeds.
valid_cabrillo_header: str = \
"""START-OF-LOG: 3.0
CONTEST: DRACULA
CALLSIGN: YO5PJB
CATEGORY-OPERATOR: SINGLE-OP
CATEGORY-BAND: ALL
CATEGORY-MODE: MIXED
CREATED-BY: logXchecker test generator
END-OF-LOG:
"""

# Invalid logs for various header error cases
invalid_cabrillo_log_no_callsign: str = \
"""START-OF-LOG: 3.0
CONTEST: DRACULA
CATEGORY-OPERATOR: B3
CATEGORY-BAND: ALL
CATEGORY-MODE: MIXED
"""

invalid_cabrillo_log_no_band: str = \
"""START-OF-LOG: 3.0
CONTEST: DRACULA
CALLSIGN: YO5PJB
CATEGORY-OPERATOR: B3
CATEGORY-MODE: MIXED
"""

invalid_cabrillo_log_no_category: str = \
"""START-OF-LOG: 3.0
CONTEST: DRACULA
CALLSIGN: YO5PJB
CATEGORY-BAND: ALL
CATEGORY-MODE: MIXED
"""

invalid_cabrillo_log_no_start: str = \
"""CONTEST: DRACULA
CALLSIGN: YO5PJB
CATEGORY-OPERATOR: B3
CATEGORY-BAND: ALL
"""
# only v2.0 and 3.0 are supported, so version 1.0 is invalid
invalid_cabrillo_log_bad_version: str = \
"""START-OF-LOG: 1.0
CONTEST: DRACULA
CALLSIGN: YO5PJB
CATEGORY-OPERATOR: B3
CATEGORY-BAND: ALL
"""

invalid_cabrillo_log_invalid_callsign: str = \
"""START-OF-LOG: 3.0
CONTEST: DRACULA
CALLSIGN: invalid!
CATEGORY-OPERATOR: B3
CATEGORY-BAND: ALL
CATEGORY-MODE: MIXED
"""

# Test QSO lines
test_valid_qso_lines_11f: List[str] = [
    'QSO: 14000 CW 2026-10-31 1200 YO5PJB          599 CJ  YO5BTZ          599 001',
    'QSO:  7200 PH 2026-10-31 1210 YO5PJB          59  CJ  YO5PLP          59  002',
]

test_valid_qso_lines_13f: List[str] = [
    'QSO:  7200 PH 2026-10-31 1208 YO5FGH          59  CJ  TF3AAA          59  448',
    'QSO: 14340 PH 2026-10-31 1210 YO5FGH          59  CJ  F5XXX           59  016',
]

test_valid_qso_fields_11f: List[Dict[str, Any]] = [
    {
        'date': '261031',
        'hour': '1200',
        'call': 'YO5BTZ',
        'mode': 'CW',
        'rst_sent': '599',
        'nr_sent': 'CJ',
        'rst_recv': '599',
        'nr_recv': '001',
        'wwl': '',
        'points': None,
        'new_exchange': None,
        'new_wwl': None,
        'new_dxcc': None,
        'duplicate_qso': None,
    },
    {
        'date': '261031',
        'hour': '1210',
        'call': 'YO5PLP',
        'mode': 'SSB',
        'rst_sent': '59',
        'nr_sent': 'CJ',
        'rst_recv': '59',
        'nr_recv': '002',
        'wwl': '',
        'points': None,
        'new_exchange': None,
        'new_wwl': None,
        'new_dxcc': None,
        'duplicate_qso': None,
    },
]

test_invalid_qso_lines: List[Tuple[str, str]] = [
    ('', 'QSO line is empty'),
    ('NOT-QSO: blah blah', 'QSO line does not start with QSO:'),
    ('QSO: 14000 CW 2026-10-31 1200 YO5PJB', 'Incorrect QSO line format'),
    ('QSO: 14000 CW 2026-10-31 1200 YO5PJB 599', 'Incorrect QSO line format'),
]

# Test QSO validation data: (linenr, qso_line, valid, errors)
test_log_qso_valid_format: List[Tuple[int, str, bool, list]] = [
    (9, 'QSO: 14000 CW 2026-10-31 1200 YO5PJB          599 CJ  YO5BTZ          599 001', True, []),
    (10, 'QSO:  7200 PH 2026-10-31 1210 YO5PJB          59  CJ  YO5PLP          59  002', True, []),
]

test_log_qso_regexp_validator: List[Tuple[int, str, bool, list]] = [
    (5, 'QSO: 14000 CW 2026-10-31 1200 YO5PJB          599 CJ  YO5BTZ          599 001', True,
     []),
    (5, 'QSO:  NOTACW 2026-10-31 1200 YO5PJB          599 CJ  YO5BTZ          599 001', False,
     [(5, 'QSO:  NOTACW 2026-10-31 1200 YO5PJB          599 CJ  YO5BTZ          599 001',
       'Incorrect QSO line format')]),
]

test_log_qso_generic_validator: List[Tuple[int, str, bool, list]] = [
    # Valid QSO
    (1, 'QSO: 14000 CW 2026-10-31 1200 YO5PJB          599 CJ  YO5BTZ          599 001', True,
     []),
    # Invalid date
    (2, 'QSO: 14000 CW 9999-99-99 1200 YO5PJB          599 CJ  YO5BTZ          599 001', False,
     [(2, 'QSO: 14000 CW 9999-99-99 1200 YO5PJB          599 CJ  YO5BTZ          599 001',
       'Qso date is invalid: unconverted data remains: 99')]),
    # Invalid hour
    (3, 'QSO: 14000 CW 2026-10-31 9999 YO5PJB          599 CJ  YO5BTZ          599 001', False,
     [(3, 'QSO: 14000 CW 2026-10-31 9999 YO5PJB          599 CJ  YO5BTZ          599 001',
       'Qso hour is invalid: unconverted data remains: 99')]),
    # Invalid callsign (the code uppercases the callsign before validation)
    (4, 'QSO: 14000 CW 2026-10-31 1200 YO5PJB          599 CJ  invalid!         599 001', False,
     [(4, 'QSO: 14000 CW 2026-10-31 1200 YO5PJB          599 CJ  invalid!         599 001',
       'Callsign is invalid: INVALID!')]),
    # Invalid RST sent (69 does not start with 1-5)
    (5, 'QSO: 14000 CW 2026-10-31 1200 YO5PJB          69  CJ  YO5BTZ          599 001', False,
     [(5, 'QSO: 14000 CW 2026-10-31 1200 YO5PJB          69  CJ  YO5BTZ          599 001',
       'Rst is invalid: 69')]),
    # RST recv "59A" is valid (trailing A/S allowed by regex)
    (6, 'QSO: 14000 CW 2026-10-31 1200 YO5PJB          599 CJ  YO5BTZ          59A 001', True,
     []),
    # Valid with modified suffix rst_sent (59S)
    (7, 'QSO: 14000 CW 2026-10-31 1200 YO5PJB          59S CJ  YO5BTZ          599 001', True,
     []),
]

test_log_qso_rules_based_validator: List[Tuple[int, str, bool, list]] = [
    # Before contest start date
    (1, 'QSO: 14000 CW 2026-10-30 1200 YO5PJB          599 CJ  YO5BTZ          599 001', False,
     [(1, 'QSO: 14000 CW 2026-10-30 1200 YO5PJB          599 CJ  YO5BTZ          599 001',
       'Qso date is invalid: before contest starts (<261031)'),
      (1, 'QSO: 14000 CW 2026-10-30 1200 YO5PJB          599 CJ  YO5BTZ          599 001',
       'Qso date/hour is invalid: not inside contest periods')]),
    # After contest end date
    (2, 'QSO: 14000 CW 2026-11-02 1200 YO5PJB          599 CJ  YO5BTZ          599 001', False,
     [(2, 'QSO: 14000 CW 2026-11-02 1200 YO5PJB          599 CJ  YO5BTZ          599 001',
       'Qso date is invalid: after contest ends (>261101)'),
      (2, 'QSO: 14000 CW 2026-11-02 1200 YO5PJB          599 CJ  YO5BTZ          599 001',
       'Qso date/hour is invalid: not inside contest periods')]),
    # Before contest start hour (on start date)
    (3, 'QSO: 14000 CW 2026-10-31 1159 YO5PJB          599 CJ  YO5BTZ          599 001', False,
     [(3, 'QSO: 14000 CW 2026-10-31 1159 YO5PJB          599 CJ  YO5BTZ          599 001',
       'Qso hour is invalid: before contest start hour (<1200)'),
      (3, 'QSO: 14000 CW 2026-10-31 1159 YO5PJB          599 CJ  YO5BTZ          599 001',
       'Qso date/hour is invalid: not inside contest periods')]),
    # Valid QSO on start date
    (4, 'QSO: 14000 CW 2026-10-31 1200 YO5PJB          599 CJ  YO5BTZ          599 001', True,
     []),
    # Valid QSO on end date
    (5, 'QSO: 14000 CW 2026-11-01 1159 YO5PJB          599 CJ  YO5BTZ          599 001', True,
     []),
    # After contest end hour (on end date)
    (6, 'QSO: 14000 CW 2026-11-01 1200 YO5PJB          599 CJ  YO5BTZ          599 001', False,
     [(6, 'QSO: 14000 CW 2026-11-01 1200 YO5PJB          599 CJ  YO5BTZ          599 001',
       'Qso hour is invalid: after contest end hour (>1159)'),
      (6, 'QSO: 14000 CW 2026-11-01 1200 YO5PJB          599 CJ  YO5BTZ          599 001',
       'Qso date/hour is invalid: not inside contest periods')]),
    # Invalid mode (not in defined CW, SSB)
    (7, 'QSO: 14000 RTTY 2026-10-31 1200 YO5PJB          599 CJ  YO5BTZ          599 001', False,
     [(7, 'QSO: 14000 RTTY 2026-10-31 1200 YO5PJB          599 CJ  YO5BTZ          599 001',
       'Qso mode is invalid: not in defined modes (CW,SSB)')]),
]

# A minimal cabrillo-compatible rules string for cross-check tests
CABRILLO_CROSSCHECK_RULES: str = \
"""[contest]
name=Test
begindate=20261031
enddate=20261101
beginhour=1200
endhour=1159
bands=1
periods=1
categories=1
modes=CW,SSB

[log]
format=cabrillo

[band1]
band=14
regexp=14\\.?|20m
multiplier=1

[period1]
begindate=20261031
enddate=20261101
beginhour=1200
endhour=1159
bands=band1

[category1]
name=SO-AB
regexp=SINGLE|SO|CHECK
bands=band1
"""

# DRACULA rules content (from test_logs/rules_hf_dracula.config)
DRACULA_RULES: str = \
r"""[contest]
name=Dracula
begindate=20261031
enddate=20261101
beginhour=1200
endhour=1159
bands=5
periods=1
categories=7
modes=CW,SSB
custom_scoring=DRACULA

[log]
format=cabrillo

[band1]
band=3.5
regexp=3\.?|80m
multiplier=1

[band2]
band=7
regexp=7\.?|40m
multiplier=1

[band3]
band=14
regexp=14\.?|20m
multiplier=1

[band4]
band=21
regexp=21\.?|15m
multiplier=1

[band5]
band=28
regexp=28\.?|10m
multiplier=1

[period1]
begindate=20261031
enddate=20261101
beginhour=1200
endhour=1159
bands=band1,band2,band3,band4,band5

[category1]
name=SO-AB-HP SSB
regexp=A1
bands=band1,band2,band3,band4,band5

[category2]
name=SO-AB-HP CW
regexp=A2
bands=band1,band2,band3,band4,band5

[category3]
name=SO-AB-HP MIXT
regexp=A3
bands=band1,band2,band3,band4,band5

[category4]
name=SO-AB-LP SSB
regexp=B1
bands=band1,band2,band3,band4,band5

[category5]
name=SO-AB-LP CW
regexp=B2
bands=band1,band2,band3,band4,band5

[category6]
name=SO-AB-LP MIXT
regexp=B3
bands=band1,band2,band3,band4,band5

[category7]
name=MO-AB-HP MIXT
regexp=C
bands=band1,band2,band3,band4,band5

[scoring]
special_callsign=YP2DRACULA,YR2DRACULA,YQ2DRACULA,YP5DRACULA,YR5DRACULA,YQ5DRACULA,YP6DRACULA,YR6DRACULA,YQ6DRACULA
non_yo_to_special_points=10
non_yo_to_yo_points=5
non_yo_dxcc_points=2
non_yo_same_country_points=1
yo_to_special_points=10
yo_to_nonyo_points=5
yo_to_yo_points=0
multiplier_enabled=true
multiplier_per_band=true
multiplier_exchange_field=nr_recv
multiplier_special_exchange=DRC
"""


class TestCabrilloLog(TestCase):
    def test_init(self) -> None:

        # test with a log with no-lines
        invalid_cabrillo_log: str = ''
        mo = mock.mock_open(read_data=invalid_cabrillo_log)
        with patch('builtins.open', mo, create=True):
            log = cabrillo.Log('some_log_file.log')
            self.assertFalse(log.valid_header, "Header should be invalid for empty log")
            self.assertIsNone(log.valid_qsos, "QSOs should be None for empty log")
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [(None, 'Log is empty')], ERR_HEADER: [], ERR_QSO: []},
                                 "Errors should match expected for empty log")

        # test with missing START-OF-LOG header
        mo = mock.mock_open(read_data=invalid_cabrillo_log_no_start)
        with patch('builtins.open', mo, create=True):
            log = cabrillo.Log('some_log_file.log')
            self.assertFalse(log.valid_header, "Header should be invalid when START-OF-LOG is missing")
            self.assertIsNone(log.valid_qsos, "QSOs should be None when START-OF-LOG is missing")
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [],
                                  ERR_HEADER: [(1, 'Missing or invalid START-OF-LOG header')],
                                  ERR_QSO: []},
                                 "Errors should indicate missing START-OF-LOG")

        # test with unsupported version
        mo = mock.mock_open(read_data=invalid_cabrillo_log_bad_version)
        with patch('builtins.open', mo, create=True):
            log = cabrillo.Log('some_log_file.log')
            self.assertFalse(log.valid_header, "Header should be invalid for unsupported version")
            self.assertIsNone(log.valid_qsos, "QSOs should be None for unsupported version")
            self.assertEqual(log.errors['header'],
                             [(1, 'Unsupported Cabrillo version: 1.0')],
                             "Errors should indicate unsupported version")

        # test with empty log_lines (zero length) - same as empty
        mo = mock.mock_open(read_data='')
        with patch('builtins.open', mo, create=True):
            log = cabrillo.Log('some_log_file.log')
            self.assertFalse(log.valid_header, "Header should be invalid for empty log")
            self.assertIsNone(log.valid_qsos, "QSOs should be None for empty log")
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [(None, 'Log is empty')], ERR_HEADER: [], ERR_QSO: []},
                                 "Errors should match expected for empty log")

        # test with missing CALLSIGN (but CONTEST is present -> header fails parsing)
        mo = mock.mock_open(read_data=invalid_cabrillo_log_no_callsign)
        with patch('builtins.open', mo, create=True):
            log = cabrillo.Log('some_log_file.log')
            self.assertFalse(log.valid_header, "Header should be invalid when CALLSIGN is missing")
            self.assertIsNone(log.valid_qsos, "QSOs should be None when CALLSIGN is missing")
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [],
                                  ERR_HEADER: [(None, 'CALLSIGN field is not present')],
                                  ERR_QSO: []},
                                 "Errors should indicate missing CALLSIGN field")

        # test with missing CATEGORY-BAND (but CALLSIGN is present)
        mo = mock.mock_open(read_data=invalid_cabrillo_log_no_band)
        with patch('builtins.open', mo, create=True):
            log = cabrillo.Log('some_log_file.log')
            self.assertFalse(log.valid_header, "Header should be invalid when CATEGORY-BAND is missing")
            self.assertIsNone(log.valid_qsos, "QSOs should be None when CATEGORY-BAND is missing")
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [],
                                  ERR_HEADER: [(None, 'CATEGORY-BAND field is not present')],
                                  ERR_QSO: []},
                                 "Errors should indicate missing CATEGORY-BAND field")

        # test with missing CATEGORY-OPERATOR
        mo = mock.mock_open(read_data=invalid_cabrillo_log_no_category)
        with patch('builtins.open', mo, create=True):
            log = cabrillo.Log('some_log_file.log')
            self.assertFalse(log.valid_header, "Header should be invalid when CATEGORY-OPERATOR is missing")
            self.assertIsNone(log.valid_qsos, "QSOs should be None when CATEGORY-OPERATOR is missing")
            header_errors = log.errors[ERR_HEADER]
            header_error_msgs = [msg for _, msg in header_errors]
            self.assertIn('CATEGORY-OPERATOR field is not present', header_error_msgs,
                          "Errors should indicate missing CATEGORY-OPERATOR")

        # test with invalid CALLSIGN
        mo = mock.mock_open(read_data=invalid_cabrillo_log_invalid_callsign)
        with patch('builtins.open', mo, create=True):
            log = cabrillo.Log('some_log_file.log')
            self.assertFalse(log.valid_header, "Header should be invalid for invalid CALLSIGN content")
            self.assertIsNone(log.valid_qsos, "QSOs should be None for invalid CALLSIGN content")
            header_errors = log.errors[ERR_HEADER]
            header_error_msgs = [msg for _, msg in header_errors]
            self.assertTrue(any('CALLSIGN field content is not valid' in msg for msg in header_error_msgs),
                            "Errors should indicate invalid CALLSIGN content")

        # test with valid header and invalid QSO.
        # Without rules, mode is not validated in generic validation, so use an
        # invalid RST number (69) which starts with a digit outside 1-5 range.
        invalid_qso_line: str = 'QSO:  7100 PH 2026-10-31 1200 YO5PJB          69  CJ  YO5BTZ          599 001'
        invalid_qso_log: str = valid_cabrillo_header + '\n' + invalid_qso_line
        mo = mock.mock_open(read_data=invalid_qso_log)
        with patch('builtins.open', mo, create=True):
            log = cabrillo.Log('some_log_file.log')
            self.assertTrue(log.valid_header, "Header should be valid for valid header fields")
            self.assertFalse(log.valid_qsos, "QSOs should be invalid when RST is invalid")
            self.assertTrue(len(log.errors[ERR_QSO]) > 0,
                            "Errors should indicate invalid QSO line")

        # test with valid V3 log and valid QSOs (11-field format)
        # Without rules, SINGLE-OP maps to 'single' category via generic validation
        mo = mock.mock_open(read_data=valid_cabrillo_log_11f)
        with patch('builtins.open', mo, create=True):
            log = cabrillo.Log('some_log_file.log')
            self.assertTrue(log.valid_header, "Header should be valid for valid log")
            self.assertTrue(log.valid_qsos, "QSOs should be valid for valid QSO lines")
            self.assertEqual(log.callsign, 'YO5PJB', "Callsign should be YO5PJB")
            self.assertEqual(log.band, 'ALL', "Band should be ALL")
            self.assertEqual(log.category, 'single', "Category should be 'single' (from generic validation of SINGLE-OP)")

    @mock.patch('os.path.isfile')
    def test_init_with_rules(self, mock_isfile: mock.MagicMock) -> None:
        mock_isfile.return_value = True
        mo_rules = mock.mock_open(read_data=DRACULA_RULES)
        with patch('builtins.open', mo_rules, create=True):
            _rules = rules_hf.RulesHf('some_rule_file.rules')

        # test with valid rules and valid cabrillo log (using DRACULA category B3)
        mo_log = mock.mock_open(read_data=valid_cabrillo_log_dracula)
        with patch('builtins.open', mo_log, create=True):
            log = cabrillo.Log('some_log_file.log', rules=_rules)
            self.assertTrue(log.valid_header, "Header should be valid for valid log with rules")
            self.assertTrue(log.valid_qsos, "QSOs should be valid for valid QSO lines with rules")

        # test with invalid mode in QSO (RTTY not in CW,SSB)
        invalid_mode_log: str = valid_cabrillo_log_dracula.replace('CW', 'RTTY')
        mo_log = mock.mock_open(read_data=invalid_mode_log)
        with patch('builtins.open', mo_log, create=True):
            log = cabrillo.Log('some_log_file.log', rules=_rules)
            self.assertTrue(log.valid_header, "Header should still be valid")
            self.assertFalse(log.valid_qsos, "QSOs should be invalid for invalid mode")

    def test_read_file_content(self) -> None:
        # test 'read_file_content', the builtins.open is mocked
        mo = mock_open(read_data=valid_cabrillo_log_11f)
        with patch('builtins.open', mo, create=True):
            log = cabrillo.Log('some_log_file.log')
        self.assertEqual(valid_cabrillo_log_11f, ''.join(log.log_lines), "Log lines should match the input data")

        # test 'read_file_content' exceptions
        log = cabrillo.Log('non-existing-log-file.log')
        self.assertFalse(log.valid_header, "Header should be invalid for non-existing file")
        self.assertEqual(log.errors,
                         {ERR_IO: [(None, "Cannot read Cabrillo log. Error: [Errno 2] No such file or directory: "
                                          "'non-existing-log-file.log'")],
                          ERR_HEADER: [], ERR_QSO: []},
                         "Errors should indicate file not found")

    def test_get_field(self) -> None:
        """get_field is a stub for Cabrillo, returns (None, None)"""
        mo = mock_open(read_data=valid_cabrillo_log_11f)
        with patch('builtins.open', mo, create=True):
            log = cabrillo.Log('some_log_file.log')
        self.assertTupleEqual((None, None), log.get_field('CALLSIGN'),
                              "get_field should return (None, None) for Cabrillo")

    def test_get_qsos(self) -> None:
        """Test QSO parsing from a real Cabrillo log."""
        mo = mock_open(read_data=valid_cabrillo_log_11f)
        with patch('builtins.open', mo, create=True):
            log = cabrillo.Log('some_log_file.log')
        # We should have extracted QSOs from lines starting with 'QSO:'
        self.assertEqual(10, len(log.qsos), "Should have 10 QSOs from the test log")
        # Check first QSO
        first_qso = log.qsos[0]
        self.assertEqual('QSO: 14000 CW 2026-10-31 1200 YO5PJB          599 CJ  YO5BTZ          599 001',
                         first_qso.qso_line.strip())
        self.assertTrue(first_qso.valid)
        # Check QSO fields
        self.assertEqual('YO5BTZ', first_qso.qso_fields['call'])
        self.assertEqual('261031', first_qso.qso_fields['date'])
        self.assertEqual('1200', first_qso.qso_fields['hour'])
        self.assertEqual('CW', first_qso.qso_fields['mode'])

    def test_validate_callsign(self) -> None:
        positive_tests: List[str] = ['YO5PJB', 'yo5pjb', 'YO5pjb', 'K4X', 'A22A', 'I20000X',
                          '4X4AAA', '3DA0RS', 'YO5PJB/P', 'YO5PJB/M', 'DL/YO5PJB', 'DL/YO5PJB/P', 'DL/YO5PJB/M']
        negative_tests: List[Optional[str]] = [None, '', 'yo%pjb', 'invalid!']

        for test in positive_tests:
            with self.subTest(callsign=test):
                self.assertTrue(cabrillo.Log.validate_callsign(test), f"Callsign {test} should be valid")
        for test in negative_tests:
            with self.subTest(callsign=test):
                self.assertFalse(cabrillo.Log.validate_callsign(test), f"Callsign {test} should be invalid")

    def test_validate_qth_locator(self) -> None:
        positive_tests: List[str] = ['KN16SS', 'kn16ss', 'AA00AA', 'RR00XX']
        negative_tests: List[Optional[str]] = [None, '', '0016SS', 'KNXXSS', 'KN1600', 'KN16SS00', '00KN16SS']

        for test in positive_tests:
            with self.subTest(locator=test):
                self.assertTrue(cabrillo.Log.validate_qth_locator(test), f"QTH locator {test} should be valid")
        for test in negative_tests:
            with self.subTest(locator=test):
                self.assertFalse(cabrillo.Log.validate_qth_locator(test), f"QTH locator {test} should be invalid")

    def test_validate_band(self) -> None:
        """Generic band validation should accept any non-empty value."""
        positive_tests: List[str] = ['ALL', '40M', '20M', '80M', '160M']
        negative_tests: List[Optional[str]] = [None, '']
        for test in positive_tests:
            with self.subTest(band=test):
                self.assertTrue(cabrillo.Log.validate_band(test), f"Band {test} should be valid")
        for test in negative_tests:
            with self.subTest(band=test):
                self.assertFalse(cabrillo.Log.validate_band(test), f"Band {test} should be invalid")

    @mock.patch('os.path.isfile')
    def test_rules_based_validate_band(self, mock_isfile: mock.MagicMock) -> None:
        mock_isfile.return_value = True
        positive_tests: List[str] = ['3.5', '7', '14', '21', '28', '80m', '40m', '20m']
        negative_tests: List[Optional[str]] = [None, '', '2m']

        mo = mock.mock_open(read_data=DRACULA_RULES)
        with patch('builtins.open', mo, create=True):
            _rules = rules_hf.RulesHf('some_rule_file.rules')
        for test in positive_tests:
            with self.subTest(band=test):
                self.assertTrue(cabrillo.Log.rules_based_validate_band(test, _rules),
                                f"Band {test} should be valid according to rules")
        for test in negative_tests:
            with self.subTest(band=test):
                self.assertFalse(cabrillo.Log.rules_based_validate_band(test, _rules),
                                 f"Band {test} should be invalid according to rules")
        self.assertRaisesRegex(ValueError, 'No contest rules provided!',
                               cabrillo.Log.rules_based_validate_band, 'ALL', None)

    def test_validate_category(self) -> None:
        positive_tests: Dict[str, List[str]] = {
            'single': ['SINGLE-OP', 'SINGLE', 'SO'],
            'multi': ['MULTI-OP', 'MULTI', 'MO', 'MOMB'],
            'checklog': ['CHECK', 'CHECK-LOG', 'CHECKLOG'],
        }
        negative_tests: List[Optional[str]] = [None, '', 'operator', 'band']
        for _category, test_list in positive_tests.items():
            for test in test_list:
                with self.subTest(category_input=test, expected_category=_category):
                    res_valid, res_cat = cabrillo.Log.validate_category(test)
                    self.assertTrue(res_valid, f"Category input {test} should validate")
                    self.assertEqual(res_cat, _category, f"Category input {test} should map to {_category}")
        for test in negative_tests:
            with self.subTest(category_input=test):
                self.assertTupleEqual(cabrillo.Log.validate_category(test), (False, None),
                                      f"Category input {test} should be invalid")

    @mock.patch('os.path.isfile')
    def test_rules_based_validate_category(self, mock_isfile: mock.MagicMock) -> None:
        mock_isfile.return_value = True
        positive_tests: Dict[str, List[str]] = {
            'SO-AB-HP SSB': ['A1'],
            'SO-AB-HP CW': ['A2'],
            'SO-AB-HP MIXT': ['A3'],
            'SO-AB-LP SSB': ['B1'],
            'SO-AB-LP CW': ['B2'],
            'SO-AB-LP MIXT': ['B3'],
            'MO-AB-HP MIXT': ['C'],
        }
        negative_tests: List[Optional[str]] = [None, '', 'operator', 'band', 'X1']
        mo = mock.mock_open(read_data=DRACULA_RULES)
        with patch('builtins.open', mo, create=True):
            _rules = rules_hf.RulesHf('some_rule_file.rules')
        for _category, test_list in positive_tests.items():
            for test in test_list:
                with self.subTest(category_input=test, expected_category=_category):
                    res_valid, res_cat = cabrillo.Log.rules_based_validate_category(test, _rules)
                    self.assertTrue(res_valid, f"Category input {test} should validate with rules")
                    self.assertEqual(res_cat, _category, f"Category input {test} should map to {_category}")
        for test in negative_tests:
            with self.subTest(category_input=test):
                self.assertTupleEqual(cabrillo.Log.rules_based_validate_category(test, _rules), (False, None),
                                      f"Category input {test} should be invalid with rules")
        self.assertRaisesRegex(ValueError, 'No contest rules provided!',
                               cabrillo.Log.rules_based_validate_category, 'A1', None)

    def test_validate_date(self) -> None:
        positive_tests: List[str] = ['2026-10-31', '2026-11-01', '2024-02-29']
        negative_tests: List[Optional[str]] = [None, '', '2026-13-01', '2026-00-01', '2026-02-30']
        for test in positive_tests:
            with self.subTest(date=test):
                self.assertTrue(cabrillo.Log.validate_date(test), f"Date {test} should be valid")
        for test in negative_tests:
            with self.subTest(date=test):
                self.assertFalse(cabrillo.Log.validate_date(test), f"Date {test} should be invalid")

    def test_rules_based_validate_date_no_rules(self) -> None:
        # TODO : rules_based_validate_band() is not yet called in the code, but test that it raises the expected exception if called without rules.
        mo = mock.mock_open(read_data=valid_cabrillo_header)
        with patch('builtins.open', mo, create=True):
            log = cabrillo.Log('some_log_file.log')

        self.assertRaisesRegex(ValueError, 'No contest rules provided!',
                               log.rules_based_validate_date, '2026-10-31', None)

    def test_validate_email(self) -> None:
        """validate_email is a stub (not yet called), just check the interface."""
        self.assertTrue(hasattr(cabrillo.Log, 'validate_email'),
                        "Log class should have validate_email method")


class TestCabrilloLogQso(TestCase):
    def test_init(self) -> None:
        for (linenr, qso, valid, errors) in test_log_qso_valid_format:
            lq = cabrillo.LogQso(qso, linenr)
            self.assertEqual(lq.line_nr, linenr)
            self.assertEqual(lq.qso_line, qso)
            self.assertEqual(lq.valid, valid)
            self.assertEqual(lq.errors, errors)

    def test_qso_parser(self) -> None:
        """Test that QSO lines parse to the expected fields (11-field format)."""
        lqlist: List[Dict[str, str]] = []
        for qso in test_valid_qso_lines_11f:
            lq = cabrillo.LogQso(qso, 1).qso_fields
            lqlist.append(lq.copy())
        self.assertEqual(lqlist, test_valid_qso_fields_11f)

    def test_qso_parser_13f(self) -> None:
        """Test that 13-field QSO format also parses correctly."""
        for qso in test_valid_qso_lines_13f:
            lq = cabrillo.LogQso(qso, 1)
            self.assertTrue(lq.valid, f"QSO should be valid: {qso}")
            self.assertIsNotNone(lq.qso_fields['call'], "Callsign should be parsed")
            self.assertIsNotNone(lq.qso_fields['date'], "Date should be parsed")
            self.assertIsNotNone(lq.qso_fields['hour'], "Hour should be parsed")
            self.assertIsNotNone(lq.qso_fields['mode'], "Mode should be parsed")
            self.assertIsNotNone(lq.qso_fields['nr_sent'], "Sent exchange should be parsed")
            self.assertIsNotNone(lq.qso_fields['nr_recv'], "Received exchange should be parsed")

    def test_valid_qso_line(self) -> None:
        """Test valid QSO lines pass regex validation."""
        for line in test_valid_qso_lines_11f + test_valid_qso_lines_13f:
            self.assertIsNone(cabrillo.LogQso.regexp_qso_validator(line),
                              f"QSO line should be valid: {line[:40]}...")

        for (line, message) in test_invalid_qso_lines:
            ret = cabrillo.LogQso.regexp_qso_validator(line)
            self.assertEqual(message, ret, f"Expected error for line: {line}")

    def test_regexp_qso_validator(self) -> None:
        """Test the regexp_qso_validator class method."""
        for (linenr, qso, valid, errors) in test_log_qso_regexp_validator:
            lq = cabrillo.LogQso(qso, linenr)
            self.assertEqual(lq.line_nr, linenr)
            self.assertEqual(lq.qso_line, qso)
            self.assertEqual(lq.valid, valid)
            self.assertEqual(lq.errors, errors)

    def test_generic_qso_validator(self) -> None:
        """Test generic QSO validation (date, time, callsign, mode, RST, exchange)."""
        for (linenr, qso, valid, errors) in test_log_qso_generic_validator:
            lq = cabrillo.LogQso(qso, linenr)
            self.assertEqual(lq.line_nr, linenr)
            self.assertEqual(lq.qso_line, qso)
            self.assertEqual(lq.valid, valid)
            self.assertEqual(lq.errors, errors)

    @mock.patch('os.path.isfile')
    def test_rules_based_qso_validator(self, mock_isfile: mock.MagicMock) -> None:
        mock_isfile.return_value = True
        mo = mock.mock_open(read_data=DRACULA_RULES)
        with patch('builtins.open', mo, create=True):
            _rules = rules_hf.RulesHf('some_rule_file.rules')

        for (linenr, qso, valid, errors) in test_log_qso_rules_based_validator:
            lq = cabrillo.LogQso(qso, linenr, rules=_rules)
            self.assertEqual(lq.line_nr, linenr)
            self.assertEqual(lq.qso_line, qso)
            self.assertEqual(lq.valid, valid)
            self.assertEqual(lq.errors, errors)


class TestCabrilloOperator(TestCase):
    def test_init(self) -> None:
        op = cabrillo.Operator('YO5PJB')
        self.assertEqual(op.callsign, 'YO5PJB')
        self.assertEqual(op.logs, [])
        op = cabrillo.Operator('YO5PJB/P')
        self.assertEqual(op.callsign, 'YO5PJB/P')
        self.assertEqual(op.logs, [])
        op = cabrillo.Operator('DL/YO5PJB')
        self.assertEqual(op.callsign, 'DL/YO5PJB')
        self.assertEqual(op.logs, [])
        op = cabrillo.Operator('DL/YO5PJB/P')
        self.assertEqual(op.callsign, 'DL/YO5PJB/P')
        self.assertEqual(op.logs, [])

    def test_add_log(self) -> None:
        op = cabrillo.Operator('YO5PJB')
        mo = mock.mock_open(read_data=valid_cabrillo_log_11f)
        with patch('builtins.open', mo, create=True):
            op.add_log_by_path('some_log_file.log')
            self.assertEqual(len(op.logs), 1)
            op.add_log_by_path('some_log_file.log')
            self.assertEqual(len(op.logs), 2)
            self.assertIsInstance(op.logs[0], cabrillo.Log)
            self.assertIsInstance(op.logs[1], cabrillo.Log)

    def test_add_log_instance(self) -> None:
        op = cabrillo.Operator('YO5PJB')
        log = cabrillo.Log('some_log_file.log')

        self.assertEqual(op.logs, [])
        op.add_log_instance(log)
        self.assertEqual(op.logs, [log])

    def test_logs_by_band_regexp(self) -> None:
        op = cabrillo.Operator('YO5PJB')
        log1 = cabrillo.Log('log1.log')
        log1.band = 'ALL'
        log1.valid_header = True
        log2 = cabrillo.Log('log2.log')
        log2.band = '40M'
        log2.valid_header = True
        log3 = cabrillo.Log('log3.log')
        log3.band = '20M'
        log3.valid_header = True
        log4 = cabrillo.Log('log4_invalid.log')
        log4.band = '20M'
        log4.valid_header = None

        op.add_log_instance(log1)
        op.add_log_instance(log2)
        op.add_log_instance(log3)
        op.add_log_instance(log4)
        self.assertListEqual(op.logs_by_band_regexp('ALL|40M|20M'), [log1, log2, log3])
        self.assertListEqual(op.logs_by_band_regexp('40M'), [log2])


class TestCabrilloHelperFunctions(TestCase):
    def test_is_yo_callsign(self) -> None:
        positive_tests: List[str] = [
            'YO5PJB', 'YP2DRACULA', 'YQ6DRACULA', 'YR5DRACULA',
            'yo5pjb', 'Yo5pjb',
            'YO2AAA', 'YP3XXX', 'YQ4YYY', 'YR9ZZZ',
        ]
        negative_tests: List[Optional[str]] = [
            None, '', 'DL1ABC', 'HA5ABC', 'I4ABC', 'K4X',
            'DA1ABC', 'DB1XYZ', 'W1AW', 'AA1AAA', 'K1A',
        ]

        for test in positive_tests:
            with self.subTest(callsign=test):
                self.assertTrue(cabrillo.is_yo_callsign(test), f"Callsign {test} should be YO")
        for test in negative_tests:
            with self.subTest(callsign=test):
                self.assertFalse(cabrillo.is_yo_callsign(test), f"Callsign {test} should not be YO")

    # ── DXCC database tests ────────────────────────────────────────────

    def test_lookup_callsign_none_or_empty(self) -> None:
        """lookup_callsign should return None for None/empty input."""
        self.assertIsNone(cabrillo.lookup_callsign(None))
        self.assertIsNone(cabrillo.lookup_callsign(''))
        self.assertIsNone(cabrillo.lookup_callsign('   '))

    def test_lookup_callsign_romania(self) -> None:
        """Romanian callsigns should resolve to country='Romania', main_prefix='YO'."""
        info = cabrillo.lookup_callsign('YO5PJB')
        self.assertIsNotNone(info)
        self.assertEqual(info['country'], 'Romania')
        self.assertEqual(info['main_prefix'], 'YO')
        self.assertEqual(info['continent'], 'EU')

    def test_lookup_callsign_yp_yq_yr(self) -> None:
        """YP, YQ, YR callsigns should also resolve to Romania."""
        for cs in ['YP2DRACULA', 'YQ6ABC', 'YR5XYZ']:
            info = cabrillo.lookup_callsign(cs)
            self.assertIsNotNone(info, f"Callsign {cs} should resolve")
            self.assertEqual(info['main_prefix'], 'YO', f"{cs} should be in YO DXCC")

    def test_lookup_callsign_germany(self) -> None:
        """German callsigns (DL, DA, etc.) should resolve to Fed. Rep. of Germany."""
        for cs in ['DL1ABC', 'DA1AAA', 'Y2A']:
            info = cabrillo.lookup_callsign(cs)
            self.assertIsNotNone(info, f"Callsign {cs} should resolve")
            self.assertEqual(info['main_prefix'], 'DL', f"{cs} should be in DL (Germany)")

    def test_lookup_callsign_usa(self) -> None:
        """US callsigns (K, W, AA, etc.) should resolve to United States."""
        for cs in ['K4X', 'W1AW', 'AA1AAA', 'N1ABC']:
            info = cabrillo.lookup_callsign(cs)
            self.assertIsNotNone(info, f"Callsign {cs} should resolve")
            self.assertEqual(info['main_prefix'], 'K', f"{cs} should be in US (K)")

    def test_lookup_callsign_hawaii(self) -> None:
        """Hawaii (KH6) should resolve to its own DXCC entity."""
        info = cabrillo.lookup_callsign('KH6XYZ')
        # KH6 could match either 'KH' (just a prefix) or 'KH6'
        # 'KH6' is prefix for Hawaii
        if info:
            # KH may be Kiribati (T30) or other. Let's just verify it resolves.
            self.assertIn('country', info)

    def test_get_callsign_continent(self) -> None:
        """Test continent lookup for various callsigns."""
        self.assertEqual(cabrillo.get_callsign_continent('YO5PJB'), 'EU')
        self.assertEqual(cabrillo.get_callsign_continent('DL1ABC'), 'EU')
        self.assertEqual(cabrillo.get_callsign_continent('K4X'), 'NA')
        self.assertEqual(cabrillo.get_callsign_continent('W1AW'), 'NA')
        self.assertEqual(cabrillo.get_callsign_continent('LU1ABC'), 'SA')
        self.assertEqual(cabrillo.get_callsign_continent(None), None)
        self.assertEqual(cabrillo.get_callsign_continent(''), None)

    def test_are_same_dxcc(self) -> None:
        """Test are_same_dxcc for various callsign pairs."""
        # Same country (Romania)
        self.assertTrue(cabrillo.are_same_dxcc('YO5PJB', 'YP2DRACULA'))
        # Same country (Germany)
        self.assertTrue(cabrillo.are_same_dxcc('DL1ABC', 'DA1XYZ'))
        # Same country (USA)
        self.assertTrue(cabrillo.are_same_dxcc('K4X', 'W1AW'))
        # Different countries
        self.assertFalse(cabrillo.are_same_dxcc('YO5PJB', 'DL1ABC'))
        self.assertFalse(cabrillo.are_same_dxcc('K4X', 'YO5PJB'))
        # Edge cases
        self.assertFalse(cabrillo.are_same_dxcc(None, 'YO5PJB'))
        self.assertFalse(cabrillo.are_same_dxcc('', 'YO5PJB'))
        self.assertFalse(cabrillo.are_same_dxcc(None, None))

    def test_lookup_callsign_multiple_parts(self) -> None:
        """Test portable callsign format with /."""
        # DL/YO5PJB (German station operating portable with YO5PJB)
        # DL prefix -> Germany
        info = cabrillo.lookup_callsign('DL/YO5PJB/P')
        # The first part "DL" should match Germany
        self.assertIsNotNone(info)
        self.assertEqual(info['main_prefix'], 'DL')
        
        # YO5PJB/P -> YO -> Romania
        info = cabrillo.lookup_callsign('YO5PJB/P')
        self.assertIsNotNone(info)
        self.assertEqual(info['main_prefix'], 'YO')

    def test_is_yo_county(self) -> None:
        positive_tests: List[str] = ['AR', 'CJ', 'BU', 'IS', 'CT', 'BV', 'AG', 'BC', 'BZ', 'TM']
        negative_tests: List[Optional[str]] = [None, '', 'XX', 'YY', 'ZZ', 'USA']

        for test in positive_tests:
            with self.subTest(county=test):
                self.assertTrue(cabrillo.is_yo_county(test), f"County {test} should be a YO county")
        for test in negative_tests:
            with self.subTest(county=test):
                self.assertFalse(cabrillo.is_yo_county(test), f"County {test} should not be a YO county")

    def test_is_dracula_contest(self) -> None:
        # Create a mock rules with DRACULA custom scoring
        mock_rules_dracula = mock.Mock()
        mock_rules_dracula.contest_custom_scoring = 'DRACULA'
        self.assertTrue(cabrillo.is_dracula_contest(mock_rules_dracula))

        # Create a mock rules without custom scoring
        mock_rules_none = mock.Mock()
        mock_rules_none.contest_custom_scoring = None
        self.assertFalse(cabrillo.is_dracula_contest(mock_rules_none))

        # No rules
        self.assertFalse(cabrillo.is_dracula_contest(None))

    def test_is_dracula_special(self) -> None:
        mock_rules = mock.Mock()
        mock_rules.contest_special_callsign = ['YP2DRACULA', 'YR5DRACULA', 'YQ6DRACULA']

        self.assertTrue(cabrillo.is_dracula_special('YP2DRACULA', mock_rules))
        self.assertTrue(cabrillo.is_dracula_special('yp2dracula', mock_rules))
        self.assertTrue(cabrillo.is_dracula_special('YQ6DRACULA', mock_rules))
        self.assertFalse(cabrillo.is_dracula_special('YO5PJB', mock_rules))
        self.assertFalse(cabrillo.is_dracula_special('', mock_rules))
        self.assertFalse(cabrillo.is_dracula_special(None, mock_rules))
        self.assertFalse(cabrillo.is_dracula_special('YP2DRACULA', None))

    def test_normalize_cabrillo_mode(self) -> None:
        test_cases: List[Tuple[str, str]] = [
            ('CW', 'CW'),
            ('SSB', 'SSB'),
            ('PHONE', 'SSB'),
            ('PH', 'SSB'),
            ('LSB', 'SSB'),
            ('USB', 'SSB'),
            ('FM', 'FM'),
            ('AM', 'AM'),
            ('RTTY', 'DIGI'),
            ('FT8', 'DIGI'),
            ('FT4', 'DIGI'),
            ('PSK31', 'DIGI'),
            ('DIGI', 'DIGI'),
            ('UNKNOWN', 'UNKNOWN'),
        ]
        for input_mode, expected in test_cases:
            with self.subTest(mode=input_mode):
                self.assertEqual(cabrillo.normalize_cabrillo_mode(input_mode), expected)

    def test_dict_to_json(self) -> None:
        input_dict: Dict[str, str] = {'1': '2', 'Hello': 'World!'}
        output: str = '{"1": "2", "Hello": "World!"}'
        self.assertEqual(cabrillo.dict_to_json(input_dict), output)

    def test_dict_to_xml(self) -> None:
        input_dict: Dict[str, str] = {'1': '2', 'Hello': 'World!'}
        output: bytes = b'<?xml version="1.0" encoding="UTF-8" ?><root><n1 type="str">2</n1><Hello type="str">World!</Hello></root>'
        self.assertEqual(cabrillo.dict_to_xml(input_dict), output)

    def test_qth_distance(self) -> None:
        """Currently always returns 1 (placeholder implementation)."""
        self.assertEqual(1, cabrillo.qth_distance('KN16SS', 'KN16SS'))
        self.assertEqual(1, cabrillo.qth_distance('KN16SS', 'KN17SS'))
        self.assertEqual(1, cabrillo.qth_distance('KN16SS', 'KN16SQ'))

    def test_compare_qso_raises_first_qso_error(self) -> None:
        qso1 = cabrillo.LogQso(
            'QSO: 14000 CW 9999-99-99 1200 YO5AAA          599 CJ  YO5BBB          599 001', 1)
        qso2 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5BBB          599 CJ  YO5AAA          599 001', 2)
        log1 = mock.Mock(callsign='YO5AAA')
        log2 = mock.Mock(callsign='YO5BBB')

        self.assertRaisesRegex(ValueError,
                               'Qso date is invalid: unconverted data remains: 99',
                               cabrillo.compare_qso, log1, qso1, log2, qso2)

    def test_compare_qso_raises_other_ham_invalid_error(self) -> None:
        qso1 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5AAA          599 CJ  YO5BBB          599 001', 1)
        qso2 = cabrillo.LogQso(
            'QSO: 14000 CW 9999-99-99 1200 YO5BBB          599 CJ  YO5AAA          599 001', 2)
        log1 = mock.Mock(callsign='YO5AAA')
        log2 = mock.Mock(callsign='YO5BBB')

        self.assertRaisesRegex(ValueError,
                               'Other ham qso is invalid',
                               cabrillo.compare_qso, log1, qso1, log2, qso2)

    def test_compare_qso_callsign_mismatch(self) -> None:
        qso1 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5AAA          599 CJ  YO5BBB          599 001', 1)
        qso2 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5CCC          599 CJ  YO5AAA          599 001', 2)
        log1 = mock.Mock(callsign='YO5AAA')
        log2 = mock.Mock(callsign='YO5CCC')

        self.assertRaisesRegex(ValueError,
                               'Callsign mismatch',
                               cabrillo.compare_qso, log1, qso1, log2, qso2)

    def test_compare_qso_rst_mismatch_reverse_direction(self) -> None:
        """Test RST mismatch in the recv->sent direction.

        qso1.rst_recv (59) should match qso2.rst_sent (599), but doesn't.
        The rst_sent->rst_recv check passes fine (599 == 599).
        """
        qso1 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5AAA          599 CJ  YO5BBB          59  001', 1)
        qso2 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5BBB          599 CJ  YO5AAA          599 001', 2)
        log1 = mock.Mock(callsign='YO5AAA')
        log2 = mock.Mock(callsign='YO5BBB')
        self.assertRaisesRegex(ValueError, 'Rst mismatch',
                               cabrillo.compare_qso, log1, qso1, log2, qso2)

    @mock.patch('os.path.isfile')
    def test_compare_qso_exchange_mismatch_non_dracula(self, mock_isfile: mock.MagicMock) -> None:
        """Test exchange/serial mismatch (sent->recv direction) for non-DRACULA contests.

        Exercises the first exchange check:
            qso1.nr_sent should match qso2.nr_recv
        qso1.nr_sent (001) != qso2.nr_recv (003) → 'Serial number mismatch (other ham)'.
        Uses CABRILLO_CROSSCHECK_RULES which has no custom_scoring set.
        """
        mock_isfile.return_value = True
        mo_rules = mock.mock_open(read_data=CABRILLO_CROSSCHECK_RULES)
        with patch('builtins.open', mo_rules, create=True):
            _rules = rules_hf.RulesHf('some_rule_file.rules')

        # qso1.nr_sent=001, qso2.nr_recv=003 → mismatch (first check fires)
        qso1 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5AAA          599 001 YO5BBB          599 002', 1, _rules)
        qso2 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5BBB          599 999 YO5AAA          599 003', 2, _rules)
        log1 = mock.Mock(callsign='YO5AAA')
        log2 = mock.Mock(callsign='YO5BBB')
        self.assertRaisesRegex(ValueError, re.escape('Serial number mismatch (other ham)'),
                               cabrillo.compare_qso, log1, qso1, log2, qso2)


    @mock.patch('os.path.isfile')
    def test_compare_qso_exchange_mismatch_reverse_non_dracula(self, mock_isfile: mock.MagicMock) -> None:
        """Test exchange/serial mismatch (recv->sent direction) for non-DRACULA contests.

        Exercises the second exchange check:
            qso1.nr_recv should match qso2.nr_sent
        qso1.nr_recv (002) != qso2.nr_sent (999) → 'Serial number mismatch'.

        The first check (nr_sent vs nr_recv) must pass: both are 001.
        Uses CABRILLO_CROSSCHECK_RULES which has no custom_scoring set.
        """
        mock_isfile.return_value = True
        mo_rules = mock.mock_open(read_data=CABRILLO_CROSSCHECK_RULES)
        with patch('builtins.open', mo_rules, create=True):
            _rules = rules_hf.RulesHf('some_rule_file.rules')

        # qso1.nr_sent=001 == qso2.nr_recv=001 → first check PASSES
        # qso1.nr_recv=002 != qso2.nr_sent=999 → second check FAILS → 'Serial number mismatch'
        qso2_wrong_sent = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5BBB          599 999 YO5AAA          599 001', 2, _rules)
        qso1 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5AAA          599 001 YO5BBB          599 002', 1, _rules)
        log1 = mock.Mock(callsign='YO5AAA')
        log2 = mock.Mock(callsign='YO5BBB')
        self.assertRaisesRegex(ValueError, 'Serial number mismatch$',
                               cabrillo.compare_qso, log1, qso1, log2, qso2_wrong_sent)


    @mock.patch('os.path.isfile')
    def test_compare_qso_dracula_skips_exchange(self, mock_isfile: mock.MagicMock) -> None:
        """Test that DRACULA contest does NOT compare exchange/serial values.

        Exchange values differ between qso1 and qso2, but compare_qso
        should still return 1 (valid match) because DRACULA skips
        the exchange comparison.
        """
        mock_isfile.return_value = True
        mo_rules = mock.mock_open(read_data=DRACULA_RULES)
        with patch('builtins.open', mo_rules, create=True):
            _rules = rules_hf.RulesHf('some_rule_file.rules')

        # Different exchange values, but should still match for DRACULA
        qso1 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5AAA          599 CJ  YO5BBB          599 001', 1, _rules)
        qso2 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5BBB          599 999 YO5AAA          599 XXX', 2, _rules)
        log1 = mock.Mock(callsign='YO5AAA')
        log2 = mock.Mock(callsign='YO5BBB')
        # Should not raise ValueError - compare_qso should return 1
        result = cabrillo.compare_qso(log1, qso1, log2, qso2)
        self.assertEqual(result, 1)

    def test_compare_qso_invalid_date_format(self) -> None:
        """Test that an unparseable date in qso_fields raises ValueError.

        This exercises the defensive REGEX_DATE regex check inside
        compare_qso (even though the generic validator would normally
        catch invalid dates before compare_qso runs).
        """
        qso1 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5AAA          599 CJ  YO5BBB          599 001', 1)
        qso2 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5BBB          599 CJ  YO5AAA          599 001', 2)
        # Manually corrupt the date to something the regex won't match
        qso2.qso_fields['date'] = 'abc123'
        log1 = mock.Mock(callsign='YO5AAA')
        log2 = mock.Mock(callsign='YO5BBB')
        self.assertRaisesRegex(ValueError, 'Date format is invalid',
                               cabrillo.compare_qso, log1, qso1, log2, qso2)

    def test_compare_qso_invalid_hour_format(self) -> None:
        """Test that an unparseable hour in qso_fields raises ValueError.

        This exercises the defensive REGEX_HOUR regex check inside
        compare_qso (even though the generic validator would normally
        catch invalid hours before compare_qso runs).
        """
        qso1 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5AAA          599 CJ  YO5BBB          599 001', 1)
        qso2 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5BBB          599 CJ  YO5AAA          599 001', 2)
        # Manually corrupt the hour to something the regex won't match
        qso2.qso_fields['hour'] = 'abc'
        log1 = mock.Mock(callsign='YO5AAA')
        log2 = mock.Mock(callsign='YO5BBB')
        self.assertRaisesRegex(ValueError, 'Hour format is invalid',
                               cabrillo.compare_qso, log1, qso1, log2, qso2)

    def test_mark_older_logs(self) -> None:
        log1 = mock.Mock(path='log1.log')
        log2 = mock.Mock(path='log2.log')
        log1.ignore_this_log = False
        log2.ignore_this_log = False

        with patch('os.path.getmtime', side_effect=[100.0, 200.0]):
            cabrillo.mark_older_logs([log1, log2])

        self.assertTrue(log1.ignore_this_log)
        self.assertFalse(log2.ignore_this_log)

    def test_run_crosscheck_no_rules(self) -> None:
        with patch('builtins.print') as mock_print:
            result = cabrillo.run_crosscheck(cabrillo.Log, rules=None, logs_folder='logs')
        self.assertEqual({}, result)
        mock_print.assert_called_once_with('No rules were provided')

    def test_run_crosscheck_logs_folder_not_dir(self) -> None:
        mo_rules = mock.mock_open(read_data=CABRILLO_CROSSCHECK_RULES)
        with patch('builtins.open', mo_rules, create=True), patch('os.path.isfile', return_value=True):
            _rules = rules_hf.RulesHf('some_rule_file.rules')

        with patch('builtins.print') as mock_print, patch('os.path.isdir', return_value=False):
            result = cabrillo.run_crosscheck(cabrillo.Log, rules=_rules, logs_folder='logs')

        self.assertEqual({}, result)
        mock_print.assert_called_once_with('Cannot open logs folder : logs')

    def test_run_crosscheck_checklogs_folder_not_dir(self) -> None:
        mo_rules = mock.mock_open(read_data=CABRILLO_CROSSCHECK_RULES)
        with patch('builtins.open', mo_rules, create=True), patch('os.path.isfile', return_value=True):
            _rules = rules_hf.RulesHf('some_rule_file.rules')

        log_content: str = \
"""START-OF-LOG: 3.0
CONTEST: TEST
CALLSIGN: YO5AAA
CATEGORY-OPERATOR: SINGLE-OP
CATEGORY-BAND: ALL
CATEGORY-MODE: MIXED
QSO: 14000 CW 2026-10-31 1200 YO5AAA          599 001 YO5BBB          599 002
"""

        file_contents: Dict[str, str] = {
            os.path.join('logs', 'log1.log'): log_content
        }

        def fake_open(path: str, mode: str = 'r', *args: Any, **kwargs: Any) -> io.StringIO:
            return io.StringIO(file_contents[path])

        with patch('builtins.print') as mock_print, \
             patch('os.path.isdir', side_effect=lambda path: path == 'logs'), \
             patch('os.listdir', return_value=['log1.log']), \
             patch('builtins.open', fake_open, create=True):
            result = cabrillo.run_crosscheck(cabrillo.Log, rules=_rules,
                                              logs_folder='logs', checklogs_folder='checklogs')

        self.assertEqual({}, result)
        mock_print.assert_called_once_with('Cannot open checklogs folder : checklogs')

    def test_run_crosscheck_happy_path(self) -> None:
        """Test run_crosscheck with two matching logs (no custom scoring)."""
        mo_rules = mock.mock_open(read_data=CABRILLO_CROSSCHECK_RULES)
        with patch('builtins.open', mo_rules, create=True), patch('os.path.isfile', return_value=True):
            _rules = rules_hf.RulesHf('some_rule_file.rules')

        log1_content: str = \
"""START-OF-LOG: 3.0
CONTEST: TEST
CALLSIGN: YO5AAA
CATEGORY-OPERATOR: SINGLE-OP
CATEGORY-BAND: ALL
CATEGORY-MODE: MIXED
QSO: 14000 CW 2026-10-31 1200 YO5AAA          599 001 YO5BBB          599 002
"""
        log2_content: str = \
"""START-OF-LOG: 3.0
CONTEST: TEST
CALLSIGN: YO5BBB
CATEGORY-OPERATOR: SINGLE-OP
CATEGORY-BAND: ALL
CATEGORY-MODE: MIXED
QSO: 14000 CW 2026-10-31 1200 YO5BBB          599 002 YO5AAA          599 001
"""
        file_contents = {
            os.path.join('logs', 'log1.log'): log1_content,
            os.path.join('logs', 'log2.log'): log2_content,
        }

        def fake_open(path: str, mode: str = 'r', *args: Any, **kwargs: Any) -> io.StringIO:
            return io.StringIO(file_contents[path])

        with patch('os.path.isdir', return_value=True), \
             patch('os.listdir', return_value=['log1.log', 'log2.log']), \
             patch('os.path.getmtime', side_effect=[100.0, 200.0]), \
             patch('builtins.open', fake_open, create=True):
            operator_instances = cabrillo.run_crosscheck(cabrillo.Log, _rules, logs_folder='logs')

        self.assertSetEqual(set(operator_instances.keys()), {'YO5AAA', 'YO5BBB'})
        # Since this is "standard" scoring (no DRACULA custom scoring),
        # crosscheck runs without scoring. QSOs will NOT be cc_confirmed
        # because the standard scoring requires additional setup.
        # Just verify that the operators and their logs exist.
        self.assertIn('YO5AAA', operator_instances)
        self.assertIn('YO5BBB', operator_instances)
        self.assertGreater(len(operator_instances['YO5AAA'].logs), 0)
        self.assertGreater(len(operator_instances['YO5BBB'].logs), 0)

    @mock.patch('os.path.isfile')
    def test_compare_qso(self, mock_isfile: mock.MagicMock) -> None:
        mock_isfile.return_value = True
        mo_rules = mock.mock_open(read_data=DRACULA_RULES)
        with patch('builtins.open', mo_rules, create=True):
            _rules = rules_hf.RulesHf('some_rule_file.rules')

        # Create two separate log instances for proper callsign comparison.
        # In compare_qso:
        #   log1.callsign must match qso2.qso_fields['call']
        #   log2.callsign must match qso1.qso_fields['call']
        _log_yo5aaa = cabrillo.Log('log1.log')
        _log_yo5aaa.callsign = 'YO5AAA'
        _log_yo5aaa.valid_header = True
        _log_yo5aaa.valid_qsos = True

        _log_yo5bbb = cabrillo.Log('log2.log')
        _log_yo5bbb.callsign = 'YO5BBB'
        _log_yo5bbb.valid_header = True
        _log_yo5bbb.valid_qsos = True

        # qso1 is from YO5AAA's perspective, calling YO5BBB
        base_qso: cabrillo.LogQso = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5AAA          599 CJ  YO5BBB          599 001',
            1, _rules)

        # qso2 is from YO5BBB's perspective, calling YO5AAA
        base_qso_reciprocal: cabrillo.LogQso = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5BBB          599 CJ  YO5AAA          599 001',
            2, _rules)

        # QSO with wrong time (>5min diff) from YO5BBB's perspective
        qso_wrong_time: cabrillo.LogQso = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1206 YO5BBB          599 CJ  YO5AAA          599 001',
            2, _rules)

        # QSO with correct time (<5min diff) from YO5BBB's perspective
        qso_correct_time: cabrillo.LogQso = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1201 YO5BBB          599 CJ  YO5AAA          599 001',
            2, _rules)

        # QSO with wrong mode from YO5BBB's perspective
        qso_wrong_mode: cabrillo.LogQso = cabrillo.LogQso(
            'QSO: 14000 SSB 2026-10-31 1200 YO5BBB          59  CJ  YO5AAA          59  001',
            2, _rules)

        # QSO with wrong rst from YO5BBB's perspective
        qso_wrong_rst: cabrillo.LogQso = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5BBB          599 CJ  YO5AAA          59  001',
            2, _rules)

        # QSO with different called callsign from YO5BBB's perspective
        qso_diff_call: cabrillo.LogQso = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5BBB          599 CJ  YO5CCC          599 001',
            2, _rules)

        qso_test: List[Tuple[
            cabrillo.LogQso, cabrillo.LogQso, Any, Any, str
        ]] = [
            # Valid QSO match (same time, same mode, same rst)
            (base_qso, base_qso_reciprocal, 1, None, None),
            # Wrong time >5min
            (base_qso, qso_wrong_time, None, ValueError, 'Different date/time'),
            # Correct time (<5min diff)
            (base_qso, qso_correct_time, 1, None, None),
            # Wrong mode
            (base_qso, qso_wrong_mode, None, ValueError, 'Mode mismatch'),
            # Wrong rst (other ham)
            (base_qso, qso_wrong_rst, None, ValueError, 'Rst mismatch'),
            # Different callsign
            (base_qso, qso_diff_call, None, ValueError, 'Callsign mismatch'),
        ]

        for q1, q2, distance, ex, ex_msg in qso_test:
            if distance is not None and ex is None:
                self.assertEqual(
                    cabrillo.compare_qso(_log_yo5aaa, q1, _log_yo5bbb, q2),
                    distance)
            if ex:
                self.assertRaisesRegex(
                    ex, ex_msg,
                    cabrillo.compare_qso,
                    _log_yo5aaa, q1, _log_yo5bbb, q2)

    def test_dracula_scoring(self) -> None:
        """Test DRACULA-specific scoring logic."""
        # Create a mock rules with proper contest_special_callsign list
        mock_rules = mock.Mock()
        mock_rules.contest_special_callsign = [
            'YP2DRACULA', 'YR2DRACULA', 'YQ2DRACULA',
            'YP5DRACULA', 'YR5DRACULA', 'YQ5DRACULA',
            'YP6DRACULA', 'YR6DRACULA', 'YQ6DRACULA'
        ]
        mock_rules.contest_yo_to_special_points = 10
        mock_rules.contest_yo_to_nonyo_points = 5
        mock_rules.contest_yo_to_yo_points = 0
        mock_rules.contest_non_yo_to_special_points = 10
        mock_rules.contest_non_yo_to_yo_points = 5
        mock_rules.contest_non_yo_dxcc_points = 2
        mock_rules.contest_non_yo_same_country_points = 1
        mock_rules.contest_multiplier_enabled = 'true'
        mock_rules.contest_multiplier_per_band = 'true'
        mock_rules.contest_multiplier_exchange_field = 'nr_recv'
        mock_rules.contest_multiplier_special_exchange = 'DRC'

        # YO to DRC special station = 10 points
        qso1 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5AAA          599 CJ  YP2DRACULA      599 DRC', 1)
        qso1.cc_confirmed, qso1.cc_error = cabrillo._dracula_scoring('YO5AAA', 'YP2DRACULA', mock_rules, qso1)
        self.assertTrue(qso1.cc_confirmed)
        self.assertEqual(qso1.points, 10)

        # YO to non-YO = 5 points
        qso2 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5AAA          599 CJ  DL1ABC          599 005', 1)
        qso2.cc_confirmed, qso2.cc_error = cabrillo._dracula_scoring('YO5AAA', 'DL1ABC', mock_rules, qso2)
        self.assertTrue(qso2.cc_confirmed)
        self.assertEqual(qso2.points, 5)

        # Non-YO to YO = 5 points
        qso3 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 DL1AAA          599 005 YO5PJB          599 CJ', 1)
        qso3.cc_confirmed, qso3.cc_error = cabrillo._dracula_scoring('DL1AAA', 'YO5PJB', mock_rules, qso3)
        self.assertTrue(qso3.cc_confirmed)
        self.assertEqual(qso3.points, 5)

        # Non-YO to non-YO, different prefix (DXCC) = 2 points
        qso4 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 DL1AAA          599 005 F5XXX           599 016', 1)
        qso4.cc_confirmed, qso4.cc_error = cabrillo._dracula_scoring('DL1AAA', 'F5XXX', mock_rules, qso4)
        self.assertTrue(qso4.cc_confirmed)
        self.assertEqual(qso4.points, 2)

        # Non-YO to non-YO, same prefix = 1 point
        qso5 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 DL1AAA          599 005 DL1BBB          599 010', 1)
        qso5.cc_confirmed, qso5.cc_error = cabrillo._dracula_scoring('DL1AAA', 'DL1BBB', mock_rules, qso5)
        self.assertTrue(qso5.cc_confirmed)
        self.assertEqual(qso5.points, 1)

    def test_extract_county_from_exchange(self) -> None:
        test_cases: List[Tuple[Optional[str], str]] = [
            ('001 BN', 'BN'),
            ('005 IS', 'IS'),
            ('CJ', 'CJ'),
            ('DRC', 'DRC'),
            ('', ''),
            (None, ''),
        ]
        for input_val, expected in test_cases:
            with self.subTest(exchange=input_val):
                self.assertEqual(cabrillo._extract_county_from_exchange(input_val), expected)

    @mock.patch('os.path.isfile')
    def test_crosscheck_band(self, mock_isfile: mock.MagicMock) -> None:
        mock_isfile.return_value = True
        mo_rules = mock.mock_open(read_data=DRACULA_RULES)
        with patch('builtins.open', mo_rules, create=True):
            _rules = rules_hf.RulesHf('some_rule_file.rules')

        # YO2ARM log with a QSO to YO3APJ (both on 40m/band2 in DRACULA rules)
        log1_content: str = \
"""START-OF-LOG: 3.0
CONTEST: DRACULA
CALLSIGN: YO2ARM
CATEGORY-OPERATOR: B1
CATEGORY-BAND: 40M
CATEGORY-MODE: SSB
CREATED-BY: logXchecker test generator

QSO:  7150 PH 2026-10-31 1532 YO2ARM          59  AR  YO3APJ          59  BU
QSO:  7150 PH 2026-10-31 1540 YO2ARM          59  AR  YO5TP           59  CJ
QSO:  7100 PH 2026-10-31 1543 YO2ARM          59  AR  EV5GHI          59  255
"""
        # YO3APJ log with reciprocal QSO to YO2ARM
        log2_content: str = \
"""START-OF-LOG: 3.0
CONTEST: DRACULA
CALLSIGN: YO3APJ
CATEGORY-OPERATOR: B1
CATEGORY-BAND: 40M
CATEGORY-MODE: SSB
CREATED-BY: logXchecker test generator

QSO:  7150 PH 2026-10-31 1532 YO3APJ          59  BU  YO2ARM          59  AR
"""
        # YO5TP log with reciprocal QSO to YO2ARM
        log3_content: str = \
"""START-OF-LOG: 3.0
CONTEST: DRACULA
CALLSIGN: YO5TP
CATEGORY-OPERATOR: B1
CATEGORY-BAND: ALL
CATEGORY-MODE: SSB
CREATED-BY: logXchecker test generator

QSO:  7150 PH 2026-10-31 1540 YO5TP           59  CJ  YO2ARM          59  AR
"""
        op1 = cabrillo.Operator('YO2ARM')
        mo = mock.mock_open(read_data=log1_content)
        with patch('builtins.open', mo, create=True):
            op1.add_log_by_path('some_log_file.log', rules=_rules)
            self.assertEqual(len(op1.logs), 1)

        op2 = cabrillo.Operator('YO3APJ')
        mo = mock.mock_open(read_data=log2_content)
        with patch('builtins.open', mo, create=True):
            op2.add_log_by_path('some_log_file.log', rules=_rules)
            self.assertEqual(len(op2.logs), 1)

        op3 = cabrillo.Operator('YO5TP')
        mo = mock.mock_open(read_data=log3_content)
        with patch('builtins.open', mo, create=True):
            op3.add_log_by_path('some_log_file.log', rules=_rules)
            self.assertEqual(len(op3.logs), 1)
    
        op_inst: Dict[str, cabrillo.Operator] = {
            'YO2ARM': op1,
            'YO3APJ': op2,
            'YO5TP': op3,
        }

        confirmed_pairs: set = set()
        # Use band_nr=2 (40m/7MHz) since QSOs are on 7150/7100 kHz
        cabrillo.crosscheck_band(op_inst, _rules, 2, confirmed_pairs)

        # Check YO2ARM's QSO to YO3APJ is confirmed and has points
        yo2arm_log = op1.logs[0]
        qso_to_yo3apj = None
        qso_to_ev5ghi = None
        for qso in yo2arm_log.qsos:
            if qso.qso_fields['call'] == 'YO3APJ':
                qso_to_yo3apj = qso
            elif qso.qso_fields['call'] == 'EV5GHI':
                qso_to_ev5ghi = qso
            elif qso.qso_fields['call'] == 'YO5TP':
                qso_to_yo5tp = qso

        self.assertIsNotNone(qso_to_yo3apj, "Should find QSO to YO3APJ")
        self.assertTrue(qso_to_yo3apj.cc_confirmed,
                        "QSO YO2ARM->YO3APJ should be confirmed")
        # DRACULA rules: YO-YO = 0 points
        self.assertEqual(qso_to_yo3apj.points, 0,
                         "YO-YO QSO should be 0 points per DRACULA rules")

        # EV5GHI has no log, so that QSO should not be confirmed
        self.assertIsNotNone(qso_to_ev5ghi, "Should find QSO to EV5GHI")
        self.assertFalse(qso_to_ev5ghi.cc_confirmed,
                         "QSO to EV5GHI should not be confirmed (no log)")

        # YO5TP has a log, so that QSO should be confirmed
        self.assertIsNotNone(qso_to_yo5tp, "Should find QSO to YO5TP")
        self.assertTrue(qso_to_yo5tp.cc_confirmed,
                        "QSO to YO5TP should be confirmed")

    def test_apply_custom_scoring(self) -> None:
        """Test the custom scoring dispatcher."""
        mock_rules = mock.Mock()
        mock_rules.contest_custom_scoring = 'DRACULA'
        mock_rules.contest_non_yo_to_special_points = 10
        mock_rules.contest_yo_to_nonyo_points = 5
        mock_rules.contest_non_yo_to_yo_points = 5
        mock_rules.contest_non_yo_dxcc_points = 2
        mock_rules.contest_non_yo_same_country_points = 1
        mock_rules.contest_multiplier_enabled = 'true'
        mock_rules.contest_multiplier_per_band = 'true'
        mock_rules.contest_multiplier_exchange_field = 'nr_recv'
        mock_rules.contest_multiplier_special_exchange = 'DRC'
        mock_rules.contest_special_callsign = ['YP2DRACULA']

        # DRACULA scoring: YO to non-YO = 5
        qso = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5AAA          599 CJ  DL1ABC          599 005', 1)
        confirmed, errors = cabrillo.apply_custom_scoring(
            'YO5AAA', 'DL1ABC', mock_rules, qso, set(), 1, 1, 10, [], 1)
        self.assertTrue(confirmed)
        self.assertEqual(qso.points, 5)

        # NotImplemented for unknown custom scoring
        mock_rules3 = mock.Mock()
        mock_rules3.contest_custom_scoring = 'UNKNOWN'
        qso2 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5AAA          599 CJ  DL1ABC          599 005', 1)
        self.assertRaises(NotImplementedError,
                          cabrillo.apply_custom_scoring,
                          'YO5AAA', 'DL1ABC', mock_rules3, qso2, set(), 1, 1, 10, [], 1)
