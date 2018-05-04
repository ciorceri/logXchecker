"""
Copyright 2016-2018 Ciorceri Petru Sorin

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

from unittest import TestCase, mock
from unittest.mock import mock_open, patch

import rules
from test_rules import VALID_RULES

import edi
from edi import ERR_FILE, ERR_HEADER, ERR_QSO

valid_edi_log = """
TName=Cupa Nasaud
TDate=20130803;20130806
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
130803;1335;YO5CRQ/M;6;59;004;59;006;;KN17WP;100;;;;
130803;1337;YO5CKZ;6;59;005;59;007;;KN27EG;84;;;;
130803;1438;YO8SSB;6;59;006;59;016;;KN27OD;133;;;;
130803;1438;YO5OO;6;59;007;59;004;;KN16RS;6;;;;
130803;1446;YO6PVT;6;59;008;59;012;;KN16TR;7;;;;
130803;1459;YO6POK;6;59;009;59;015;;KN27JG;109;;;;
130804;0632;YO5TP;6;59;010;59;018;;KN16SS;1;;;;
130804;0632;YO5OO;6;59;011;59;011;;KN16RS;6;;;;
130804;0635;YO5PLP/P;6;59;012;59;031;;KN27HM;116;;;;
130804;0635;YO5CKZ;6;59;013;59;036;;KN27EG;84;;;;
130804;0642;YO6POK;6;59;014;59;030;;KN27JG;109;;;;
130804;0657;YO8SSB;6;59;015;59;035;;KN27OD;133;;;;"""

invalid_edi_log_PBand = """
PCall=YO5PJB
PWWLo=KN16SS
PBand=200 MHz
"""
invalid_edi_log_PSect = """
PCall=YO5PJB
PWWLo=KN16SS
PBand=144 MHz
PSect=extraterrestrial
"""
invalid_edi_log_TDate = """
TDate=20250101;20250102
PCall=YO5PJB
PWWLo=KN16SS
PBand=144 MHz
PSect=SOMB
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
    ('130803;1319;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;', 'Incorrect QSO line format (minimal QSO checks didn\'t pass).'),
    ('30803;1319;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', 'Incorrect QSO line format. (QSO checks didn\'t pass).'),
    ('130803;319;YO5BTZ;;59;001;59;001;;KN16SS;1;;;;', 'Incorrect QSO line format. (QSO checks didn\'t pass).'),
    ('130803;1319;YO5BTZ;6;9;001;59;001;;KN16SS;1;;;;', 'Incorrect QSO line format. (QSO checks didn\'t pass).'),
    ('130803;1319;YO5BTZ;6;59;1;59;001;;KN16SS;1;;;;', 'Incorrect QSO line format. (QSO checks didn\'t pass).'),
    ('130803;1319;YO5BTZ;6;59;00001;59;001;;KN16SS;1;;;;', 'Incorrect QSO line format. (QSO checks didn\'t pass).'),
    ('130803;1319;YO5BTZ;6;59;001;9;001;;KN16SS;1;;;;', 'Incorrect QSO line format. (QSO checks didn\'t pass).'),
    ('130803;1319;YO5BTZ;6;59;001;59;00001;;KN16SS;1;;;;', 'Incorrect QSO line format. (QSO checks didn\'t pass).'),
]

test_logQso_qsos = [
    edi.Log.qsos_tuple(linenr=40, qso='130803;1319;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=41, qso='130803;1321;YO5PLP/P;6;59;002;59;007;;KN27HM;116;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=42, qso='130803;1322;YO5TP;6;59;003;59;002;;KN16SS;1;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=43, qso='130803;1335;YO5CRQ/M;6;59;004;59;006;;KN17WP;100;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=44, qso='130803;1337;YO5CKZ;6;59;005;59;007;;KN27EG;84;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=45, qso='130803;1438;YO8SSB;6;59;006;59;016;;KN27OD;133;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=46, qso='130803;1438;YO5OO;6;59;007;59;004;;KN16RS;6;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=47, qso='130803;1446;YO6PVT;6;59;008;59;012;;KN16TR;7;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=48, qso='130803;1459;YO6POK;6;59;009;59;015;;KN27JG;109;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=49, qso='130804;0632;YO5TP;6;59;010;59;018;;KN16SS;1;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=50, qso='130804;0632;YO5OO;6;59;011;59;011;;KN16RS;6;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=51, qso='130804;0635;YO5PLP/P;6;59;012;59;031;;KN27HM;116;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=52, qso='130804;0635;YO5CKZ;6;59;013;59;036;;KN27EG;84;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=53, qso='130804;0642;YO6POK;6;59;014;59;030;;KN27JG;109;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=54, qso='130804;0657;YO8SSB;6;59;015;59;035;;KN27OD;133;;;;', valid=True,
                       errors=[]),
]

test_logQso_regexp_qso_validator = [
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59;001;59;001;;0016SS;1;;;;', valid=False,
                       errors=[(5, "Incorrect QSO line format. (QSO checks didn't pass).")]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59;001;59;001;;KN1600;1;;;;', valid=False,
                       errors=[(5, "Incorrect QSO line format. (QSO checks didn't pass).")]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59;001;59;001;;KNAASS;1;;;;', valid=False,
                       errors=[(5, "Incorrect QSO line format. (QSO checks didn't pass).")]),
]

test_logQso_generic_qso_validator = [
    edi.Log.qsos_tuple(linenr=1, qso='999999;1319;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(1, 'QSO date is invalid: unconverted data remains: 99')]),
    edi.Log.qsos_tuple(linenr=2, qso='130803;9999;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(2, 'QSO hour is invalid: unconverted data remains: 99')]),
    edi.Log.qsos_tuple(linenr=3, qso='130803;1319;YO5BTZ/P/P;6;59;001;59;001;;KN16SS;1;;;;;', valid=False,
                       errors=[(3, 'Callsign is invalid: YO5BTZ/P/P')]),
    edi.Log.qsos_tuple(linenr=4, qso='130803;1319;YO5BTZ;A;59;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(4, 'QSO mode is invalid: A')]),

    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;09;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(5, 'RST is invalid: 09')]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59A;001;59;001;;KN16SS;1;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59;001;59A;001;;KN16SS;1;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;69;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(5, 'RST is invalid: 69')]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;50;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(5, 'RST is invalid: 50')]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59Z;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(5, 'RST is invalid: 59Z')]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;69A;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(5, 'RST is invalid: 69A')]),

    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59;001;09;001;;KN16SS;1;;;;', valid=False,
                       errors=[(5, 'RST is invalid: 09')]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59;001;69;001;;KN16SS;1;;;;', valid=False,
                       errors=[(5, 'RST is invalid: 69')]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59;001;50;001;;KN16SS;1;;;;', valid=False,
                       errors=[(5, 'RST is invalid: 50')]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59;001;59Z;001;;KN16SS;1;;;;', valid=False,
                       errors=[(5, 'RST is invalid: 59Z')]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59;001;69A;001;;KN16SS;1;;;;', valid=False,
                       errors=[(5, 'RST is invalid: 69A')]),

    edi.Log.qsos_tuple(linenr=6, qso='130803;1319;YO5BTZ;6;59;001;59;001;1234567;KN16SS;1;;;;', valid=False,
                       errors=[(6, 'Received exchange is invalid: 1234567')]),
    edi.Log.qsos_tuple(linenr=7, qso='130803;1319;YO5BTZ;6;59;001;59;001;;ZZ27HM;1;;;;', valid=False,
                       errors=[(7, 'QSO WWL is invalid: ZZ27HM')]),
    edi.Log.qsos_tuple(linenr=7, qso='130803;1319;YO5BTZ;6;59;001;59;001;;KN27ZZ;1;;;;', valid=False,
                       errors=[(7, 'QSO WWL is invalid: KN27ZZ')]),
]

test_logQso_rules_based_qso_validator = [
    edi.Log.qsos_tuple(linenr=1, qso='130802;1200;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(1, 'QSO date is invalid: before contest starts (<130803)'), (1, 'QSO date/hour is invalid: not inside contest periods')]),
    edi.Log.qsos_tuple(linenr=2, qso='130803;1159;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(2, 'QSO hour is invalid: before contest start hour (<1200)'), (2, 'QSO date/hour is invalid: not inside contest periods')]),
    edi.Log.qsos_tuple(linenr=3, qso='130803;1200;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=4, qso='130803;1759;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1800;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(5, 'QSO date/hour is invalid: not inside contest periods')]),
    edi.Log.qsos_tuple(linenr=6, qso='130804;0559;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(6, 'QSO date/hour is invalid: not inside contest periods')]),
    edi.Log.qsos_tuple(linenr=7, qso='130804;0600;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=8, qso='130805;1200;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=9, qso='130806;1159;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=10, qso='130806;1200;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(10, 'QSO hour is invalid: after contest end hour (>1159)'), (10, 'QSO date/hour is invalid: not inside contest periods')]),

    edi.Log.qsos_tuple(linenr=11, qso='130803;1200;YO5BTZ;7;59;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(11, 'QSO mode is invalid: not in defined modes ([1, 2, 6])')]),
]


class TestEdiLog(TestCase):
    def test_init(self):

        # test with missing PCall
        invalid_edi_log = [x for x in valid_edi_log.split('\n') if not x.startswith('PCall=')]
        invalid_edi_log = '\n'.join(invalid_edi_log)
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertDictEqual(log.errors,
                                 {ERR_FILE: [], ERR_HEADER: [(None, 'PCall field is not present')], ERR_QSO: []})

        # test with multiple PCall
        invalid_edi_log = 'PCall=test\n' + valid_edi_log
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertDictEqual(log.errors,
                                 {ERR_FILE: [], ERR_HEADER: [(5, 'PCall field is present multiple times')], ERR_QSO: []})

        # test with missing PWWLo
        invalid_edi_log = [x for x in valid_edi_log.split('\n') if not x.startswith('PWWLo=')]
        invalid_edi_log = '\n'.join(invalid_edi_log)
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertDictEqual(log.errors,
                                 {ERR_FILE: [], ERR_HEADER: [(None, 'PWWLo field is not present')], ERR_QSO: []})

        # test with invalid PWWLo
        invalid_edi_log = 'PWWLo=test\n' + invalid_edi_log
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertDictEqual(log.errors,
                                 {ERR_FILE: [], ERR_HEADER: [(1, 'PWWLo field value is not valid')], ERR_QSO: []})

        # test with multiple PWWLo
        invalid_edi_log = 'PWWLo=test\n' + valid_edi_log
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertDictEqual(log.errors,
                                 {ERR_FILE: [], ERR_HEADER: [(6, 'PWWLo field is present multiple times')], ERR_QSO: []})

        # test with missing PBand
        invalid_edi_log = [x for x in valid_edi_log.split('\n') if not x.startswith('PBand=')]
        invalid_edi_log = '\n'.join(invalid_edi_log)
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertDictEqual(log.errors,
                                 {ERR_FILE: [], ERR_HEADER: [(None, 'PBand field is not present')], ERR_QSO: []})

        # test with invalid PBand
        invalid_edi_log = 'PBand=test\n' + invalid_edi_log
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertDictEqual(log.errors,
                                 {ERR_FILE: [], ERR_HEADER: [(1, 'PBand field value is not valid')], ERR_QSO: []})

        # test with multiple PBand
        invalid_edi_log = 'PBand=test\n' + valid_edi_log
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertDictEqual(log.errors,
                                 {ERR_FILE: [], ERR_HEADER: [(11, 'PBand field is present multiple times')], ERR_QSO: []})

        # test with missing PSect
        invalid_edi_log = [x for x in valid_edi_log.split('\n') if not x.startswith('PSect=')]
        invalid_edi_log = '\n'.join(invalid_edi_log)
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertDictEqual(log.errors,
                                 {ERR_FILE: [], ERR_HEADER: [(None, 'PSect field is not present')], ERR_QSO: []})

        # test with invalid PSect
        invalid_edi_log = 'PSect=test\n' + invalid_edi_log
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertDictEqual(log.errors,
                                 {ERR_FILE: [], ERR_HEADER: [(1, 'PSect field value is not valid')], ERR_QSO: []})

        # test with multiple PSect
        invalid_edi_log = 'PSect=test\n' + valid_edi_log
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertDictEqual(log.errors,
                                 {ERR_FILE: [], ERR_HEADER: [(10, 'PSect field is present multiple times')], ERR_QSO: []})

        # test with missing TDate
        invalid_edi_log = [x for x in valid_edi_log.split('\n') if not x.startswith('TDate=')]
        invalid_edi_log = '\n'.join(invalid_edi_log)
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertDictEqual(log.errors,
                                 {ERR_FILE: [], ERR_HEADER: [(None, 'TDate field is not present')], ERR_QSO: []})

        # test with invalid TDate
        invalid_edi_log2 = 'TDate=20170101,20170102\n' + invalid_edi_log
        mo = mock.mock_open(read_data=invalid_edi_log2)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertDictEqual(log.errors,
                                 {ERR_FILE: [], ERR_HEADER: [(1, 'TDate field value is not valid (20170101,20170102)')],
                                  ERR_QSO: []})

        invalid_edi_log2 = 'TDate=20170101;201701020\n' + invalid_edi_log
        mo = mock.mock_open(read_data=invalid_edi_log2)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertDictEqual(log.errors,
                                 {ERR_FILE: [],
                                  ERR_HEADER: [(1, 'TDate field value is not valid (20170101;201701020)')],
                                  ERR_QSO: []})

        # test with multiple TDate
        invalid_edi_log2 = 'TDate=test\n' + valid_edi_log
        mo = mock.mock_open(read_data=invalid_edi_log2)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertDictEqual(log.errors,
                                 {ERR_FILE: [],
                                  ERR_HEADER: [(4, 'TDate field is present multiple times')],
                                  ERR_QSO: []})

    @mock.patch('os.path.isfile')
    def test_init_with_rules(self, mock_isfile):
        mock_isfile.return_value = True
        mo_rules = mock.mock_open(read_data=VALID_RULES)
        with patch('builtins.open', mo_rules, create=True):
            _rules = rules.Rules('some_rule_file.rules')

        # test with valid rules and with valid edi log
        mo_log = mock.mock_open(read_data=valid_edi_log)
        with patch('builtins.open', mo_log, create=True):
            edi.Log('some_log_file.edi', rules=_rules)

        # test with valid rules and with invalid edi log (invalid PBand)
        mo_log = mock.mock_open(read_data=invalid_edi_log_PBand)
        with patch('builtins.open', mo_log, create=True):
            log = edi.Log('some_log_file.edi', rules=_rules)
            self.assertFalse(log.valid_header)
            self.assertDictEqual(log.errors,
                                 {ERR_FILE: [], ERR_HEADER: [(4, 'PBand field value has an invalid value (200 MHz). '
                                                             'Not as defined in contest rules'),
                                                         (None, 'PSect field is not present'),
                                                         (None, 'TDate field is not present')], ERR_QSO: []})

        # test with valid rules and with invalid edi log (invalid PSect)
        mo_log = mock.mock_open(read_data=invalid_edi_log_PSect)
        with patch('builtins.open', mo_log, create=True):
            log = edi.Log('some_log_file.edi', rules=_rules)
            self.assertFalse(log.valid_header)
            self.assertDictEqual(log.errors,
                                 {ERR_FILE: [],
                                  ERR_HEADER: [(5, 'PSect field value has an invalid value (extraterrestrial). '
                                             'Not as defined in contest rules'),
                                             (None, 'TDate field is not present')],
                                  ERR_QSO: []})

        # test with valid rules and with invalid edi log (invalid TDate)
        mo_log = mock.mock_open(read_data=invalid_edi_log_TDate)
        with patch('builtins.open', mo_log, create=True):
            log = edi.Log('some_log_file.edi', rules=_rules)
            self.assertFalse(log.valid_header)
            self.assertDictEqual(log.errors,
                                 {ERR_FILE: [],
                                  ERR_HEADER: [(2, 'TDate field value has an invalid value (20250101;20250102). '
                                                 'Not as defined in contest rules')],
                                  ERR_QSO: []})

    def test_read_file_content(self):
        # test 'read_file_content', the buildins.open is mocked
        mo = mock_open(read_data=valid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
        self.assertEqual(valid_edi_log, ''.join(log.log_lines))

        # test 'read_file_content' exceptions
        log = edi.Log('non-existing-log-file.edi')
        self.assertFalse(log.valid_header)
        self.assertDictEqual(log.errors,
                             {ERR_FILE: [(None, 'Cannot read edi log')], ERR_HEADER: [], ERR_QSO: []})

    @mock.patch.object(edi.Log, 'read_file_content')
    def test_get_field(self, mock_read_file_content):
        mock_read_file_content.return_value = valid_edi_log.split('\n')
        log = edi.Log('some_log_file.edi')
        self.assertTupleEqual((['YO5PJB'], 4), log.get_field('PCall'))
        self.assertTupleEqual((['YO5PJB'], 4), log.get_field('pcall'))

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
            _error1 = qso1.errors
            _ln2 = qso2.line_nr
            _qso2 = qso2.qso_line
            _valid2 = qso2.valid
            _error2 = qso2.errors
            print("DEBUG : ", _error1, _error2)
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

    def test_get_band(self):
        positive_tests_144 = ['144', '145', '144mhz', '145mhz']
        negative_tests_144 = [' 144', ' 145', '143', '146']
        positive_tests_432 = ['430', '432', '435', '430mhz', '432mhz', '432.200', '435mhz']
        negative_tests_432 = ['431', '433', '434']

        for test in positive_tests_144:
            self.assertEqual(144, edi.Log.get_band(test))

        for test in negative_tests_144:
            self.assertIsNone(edi.Log.get_band(test))

        for test in positive_tests_432:
            self.assertEqual(432, edi.Log.get_band(test))

        for test in negative_tests_432:
            self.assertIsNone(edi.Log.get_band(test))

    def test_validate_band(self):
        positive_tests = ['144', '145', '144mhz', '145mhz', '430', '432', '435', '430mhz', '432mhz', '432.2',
                          '435hz', '1296', '1296mhz', '1.2g', '1.3g']
        negative_tests = ['143', '146', '431', '433', '1200']
        for test in positive_tests:
            self.assertTrue(edi.Log.validate_band(test))
        for test in negative_tests:
            self.assertFalse(edi.Log.validate_band(test))

    @mock.patch('os.path.isfile')
    def test_rules_based_validate_band(self, mock_isfile):
        mock_isfile.return_value = True
        positive_tests = ['144', '145', '144mhz', '145mhz', '430', '432', '430mhz', '432mhz', '432.2']
        negative_tests = ['143', '146', '431', '433', '435']

        mo = mock.mock_open(read_data=VALID_RULES)
        with patch('builtins.open', mo, create=True):
            _rules = rules.Rules('some_rule_file.rules')
        for test in positive_tests:
            self.assertTrue(edi.Log.rules_based_validate_band(test, _rules))
        for test in negative_tests:
            self.assertFalse(edi.Log.rules_based_validate_band(test, _rules))

    def test_validate_section(self):
        positive_tests = ['so', 'sosb', 'somb', 'single', 'single op', 'single-op',
                          'mo', 'mosb', 'momb', 'multi', 'multi op', 'multi-op']
        negative_tests = ['operator', 'band']
        for test in positive_tests:
            self.assertTrue(edi.Log.validate_section(test))
        for test in negative_tests:
            self.assertFalse(edi.Log.validate_section(test))

    @mock.patch('os.path.isfile')
    def test_rules_based_validate_section(self, mock_isfile):
        mock_isfile.return_value = True
        positive_tests = ['so', 'sosb', 'somb', 'single', 'mo', 'multi',
                          'single-op', 'single-operator', 'single operator',
                          'multi-op', 'multi-operator' 'multi operator']
        negative_tests = ['operator', 'band']
        mo = mock.mock_open(read_data=VALID_RULES)
        with patch('builtins.open', mo, create=True):
            _rules = rules.Rules('some_rule_file.rules')
        for test in positive_tests:
            self.assertTrue(edi.Log.rules_based_validate_section(test, _rules))
        for test in negative_tests:
            self.assertFalse(edi.Log.rules_based_validate_section(test, _rules))

class TestEdiLogQso(TestCase):
    def test_init(self):
        for (linenr, qso, valid, error) in test_logQso_qsos:
            lq = edi.LogQso(qso, linenr)
            self.assertEqual(lq.line_nr, linenr)
            self.assertEqual(lq.qso_line, qso)
            self.assertEqual(lq.valid, valid)
            self.assertEqual(lq.errors, error)

    def test_qso_parser(self):
        lqlist = []
        for qso in test_valid_qso_lines:
            lq = edi.LogQso(qso, 1).qso_fields
            lqlist.append(lq.copy())
        self.assertEqual(lqlist, test_valid_qso_fields)

    def test_valid_qso_line(self):
        for line in test_valid_qso_lines:
            self.assertIsNone(edi.LogQso.regexp_qso_validator(line))

        for (line, message) in test_invalid_qso_lines:
            ret = edi.LogQso.regexp_qso_validator(line)
            self.assertEqual(message, ret)

    def test_regexp_qso_validator(self):
        for (linenr, qso, valid, errors) in test_logQso_regexp_qso_validator:
            lq = edi.LogQso(qso, linenr)
            self.assertEqual(lq.line_nr, linenr)
            self.assertEqual(lq.qso_line, qso)
            self.assertEqual(lq.valid, valid)
            self.assertEqual(lq.errors, errors)

    def test_generic_qso_validator(self):
        for (linenr, qso, valid, errors) in test_logQso_generic_qso_validator:
            lq = edi.LogQso(qso, linenr)
            self.assertEqual(lq.line_nr, linenr)
            self.assertEqual(lq.qso_line, qso)
            self.assertEqual(lq.valid, valid)
            self.assertEqual(lq.errors, errors)

    @mock.patch('os.path.isfile')
    def test_rules_based_qso_validator(self, mock_isfile):
        mock_isfile.return_value = True
        mo = mock.mock_open(read_data=VALID_RULES)
        with patch('builtins.open', mo, create=True):
            _rules = rules.Rules('some_rule_file.rules')

        # test qso date&time based on
        for (linenr, qso, valid, error) in test_logQso_rules_based_qso_validator:
            lq = edi.LogQso(qso, linenr, rules=_rules)
            self.assertEqual(lq.line_nr, linenr)
            self.assertEqual(lq.qso_line, qso)
            self.assertEqual(lq.valid, valid)
            self.assertEqual(lq.errors, error)
