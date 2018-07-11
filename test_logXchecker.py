"""
Copyright 2018 Ciorceri Petru Sorin (yo5pjb)

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

import unittest
from unittest import mock
from unittest.mock import patch

import edi
import rules
import logXchecker

VALID_RULES = '''
[contest]
name=Cupa Nasaud
begindate=20130803
enddate=20130806
beginhour=1200
endhour=1159
bands=1
periods=1
categories=1
modes=1,2,6

[log]
format=edi

[band1]
band=144
regexp=144|145|2m
multiplier=1

[period1]
begindate=20130803
enddate=20130803
beginhour=1200
endhour=1759
bands=band1

[category1]
name=Single Operator 144
regexp=so|single
bands=band1
'''

QSOS = '''130803;1200;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;
130804;1200;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;
130903;1200;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;
140803;1200;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;
130803;1205;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;
130803;1155;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;
130803;1210;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;
'''



class TestHelperMethods(unittest.TestCase):
    def test_qth_distance(self):
        distance = [('KN16SS', 'KN16SS', 1),
                    ('KN16SS', 'KN16SQ', 9),
                    ('KN16SS', 'KN17SS', 111)]
        for qth1, qth2, km in distance:
            self.assertEqual(logXchecker.qth_distance(qth1, qth2), km)

    @patch('os.path.isfile')
    def test_compare_qso(self, mock_isfile):
        mock_isfile.return_value = True
        mo_rules = mock.mock_open(read_data=VALID_RULES)
        with patch('builtins.open', mo_rules, create=True):
            _rules = rules.Rules('some_rule_file.rules')

        _log = edi.Log('log1.edi')
        _log.callsign = 'YO5AAA'
        _log.maidenhead_locator = 'KN16AA'
        _log.valid_header = True
        _log.valid_qsos = True

        qso_list = [
            # base qso (0)
            edi.LogQso('130803;1200;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            # qso's with date issues (1-6)
            edi.LogQso('120803;1200;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('140803;1200;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130703;1200;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130903;1200;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130802;1200;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130804;1200;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            # qso's with time issues (7-11)
            edi.LogQso('130803;1159;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1150;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1205;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1206;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1210;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            # qso's with callsign error (12-16)
            edi.LogQso('130803;1200;YO5AAA/P;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1200;YO5AAA-P;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1200;YO5AAA/M;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1200;YO5AAA-M;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1200;YO5BBB;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            # qso's with mode issues (17-18)
            edi.LogQso('130803;1200;YO5AAA;1;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1200;YO5AAA;4;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            # TODO
            # qso's with RST issues
            # qso's with QTH issues
            # qso's with duplicate issues
        ]

        qso_test = (
            # test different date
            (qso_list[0], qso_list[1], None, ValueError, 'Different date/time between qso\'s'),
            (qso_list[0], qso_list[2], None, ValueError, 'Different date/time between qso\'s'),
            (qso_list[0], qso_list[3], None, ValueError, 'Different date/time between qso\'s'),
            (qso_list[0], qso_list[4], None, ValueError, 'Different date/time between qso\'s'),
            (qso_list[0], qso_list[5], None, ValueError, 'Different date/time between qso\'s'),
            (qso_list[0], qso_list[6], None, ValueError, 'Different date/time between qso\'s'),
            # reverse test of different date
            (qso_list[1], qso_list[0], None, ValueError, 'Qso date is invalid: before contest starts \(<130803\)'),
            (qso_list[2], qso_list[0], None, ValueError, 'Qso date is invalid: after contest ends \(>130806\)'),
            (qso_list[3], qso_list[0], None, ValueError, 'Qso date is invalid: before contest starts \(<130803\)'),
            (qso_list[4], qso_list[0], None, ValueError, 'Qso date is invalid: after contest ends \(>130806\)'),
            (qso_list[5], qso_list[0], None, ValueError, 'Qso date is invalid: before contest starts \(<130803\)'),
            (qso_list[6], qso_list[0], None, ValueError, 'Qso date/hour is invalid: not inside contest periods'),
            # test different time
            (qso_list[0], qso_list[7], 1, None, None),
            (qso_list[0], qso_list[8], None, ValueError, 'Different date/time between qso\'s'),
            (qso_list[0], qso_list[9], 1, None, None),
            (qso_list[0], qso_list[10], None, ValueError, 'Different date/time between qso\'s'),
            (qso_list[0], qso_list[11], None, ValueError, 'Different date/time between qso\'s'),
            # reverse test of different time
            (qso_list[7], qso_list[0], None, ValueError, 'Qso hour is invalid: before contest start hour \(<1200\)'),
            (qso_list[8], qso_list[0], None, ValueError, 'Qso hour is invalid: before contest start hour \(<1200\)'),
            (qso_list[9], qso_list[0], 1, None, None),
            (qso_list[10], qso_list[0], None, ValueError, 'Different date/time between qso\'s'),
            (qso_list[11], qso_list[0], None, ValueError, 'Different date/time between qso\'s'),
            # test different callsign
            (qso_list[0], qso_list[12], -1, None, None),
            (qso_list[0], qso_list[13], None, None, None),
            (qso_list[0], qso_list[14], -1, None, None),
            (qso_list[0], qso_list[15], -1, None, None),
            (qso_list[0], qso_list[16], -1, None, None),
            # reverse test of different callsign
            (qso_list[12], qso_list[0], -1, None, None),
            (qso_list[13], qso_list[0], None, ValueError, 'Callsign is invalid: YO5AAA-P'),
            (qso_list[14], qso_list[0], -1, None, None),
            (qso_list[15], qso_list[0], None, ValueError, 'Callsign is invalid: YO5AAA-M'),
            (qso_list[16], qso_list[0], -1, None, None),
            # test different modes
            (qso_list[0], qso_list[17], None, ValueError, 'Mode mismatch'),
            (qso_list[0], qso_list[18], None, ValueError, 'Mode mismatch'),
            # reverse test of different modes
            (qso_list[17], qso_list[0], None, ValueError, 'Mode mismatch'),
            (qso_list[18], qso_list[0], None, ValueError, 'Qso mode is invalid: not in defined modes \(\[1, 2, 6\]\)'),
        )

        for q1, q2, r, ex, ex_msg in qso_test:
            print('>>>>>', q1.qso_line, q2.qso_line)
            if r:
                self.assertEqual(logXchecker.compare_qso(_log, q1, _log, q2), r)
            if ex:
                self.assertRaisesRegex(ex, ex_msg, logXchecker.compare_qso, _log, q1, _log, q2)

