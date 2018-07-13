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
            self.assertEqual(edi.qth_distance(qth1, qth2), km)

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
            # qso's with wrong date (1-6)
            edi.LogQso('120803;1200;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('140803;1200;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130703;1200;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130903;1200;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130802;1200;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130804;1200;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            # qso's with wrong time (7-11)
            edi.LogQso('130803;1159;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1150;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1205;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1206;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1210;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            # qso's with wrong callsign (12-16)
            edi.LogQso('130803;1200;YO5AAA/P;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1200;YO5AAA-P;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1200;YO5AAA/M;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1200;YO5AAA-M;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1200;YO5BBB;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            # qso's with wrong mode (17-18)
            edi.LogQso('130803;1200;YO5AAA;1;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1200;YO5AAA;4;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
            # qso's with wrong rst & serial (19-22)
            edi.LogQso('130803;1200;YO5AAA;6;58;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1200;YO5AAA;6;59;002;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1200;YO5AAA;6;59;001;58;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1200;YO5AAA;6;59;001;59;002;;KN16AA;1;;;;', 1, _rules),
            # qso with invalid rst & serial (23-26)
            edi.LogQso('130803;1200;YO5AAA;6;00;001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1200;YO5AAA;6;59;001;00;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1200;YO5AAA;6;59;00001;59;001;;KN16AA;1;;;;', 1, _rules),
            edi.LogQso('130803;1200;YO5AAA;6;59;001;59;00001;;KN16AA;1;;;;', 1, _rules),
            # qso with wrong qth (27)
            edi.LogQso('130803;1200;YO5AAA;6;59;001;59;001;;KN16AB;1;;;;', 1, _rules),
            # qso with invalid qth (28)
            edi.LogQso('130803;1200;YO5AAA;6;59;001;59;001;;ZZ16ZZ;1;;;;', 1, _rules),
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
            # test different rst & serial
            (qso_list[0], qso_list[19], None, ValueError, 'Rst mismatch'),
            (qso_list[0], qso_list[20], None, ValueError, 'Serial number mismatch'),
            (qso_list[0], qso_list[21], None, ValueError, 'Rst mismatch'),
            (qso_list[0], qso_list[22], None, ValueError, 'Serial number mismatch'),
            # reverse test of differe rst & serial
            (qso_list[19], qso_list[0], None, ValueError, 'Rst mismatch'),
            (qso_list[20], qso_list[0], None, ValueError, 'Serial number mismatch'),
            (qso_list[21], qso_list[0], None, ValueError, 'Rst mismatch'),
            (qso_list[22], qso_list[0], None, ValueError, 'Serial number mismatch'),
            # test invalid rst & serial
            (qso_list[0], qso_list[23], None, ValueError, 'Rst mismatch'),
            (qso_list[0], qso_list[24], None, ValueError, 'Rst mismatch'),
            (qso_list[0], qso_list[25], -1, None, None),
            (qso_list[0], qso_list[26], -1, None, None),
            # reverse test of invalid rst & serial
            (qso_list[23], qso_list[0], None, ValueError, 'Rst is invalid: 00'),
            (qso_list[24], qso_list[0], None, ValueError, 'Rst is invalid: 00'),
            (qso_list[25], qso_list[0], None, ValueError, 'Qso field <rst send nr> has an invalid value \(00001\)'),
            (qso_list[26], qso_list[0], None, ValueError, 'Qso field <rst received nr> has an invalid value \(00001\)'),
            # test different qth
            (qso_list[0], qso_list[27], None, ValueError, 'Qth locator mismatch'),
            (qso_list[27], qso_list[0], None, ValueError, 'Qth locator mismatch'),
            # test invalid qth
            (qso_list[0], qso_list[28], None, ValueError, 'Qth locator mismatch'),
            (qso_list[28], qso_list[0], None, ValueError, 'Qso WWL is invalid: ZZ16ZZ'),
        )

        for q1, q2, r, ex, ex_msg in qso_test:
            if r:
                self.assertEqual(edi.compare_qso(_log, q1, _log, q2), r)
            if ex:
                self.assertRaisesRegex(ex, ex_msg, edi.compare_qso, _log, q1, _log, q2)

