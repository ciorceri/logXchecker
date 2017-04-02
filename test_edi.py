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
from test_rules import valid_rules

import edi

valid_edi_log = """
[REG1TEST;1]
TName=Cupa Nasaud
TDate=20130803;20130804
PCall=YO5PJB
PWWLo=KN16SS
PExch=
PAdr1=
PAdr2=
PSect=SOMB
PBand=144 MHz
PClub=
RName=Sorin
RCall=
Radr1=
Radr2=
RPoCo=
RCity=
RCoun=Romania
RPhon=
RHBBS=
MOpe1=
MOpe2=
STXEq=FT 857
SPowe=30W
SRXEq=
SAnte=Yagi 3EL
SAntH=
CQSOs=15,1
CQSOP=1006
CWWLs=
CWWLB=
CExcs=
CExcB=
CDXCs=
CDXCB=
CToSc=1006
CODXC=YO8SSB;KN27OD;133
[Remarks]

[QSORecords;15]
130803;1319;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;
130803;1321;YO5PLP/P;6;59;002;59;007;;KN27HM;116;;;;
130803;1322;YO5TP;6;59;003;59;002;;KN16SS;1;;;;
[END;PaperQSO version 0.0.9.803]
"""

test_valid_qso_lines = [
    '130803;1319;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;',
    '160507;1531;YO7LBX/P;1;59;006;59;016;;KN14QW;76;;;;',
    '160507;1404;HA6W;1;59;001;59;005;;KN08FB;149;;N;N;',
]

test_valid_qso_fields = [
    {
        'date': '130803',
        'hour': '1319',
        'call': 'YO5BTZ',
        'mode': '6',
        'rst_sent': '59',
        'nr_sent': '001',
        'rst_recv': '59',
        'nr_recv': '001',
        'exchange_recv': '',
        'wwl': 'KN16SS',
        'points': '1',
        'new_exchange': '',
        'new_wwl': '',
        'new_dxcc': '',
        'duplicate_qso': ''
    },
    {
        'date': '160507',
        'hour': '1531',
        'call': 'YO7LBX/P',
        'mode': '1',
        'rst_sent': '59',
        'nr_sent': '006',
        'rst_recv': '59',
        'nr_recv': '016',
        'exchange_recv': '',
        'wwl': 'KN14QW',
        'points': '76',
        'new_exchange': '',
        'new_wwl': '',
        'new_dxcc': '',
        'duplicate_qso': ''
    },
    {
        'date': '160507',
        'hour': '1404',
        'call': 'HA6W',
        'mode': '1',
        'rst_sent': '59',
        'nr_sent': '001',
        'rst_recv': '59',
        'nr_recv': '005',
        'exchange_recv': '',
        'wwl': 'KN08FB',
        'points': '149',
        'new_exchange': '',
        'new_wwl': 'N',
        'new_dxcc': 'N',
        'duplicate_qso': ''
    },
]

test_invalid_qso_lines = [
    ('123456789012345678', 'QSO line is too short'),
    ('130803;1319;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;', 'Minimal QSO checks didn\'t pass'),
    ('30803;1319;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', 'QSO checks didn\'t pass'),
    ('130803;319;YO5BTZ;;59;001;59;001;;KN16SS;1;;;;', 'QSO checks didn\'t pass'),
    ('130803;1319;YO5BTZ;6;9;001;59;001;;KN16SS;1;;;;', 'QSO checks didn\'t pass'),
    ('130803;1319;YO5BTZ;6;59;1;59;001;;KN16SS;1;;;;', 'QSO checks didn\'t pass'),
    ('130803;1319;YO5BTZ;6;59;00001;59;001;;KN16SS;1;;;;', 'QSO checks didn\'t pass'),
    ('130803;1319;YO5BTZ;6;59;001;9;001;;KN16SS;1;;;;', 'QSO checks didn\'t pass'),
    ('130803;1319;YO5BTZ;6;59;001;59;00001;;KN16SS;1;;;;', 'QSO checks didn\'t pass'),
]

test_logQso_qsos = [
    edi.Log.qsos_tuple(linenr=41, qso='130803;1319;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=True, error=None),
    edi.Log.qsos_tuple(linenr=42, qso='130803;1321;YO5PLP/P;6;59;002;59;007;;KN27HM;116;;;;', valid=True, error=None),
    edi.Log.qsos_tuple(linenr=43, qso='130803;1322;YO5TP;6;59;003;59;002;;KN16SS;1;;;;', valid=True, error=None),
]

test_invalid_logQso_qsos = [
    edi.Log.qsos_tuple(linenr=1, qso='160804;1319;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=True,
                       error='Qso date is invalid: before contest starts (<160805)'),
    edi.Log.qsos_tuple(linenr=1, qso='160807;1319;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=True,
                       error='Qso date is invalid: after contest ends (>160806)'),
    edi.Log.qsos_tuple(linenr=1, qso='999999;1319;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=True,
                       error='Qso date is invalid: unconverted data remains: 99'),

    edi.Log.qsos_tuple(linenr=2, qso='160805;1100;YO5PLP/P;6;59;002;59;007;;KN27HM;116;;;;', valid=True,
                       error='Qso hour is invalid: before contest start hour (<1200)'),
    edi.Log.qsos_tuple(linenr=2, qso='160805;1300;YO5PLP/P;6;59;002;59;007;;KN27HM;116;;;;', valid=True, error=None),
    edi.Log.qsos_tuple(linenr=2, qso='160806;1300;YO5PLP/P;6;59;002;59;007;;KN27HM;116;;;;', valid=True,
                       error='Qso hour is invalid: after contest end hour (>1200)'),
    edi.Log.qsos_tuple(linenr=2, qso='160806;1100;YO5PLP/P;6;59;002;59;007;;KN27HM;116;;;;', valid=True, error=None),
    edi.Log.qsos_tuple(linenr=2, qso='160805;9999;YO5PLP/P;6;59;002;59;007;;KN27HM;116;;;;', valid=True,
                       error='Qso hour is invalid: unconverted data remains: 99'),

    edi.Log.qsos_tuple(linenr=3, qso='160805;1300;YO5PLP/P;6;09;002;59;007;;KN27HM;116;;;;', valid=True,
                       error='RST is invalid: 09'),
    edi.Log.qsos_tuple(linenr=3, qso='160805;1300;YO5PLP/P;6;69;002;59;007;;KN27HM;116;;;;', valid=True,
                       error='RST is invalid: 69'),
    edi.Log.qsos_tuple(linenr=3, qso='160805;1300;YO5PLP/P;6;50;002;59;007;;KN27HM;116;;;;', valid=True,
                       error='RST is invalid: 50'),
    edi.Log.qsos_tuple(linenr=3, qso='160805;1300;YO5PLP/P;6;59A;002;59;007;;KN27HM;116;;;;', valid=True, error=None),
    edi.Log.qsos_tuple(linenr=3, qso='160805;1300;YO5PLP/P;6;59Z;002;59;007;;KN27HM;116;;;;', valid=True,
                       error='RST is invalid: 59Z'),
    edi.Log.qsos_tuple(linenr=3, qso='160805;1300;YO5PLP/P;6;69A;002;59;007;;KN27HM;116;;;;', valid=True,
                       error='RST is invalid: 69A'),

    edi.Log.qsos_tuple(linenr=4, qso='160805;1300;YO5PLP/P;6;59;002;09;007;;KN27HM;116;;;;', valid=True,
                       error='RST is invalid: 09'),
    edi.Log.qsos_tuple(linenr=4, qso='160805;1300;YO5PLP/P;6;59;002;69;007;;KN27HM;116;;;;', valid=True,
                       error='RST is invalid: 69'),
    edi.Log.qsos_tuple(linenr=4, qso='160805;1300;YO5PLP/P;6;59;002;50;007;;KN27HM;116;;;;', valid=True,
                       error='RST is invalid: 50'),
    edi.Log.qsos_tuple(linenr=4, qso='160805;1300;YO5PLP/P;6;59;002;59A;007;;KN27HM;116;;;;', valid=True, error=None),
    edi.Log.qsos_tuple(linenr=4, qso='160805;1300;YO5PLP/P;6;59;002;59Z;007;;KN27HM;116;;;;', valid=True,
                       error='RST is invalid: 59Z'),
    edi.Log.qsos_tuple(linenr=4, qso='160805;1300;YO5PLP/P;6;59;002;69A;007;;KN27HM;116;;;;', valid=True,
                       error='RST is invalid: 69A'),

    edi.Log.qsos_tuple(linenr=5, qso='160805;1300;YO5PLP/P;6;59;002;59;007;;0027HM;116;;;;', valid=False,
                       error='QSO checks didn\'t pass'),
    edi.Log.qsos_tuple(linenr=5, qso='160805;1300;YO5PLP/P;6;59;002;59;007;;KN2700;116;;;;', valid=False,
                       error='QSO checks didn\'t pass'),
    edi.Log.qsos_tuple(linenr=5, qso='160805;1300;YO5PLP/P;6;59;002;59;007;;KNAAHM;116;;;;', valid=False,
                       error='QSO checks didn\'t pass'),
    edi.Log.qsos_tuple(linenr=5, qso='160805;1300;YO5PLP/P;6;59;002;59;007;;ZZ27HM;116;;;;', valid=True,
                       error='Qso WWL is invalid'),
    edi.Log.qsos_tuple(linenr=5, qso='160805;1300;YO5PLP/P;6;59;002;59;007;;KN27ZZ;116;;;;', valid=True,
                       error='Qso WWL is invalid'),
]


class TestEdiLog(TestCase):
    def test_read_file_content(self):
        # test 'read_file_content', the buildins.open is mocked
        mo = mock_open(read_data=valid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
        self.assertEqual(valid_edi_log, ''.join(log.log_content))
        # test 'read_file_content' exceptions
        self.assertRaises(FileNotFoundError, edi.Log, 'non-existing-log-file.edi')

    def validate_log_content(self):
        pass

    @mock.patch.object(edi.Log, 'read_file_content')
    def test_get_field(self, mock_read_file_content):
        mock_read_file_content.return_value = valid_edi_log.split('\n')
        log = edi.Log('some_log_file.edi')
        self.assertEqual('YO5PJB', log.get_field('PCall')[0])
        self.assertEqual('YO5PJB', log.get_field('pcall')[0])
        self.assertNotEqual('yo5pjb', log.get_field('pcall')[0])
        self.assertNotEqual('INVALID_CALLSIGN', log.get_field('PCall')[0])

    @mock.patch.object(edi.Log, 'read_file_content')
    def test_get_qsos(self, mock_read_file_content):
        self.maxDiff = None
        mock_read_file_content.return_value = valid_edi_log.split('\n')
        log = edi.Log('some_log_file.edi')
        self.assertEqual(len(test_logQso_qsos), len(log.qsos))
        for qso1, qso2 in zip(test_logQso_qsos, log.qsos):
            _ln1 = qso1.linenr
            _qso1 = qso1.qso
            _valid1 = qso1.valid
            _error1 = qso1.error
            _ln2 = qso2.qso_line_number
            _qso2 = qso2.qso_line
            _valid2 = qso2.valid_qso
            _error2 = qso2.error_message
            self.assertEqual(_ln1, _ln2)
            self.assertEqual(_qso1, _qso2)
            self.assertEqual(_valid1, _valid2)
            self.assertEqual(_error1, _error2)
        # self.assertEqual(test_logQso_qsos, log.qsos)

    def test_validate_qth_locator(self):
        positive_tests = ['KN16SS', 'kn16ss', 'AA00AA', 'RR00XX']
        negative_tests = ['0016SS', 'KNXXSS', 'KN1600', 'KN16SS00', '00KN16SS']

        for test in positive_tests:
            self.assertTrue(edi.Log.validate_qth_locator(test))
        for test in negative_tests:
            self.assertFalse(edi.Log.validate_qth_locator(test))

    def test_validate_band(self):
        # TODO: test for this function
        pass

    def test_rules_based_validate_band(self):
        # TODO: test for this function
        pass


class TestEdiLogQso(TestCase):
    def test_init(self):
        for _qso in test_logQso_qsos:
            linenr = _qso.linenr
            qso = _qso.qso
            valid = _qso.valid
            error = _qso.error
            lq = edi.LogQso(qso, linenr)
            self.assertEqual(lq.qso_line_number, linenr)
            self.assertEqual(lq.qso_line, qso)
            self.assertEqual(lq.valid_qso, valid)
            self.assertEqual(lq.error_message, error)

    @mock.patch('os.path.isfile')
    def test_init_with_rules(self, mock_isfile):
        mock_isfile.return_value = True
        mo = mock.mock_open(read_data=valid_rules)
        with patch('builtins.open', mo, create=True):
            _rules = rules.Rules('some_rule_file.rules')

        for _qso in test_invalid_logQso_qsos:
            linenr = _qso.linenr
            qso = _qso.qso
            valid = _qso.valid
            error = _qso.error
            lq = edi.LogQso(qso, linenr, rules=_rules)
            self.assertEqual(lq.qso_line_number, linenr)
            self.assertEqual(lq.qso_line, qso)
            self.assertEqual(lq.valid_qso, valid)
            self.assertEqual(lq.error_message, error)

    def test_qso_parser(self):
        lqlist = []
        for qso in test_valid_qso_lines:
            lq = edi.LogQso(qso, 1).qsoFields
            lqlist.append(lq.copy())
        self.assertEqual(lqlist, test_valid_qso_fields)

    def test_validate_qso(self):
        pass

    def test_valid_qso_line(self):
        for line in test_valid_qso_lines:
            self.assertIsNone(edi.LogQso.regexp_qso_validator(line))

        for (line, message) in test_invalid_qso_lines:
            ret = edi.LogQso.regexp_qso_validator(line)
            self.assertEqual(message, ret)

