"""
Copyright 2016-2024 Ciorceri Petru Sorin (yo5pjb)

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
from test_rules import VALID_RULES, VALID_RULES_BASIC

import edi
from edi import ERR_IO, ERR_HEADER, ERR_QSO


valid_edi_log = \
"""TName=Cupa Nasaud
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
130804;0657;YO8SSB;2;599;015;599;035;;KN27OD;133;;;;"""

invalid_edi_log_PCall = """
PCall=LZ1NY
PWWLo=KN16SS
PBand=144 MHz
PSect=SOMB
TDate=20130803;20130806
RHBBS=name@email.com
PAdr1=Sesame Street, 13
RName=John Doe
"""

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
PCall=YO5PJB
PWWLo=KN16SS
PBand=144 MHz
PSect=SOMB
TDate=20250101;20250102
"""

invalid_edi_log_RHBBS = """
PCall=YO5PJB
PWWLo=KN16SS
PBand=144 MHz
PSect=SOMB
TDate=20130803;20130806
RHBBS=invalid email address
"""

invalid_edi_log_RHBBS_2 = """
PCall=YO5PJB
PWWLo=KN16SS
PBand=144 MHz
PSect=SOMB
TDate=20130803;20130806
RHBBS=mail1@mail.com
RHBBS=mail2@mail.com
"""

invalid_edi_log_PAdr1 = """
PCall=YO5PJB
PWWLo=KN16SS
PBand=144 MHz
PSect=SOMB
TDate=20130803;20130806
RHBBS=name@email.com
PAdr1=None 
"""

invalid_edi_log_PAdr1_2 = """
PCall=YO5PJB
PWWLo=KN16SS
PBand=144 MHz
PSect=SOMB
TDate=20130803;20130806
RHBBS=name@email.com
PAdr1=Address1
PAdr1=Address1 again
"""


invalid_edi_log_RName = """
PCall=YO5PJB
PWWLo=KN16SS
PBand=144 MHz
PSect=SOMB
TDate=20130803;20130806
RHBBS=name@email.com
PAdr1=Sesame Street, 13
RName=cucu
"""

invalid_edi_log_RName_2 = """
PCall=YO5PJB
PWWLo=KN16SS
PBand=144 MHz
PSect=SOMB
TDate=20130803;20130806
RHBBS=name@email.com
PAdr1=Sesame Street, 13
RName=John Doe
RName=John Doe's brother
"""

valid_edi_log_header = """
PCall=YO5PJB
PWWLo=KN16SS
PBand=144 MHz
PSect=SOMB
TDate=20130803;20130806
RHBBS=name@email.com
PAdr1=Sesame Street, 13
RName=John Doe
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
    ('123456789012345678', 'Qso line is too short'),
    ('130803;1319;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;', 'Incorrect Qso line format (incorrect number of fields).'),
    ('30803;1319;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', 'Qso field <date> has an invalid value (30803)'),
    ('130803;319;YO5BTZ;;59;001;59;001;;KN16SS;1;;;;', 'Qso field <hour> has an invalid value (319)'),
    ('130803;1319;YO5BTZ;6;9;001;59;001;;KN16SS;1;;;;', 'Qso field <rst sent> has an invalid value (9)'),
    #('130803;1319;YO5BTZ;6;59;1;59;001;;KN16SS;1;;;;', 'Qso field <rst send nr> has an invalid value (1)'), # accept 1 digit rst
    ('130803;1319;YO5BTZ;6;59;00001;59;001;;KN16SS;1;;;;', 'Qso field <rst send nr> has an invalid value (00001)'),
    ('130803;1319;YO5BTZ;6;59;001;9;001;;KN16SS;1;;;;', 'Qso field <rst received> has an invalid value (9)'),
    ('130803;1319;YO5BTZ;6;59;001;59;00002;;KN16SS;1;;;;', 'Qso field <rst received nr> has an invalid value (00002)'),
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
    edi.Log.qsos_tuple(linenr=54, qso='130804;0657;YO8SSB;2;599;015;599;035;;KN27OD;133;;;;', valid=True,
                       errors=[]),
]

test_logQso_regexp_qso_validator = [
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59;001;59;001;;0016SS;1;;;;', valid=False,
                       errors=[(5, '130803;1319;YO5BTZ;6;59;001;59;001;;0016SS;1;;;;',
                                'Qso field <wwl> has an invalid value (0016SS)')]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59;001;59;001;;KN1600;1;;;;', valid=False,
                       errors=[(5, '130803;1319;YO5BTZ;6;59;001;59;001;;KN1600;1;;;;',
                                'Qso field <wwl> has an invalid value (KN1600)')]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59;001;59;001;;KNAASS;1;;;;', valid=False,
                       errors=[(5, '130803;1319;YO5BTZ;6;59;001;59;001;;KNAASS;1;;;;',
                                'Qso field <wwl> has an invalid value (KNAASS)')]),
]

test_logQso_generic_qso_validator = [
    edi.Log.qsos_tuple(linenr=1, qso='999999;1319;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(1, '999999;1319;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;',
                                'Qso date is invalid: unconverted data remains: 99')]),
    edi.Log.qsos_tuple(linenr=2, qso='130803;9999;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(2, '130803;9999;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;',
                                'Qso hour is invalid: unconverted data remains: 99')]),
    edi.Log.qsos_tuple(linenr=3, qso='130803;1319;YO5BTZ/P/P;6;59;001;59;001;;KN16SS;1;;;;;', valid=False,
                       errors=[(3, '130803;1319;YO5BTZ/P/P;6;59;001;59;001;;KN16SS;1;;;;;',
                                'Callsign is invalid: YO5BTZ/P/P')]),
    edi.Log.qsos_tuple(linenr=4, qso='130803;1319;YO5BTZ;A;59;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(4, '130803;1319;YO5BTZ;A;59;001;59;001;;KN16SS;1;;;;',
                                'Qso mode is invalid: A')]),

    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;09;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(5, '130803;1319;YO5BTZ;6;09;001;59;001;;KN16SS;1;;;;', 'Rst is invalid: 09')]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59A;001;59;001;;KN16SS;1;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59;001;59A;001;;KN16SS;1;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59S;001;59;001;;KN16SS;1;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59;001;59S;001;;KN16SS;1;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;69;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(5, '130803;1319;YO5BTZ;6;69;001;59;001;;KN16SS;1;;;;', 'Rst is invalid: 69')]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;50;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(5, '130803;1319;YO5BTZ;6;50;001;59;001;;KN16SS;1;;;;', 'Rst is invalid: 50')]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59Z;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(5, '130803;1319;YO5BTZ;6;59Z;001;59;001;;KN16SS;1;;;;', 'Rst is invalid: 59Z')]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;69A;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(5, '130803;1319;YO5BTZ;6;69A;001;59;001;;KN16SS;1;;;;', 'Rst is invalid: 69A')]),

    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59;001;09;001;;KN16SS;1;;;;', valid=False,
                       errors=[(5, '130803;1319;YO5BTZ;6;59;001;09;001;;KN16SS;1;;;;', 'Rst is invalid: 09')]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59;001;69;001;;KN16SS;1;;;;', valid=False,
                       errors=[(5, '130803;1319;YO5BTZ;6;59;001;69;001;;KN16SS;1;;;;', 'Rst is invalid: 69')]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59;001;50;001;;KN16SS;1;;;;', valid=False,
                       errors=[(5, '130803;1319;YO5BTZ;6;59;001;50;001;;KN16SS;1;;;;', 'Rst is invalid: 50')]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59;001;59Z;001;;KN16SS;1;;;;', valid=False,
                       errors=[(5, '130803;1319;YO5BTZ;6;59;001;59Z;001;;KN16SS;1;;;;', 'Rst is invalid: 59Z')]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1319;YO5BTZ;6;59;001;69A;001;;KN16SS;1;;;;', valid=False,
                       errors=[(5, '130803;1319;YO5BTZ;6;59;001;69A;001;;KN16SS;1;;;;', 'Rst is invalid: 69A')]),

    edi.Log.qsos_tuple(linenr=6, qso='130803;1319;YO5BTZ;6;59;001;59;001;1234567;KN16SS;1;;;;', valid=False,
                       errors=[(6, '130803;1319;YO5BTZ;6;59;001;59;001;1234567;KN16SS;1;;;;',
                                'Received exchange is invalid: 1234567')]),
    edi.Log.qsos_tuple(linenr=7, qso='130803;1319;YO5BTZ;6;59;001;59;001;;ZZ27HM;1;;;;', valid=False,
                       errors=[(7, '130803;1319;YO5BTZ;6;59;001;59;001;;ZZ27HM;1;;;;', 'Qso WWL is invalid: ZZ27HM')]),
    edi.Log.qsos_tuple(linenr=7, qso='130803;1319;YO5BTZ;6;59;001;59;001;;KN27ZZ;1;;;;', valid=False,
                       errors=[(7, '130803;1319;YO5BTZ;6;59;001;59;001;;KN27ZZ;1;;;;', 'Qso WWL is invalid: KN27ZZ')]),
]

test_logQso_rules_based_qso_validator = [
    edi.Log.qsos_tuple(linenr=1, qso='130802;1200;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(1, '130802;1200;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;',
                                'Qso date is invalid: before contest starts (<130803)'),
                               (1, '130802;1200;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;',
                                'Qso date/hour is invalid: not inside contest periods')]),
    edi.Log.qsos_tuple(linenr=1, qso='130807;1200;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(1, '130807;1200;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;',
                                'Qso date is invalid: after contest ends (>130806)'),
                               (1, '130807;1200;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;',
                                'Qso date/hour is invalid: not inside contest periods')]),
    edi.Log.qsos_tuple(linenr=2, qso='130803;1159;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(2, '130803;1159;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;',
                                'Qso hour is invalid: before contest start hour (<1200)'),
                               (2, '130803;1159;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;',
                                'Qso date/hour is invalid: not inside contest periods')]),
    edi.Log.qsos_tuple(linenr=3, qso='130803;1200;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=4, qso='130803;1759;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=5, qso='130803;1800;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(5, '130803;1800;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;',
                                'Qso date/hour is invalid: not inside contest periods')]),
    edi.Log.qsos_tuple(linenr=6, qso='130804;0559;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(6, '130804;0559;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;',
                                'Qso date/hour is invalid: not inside contest periods')]),
    edi.Log.qsos_tuple(linenr=7, qso='130804;0600;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=8, qso='130805;1200;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=9, qso='130806;1159;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=True,
                       errors=[]),
    edi.Log.qsos_tuple(linenr=10, qso='130806;1200;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(10, '130806;1200;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;',
                                'Qso hour is invalid: after contest end hour (>1159)'),
                               (10, '130806;1200;YO5BTZ;6;59;001;59;001;;KN16SS;1;;;;',
                                'Qso date/hour is invalid: not inside contest periods')]),

    edi.Log.qsos_tuple(linenr=11, qso='130803;1200;YO5BTZ;7;59;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(11, '130803;1200;YO5BTZ;7;59;001;59;001;;KN16SS;1;;;;',
                                'Qso mode is invalid: not in defined modes (1,2,6)')]),

    edi.Log.qsos_tuple(linenr=12, qso='130803;1200;LZ1NY;6;59;001;59;001;;KN16SS;1;;;;', valid=False,
                       errors=[(12,
                                '130803;1200;LZ1NY;6;59;001;59;001;;KN16SS;1;;;;',
                                'Qso callsign is not accepted based on \'callregexp\' from rules files')]),
]


class TestEdiLog(TestCase):
    def test_init(self):

        # test with a log with no-lines
        invalid_edi_log = ''
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [(None, 'Log is empty')], ERR_HEADER: [], ERR_QSO: []})

        # test with missing PCall
        invalid_edi_log = [x for x in valid_edi_log.split('\n') if not x.startswith('PCall=')]
        invalid_edi_log = '\n'.join(invalid_edi_log)
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [], ERR_HEADER: [(None, 'PCall field is not present')], ERR_QSO: []})

        # test with multiple PCall
        invalid_edi_log = 'PCall=test\n' + valid_edi_log
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [], ERR_HEADER: [(4, 'PCall field is present multiple times')], ERR_QSO: []})

        # test with invalid PCall
        invalid_edi_log = [x for x in valid_edi_log.split('\n') if not x.startswith('PCall=')]
        invalid_edi_log = 'PCall=test\n' + '\n'.join(invalid_edi_log)
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [], ERR_HEADER: [(1, 'PCall field content is not valid')], ERR_QSO: []})

        # test with missing PWWLo
        invalid_edi_log = [x for x in valid_edi_log.split('\n') if not x.startswith('PWWLo=')]
        invalid_edi_log = '\n'.join(invalid_edi_log)
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [], ERR_HEADER: [(None, 'PWWLo field is not present')], ERR_QSO: []})

        # test with invalid PWWLo
        invalid_edi_log = 'PWWLo=test\n' + invalid_edi_log
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [], ERR_HEADER: [(1, 'PWWLo field value is not valid')], ERR_QSO: []})

        # test with multiple PWWLo
        invalid_edi_log = 'PWWLo=test\n' + valid_edi_log
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [], ERR_HEADER: [(5, 'PWWLo field is present multiple times')], ERR_QSO: []})

        # test with missing PBand
        invalid_edi_log = [x for x in valid_edi_log.split('\n') if not x.startswith('PBand=')]
        invalid_edi_log = '\n'.join(invalid_edi_log)
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [], ERR_HEADER: [(None, 'PBand field is not present')], ERR_QSO: []})

        # test with invalid PBand
        invalid_edi_log = 'PBand=test\n' + invalid_edi_log
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [], ERR_HEADER: [(1, 'PBand field value is not valid')], ERR_QSO: []})

        # test with multiple PBand
        invalid_edi_log = 'PBand=test\n' + valid_edi_log
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [], ERR_HEADER: [(10, 'PBand field is present multiple times')], ERR_QSO: []})

        # test with missing PSect
        invalid_edi_log = [x for x in valid_edi_log.split('\n') if not x.startswith('PSect=')]
        invalid_edi_log = '\n'.join(invalid_edi_log)
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [], ERR_HEADER: [(None, 'PSect field is not present')], ERR_QSO: []})

        # test with invalid PSect
        invalid_edi_log = 'PSect=test\n' + invalid_edi_log
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [], ERR_HEADER: [(1, 'PSect field value is not valid (test)')], ERR_QSO: []})

        # test with multiple PSect
        invalid_edi_log = 'PSect=test\n' + valid_edi_log
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [], ERR_HEADER: [(9, 'PSect field is present multiple times')], ERR_QSO: []})

        # test with missing TDate
        invalid_edi_log = [x for x in valid_edi_log.split('\n') if not x.startswith('TDate=')]
        invalid_edi_log = '\n'.join(invalid_edi_log)
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [], ERR_HEADER: [(None, 'TDate field is not present')], ERR_QSO: []})

        # test with invalid TDate
        invalid_edi_log2 = 'TDate=20170101,20170102\n' + invalid_edi_log
        mo = mock.mock_open(read_data=invalid_edi_log2)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [], ERR_HEADER: [(1, 'TDate field value is not valid (20170101,20170102)')],
                                  ERR_QSO: []})

        invalid_edi_log2 = 'TDate=20170101;201701020\n' + invalid_edi_log
        mo = mock.mock_open(read_data=invalid_edi_log2)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [],
                                  ERR_HEADER: [(1, 'TDate field value is not valid (20170101;201701020)')],
                                  ERR_QSO: []})

        # test with multiple TDate
        invalid_edi_log2 = 'TDate=test\n' + valid_edi_log
        mo = mock.mock_open(read_data=invalid_edi_log2)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [],
                                  ERR_HEADER: [(3, 'TDate field is present multiple times')],
                                  ERR_QSO: []})

        # test with valid header and invalid QSO
        invalid_edi_log = valid_edi_log + '\n999999;0657;YO8SSB;6;59;015;59;035;;KN27OD;133;;;;'
        mo = mock.mock_open(read_data=invalid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertTrue(log.valid_header)
            self.assertFalse(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [],
                                  ERR_HEADER: [],
                                  ERR_QSO: [(55,
                                             '999999;0657;YO8SSB;6;59;015;59;035;;KN27OD;133;;;;',
                                             'Qso date is invalid: unconverted data remains: 99')]})

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

        # test with valid rules and with invalid edi log (not accepted PCall by 'callregexp')
        mo_log = mock.mock_open(read_data=invalid_edi_log_PCall)
        with patch('builtins.open', mo_log, create=True):
            log = edi.Log('some_log_file.edi', rules=_rules)
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [], ERR_HEADER: [(2, "PCall field content doesn't match 'callregexp' value from rules")], ERR_QSO: []})

        # test with valid rules and with invalid edi log (invalid PBand)
        mo_log = mock.mock_open(read_data=invalid_edi_log_PBand)
        with patch('builtins.open', mo_log, create=True):
            log = edi.Log('some_log_file.edi', rules=_rules)
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [],
                                  ERR_HEADER: [(4, 'PBand field value has an invalid value (200 MHz). '
                                                   'Not as defined in contest rules'),
                                               (None, 'PSect field is not present'),
                                               (None, 'TDate field is not present'),
                                               (None, 'RHBBS field is not present'),
                                               (None, 'PAdr1 field is not present'),
                                               (None, 'RName field is not present')],
                                  ERR_QSO: []})

        # test with valid rules and with invalid edi log (invalid PSect)
        mo_log = mock.mock_open(read_data=invalid_edi_log_PSect)
        with patch('builtins.open', mo_log, create=True):
            log = edi.Log('some_log_file.edi', rules=_rules)
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [],
                                  ERR_HEADER: [(5, 'PSect field value has an invalid value (extraterrestrial). '
                                                   'Not as defined in contest rules'),
                                               (None, 'TDate field is not present'),
                                               (None, 'RHBBS field is not present'),
                                               (None, 'PAdr1 field is not present'),
                                               (None, 'RName field is not present')],
                                  ERR_QSO: []})

        # test with valid rules and with invalid edi log (invalid TDate)
        mo_log = mock.mock_open(read_data=invalid_edi_log_TDate)
        with patch('builtins.open', mo_log, create=True):
            log = edi.Log('some_log_file.edi', rules=_rules)
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {ERR_IO: [],
                                  ERR_HEADER: [(6, 'TDate field value has an invalid value (20250101;20250102). '
                                                   'Not as defined in contest rules'),
                                               (None, 'RHBBS field is not present'),
                                               (None, 'PAdr1 field is not present'),
                                               (None, 'RName field is not present')],
                                  ERR_QSO: []})

        # test with valid rules and with invalid edi log (invalid RHBBS)
        mo_log = mock.mock_open(read_data=invalid_edi_log_RHBBS)
        with patch('builtins.open', mo_log, create=True):
            log = edi.Log('some_log_file.edi', rules=_rules)
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {'header': [(7, 'RHBBS field value is not valid (invalid email address)'),
                                             (None, 'PAdr1 field is not present'),
                                             (None, 'RName field is not present')],
                                  'io': [],
                                  'qso': []})

        # test with valid rules and with duplicate RHBBS
        mo_log = mock.mock_open(read_data=invalid_edi_log_RHBBS_2)
        with patch('builtins.open', mo_log, create=True):
            log = edi.Log('some_log_file.edi', rules=_rules)
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {'header': [(8, 'RHBBS is present multiple times'),
                                             (None, 'PAdr1 field is not present'),
                                             (None, 'RName field is not present')],
                                  'io': [],
                                  'qso': []})

        # test with valid rules and with invalid edi log (invalid PAdr1)
        mo_log = mock.mock_open(read_data=invalid_edi_log_PAdr1)
        with patch('builtins.open', mo_log, create=True):
            log = edi.Log('some_log_file.edi', rules=_rules)
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {'header': [(8, 'PAdr1 field is too short (None)'),
                                             (None, 'RName field is not present')],
                                  'io': [],
                                  'qso': []})

        # test with valid rules and with duplicate address
        mo_log = mock.mock_open(read_data=invalid_edi_log_PAdr1_2)
        with patch('builtins.open', mo_log, create=True):
            log = edi.Log('some_log_file.edi', rules=_rules)
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {'header': [(9, 'PAdr1 is present multiple times'),
                                             (None, 'RName field is not present')],
                                  'io': [],
                                  'qso': []})

        # test with valid rules and with invalid edi log (invalid RName)
        mo_log = mock.mock_open(read_data=invalid_edi_log_RName)
        with patch('builtins.open', mo_log, create=True):
            log = edi.Log('some_log_file.edi', rules=_rules)
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {'header': [(9, 'RName field is too short (cucu)')],
                                  'io': [],
                                  'qso': []})

        # test with valid rules and with duplicate name
        mo_log = mock.mock_open(read_data=invalid_edi_log_RName_2)
        with patch('builtins.open', mo_log, create=True):
            log = edi.Log('some_log_file.edi', rules=_rules)
            self.assertFalse(log.valid_header)
            self.assertIsNone(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {'header': [(10, 'RName is present multiple times')],
                                  'io': [],
                                  'qso': []})

        # test with valid rules and valid header
        mo_log = mock.mock_open(read_data=valid_edi_log_header)
        with patch('builtins.open', mo_log, create=True):
            log = edi.Log('some_log_file.edi', rules=_rules)
            self.assertTrue(log.valid_header)
            self.assertTrue(log.valid_qsos)
            self.assertDictEqual(log.errors,
                                 {'header': [],
                                  'io': [],
                                  'qso': []})

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
                             {ERR_IO: [(None, 'Cannot read edi log. Error: [Errno 2] No such file or directory: '
                                              "'non-existing-log-file.edi'")], ERR_HEADER: [], ERR_QSO: []})

    @mock.patch.object(edi.Log, 'read_file_content')
    def test_get_field(self, mock_read_file_content):
        mock_read_file_content.return_value = valid_edi_log.split('\n')
        log = edi.Log('some_log_file.edi')
        self.assertTupleEqual((['YO5PJB'], 3), log.get_field('PCall'))
        self.assertTupleEqual((['YO5PJB'], 3), log.get_field('pcall'))

    @mock.patch.object(edi.Log, 'read_file_content')
    def test_get_qsos(self, mock_read_file_content):
        self.maxDiff = None
        mock_read_file_content.return_value = valid_edi_log.split('\n')
        mock_read_file_content.return_value.append('[END; SomeToolSignature]')
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
            self.assertEqual(_ln1, _ln2)
            self.assertEqual(_qso1, _qso2)
            self.assertEqual(_valid1, _valid2)
            self.assertEqual(_error1, _error2)
        # self.assertEqual(test_logQso_qsos, log.qsos)

    def test_validate_callsign(self):
        positive_tests = ['yo5pjb', 'YO5PJB', 'YO5pjb', 'K4X', 'A22A', 'I20000X', '4X4AAA', '3DA0RS',
                          'yo5pjb/p', 'yo5pjb/m', 'yo5pjb/am', 'yo5pjb/mm']
        negative_tests = [None, '', 'yo%pjb', 'yoSpjb']

        for test in positive_tests:
            self.assertTrue(edi.Log.validate_callsign(test))
        for test in negative_tests:
            self.assertFalse(edi.Log.validate_callsign(test))

    def test_validate_email(self):
        positive_tests = ['yo5pjb@mail.com']
        negative_tests = [None, '', 'yo5pjb.mail.com', 'yo5pjb', '@mail.com']
        for test in positive_tests:
            self.assertTrue(edi.Log.validate_email(test))
        for test in negative_tests:
            self.assertFalse(edi.Log.validate_email(test))

    def test_validate_address(self):
        positive_tests = ['Sesame Street', 'SesameStreet,13', 'SesameStreetNo.13']
        negative_tests = [None, '', 'short', 'SesameStreet']
        for test in positive_tests:
            self.assertTrue(edi.Log.validate_address(test))
        for test in negative_tests:
            self.assertFalse(edi.Log.validate_address(test))

    def test_validate_qth_locator(self):
        positive_tests = ['KN16SS', 'kn16ss', 'AA00AA', 'RR00XX']
        negative_tests = [None, '', '0016SS', 'KNXXSS', 'KN1600', 'KN16SS00', '00KN16SS']

        for test in positive_tests:
            self.assertTrue(edi.Log.validate_qth_locator(test))
        for test in negative_tests:
            self.assertFalse(edi.Log.validate_qth_locator(test))

    def test_get_band(self):
        positive_tests_144 = ['144', '145', '144mhz', '145mhz']
        negative_tests_144 = [None, '', ' 144', ' 145', '143', '146']
        positive_tests_432 = ['430', '432', '435', '430mhz', '432mhz', '432.200', '435mhz']
        negative_tests_432 = [None, '', '431', '433', '434']

        for test in positive_tests_144:
            self.assertEqual('144', edi.Log.get_band(test))

        for test in negative_tests_144:
            self.assertIsNone(edi.Log.get_band(test))

        for test in positive_tests_432:
            self.assertEqual('432', edi.Log.get_band(test))

        for test in negative_tests_432:
            self.assertIsNone(edi.Log.get_band(test))

    def test_validate_band(self):
        positive_tests = ['144', '145', '144mhz', '145mhz', '430', '432', '435', '430mhz', '432mhz', '432.2',
                          '435hz', '1296', '1296mhz', '1.2g', '1.3g']
        negative_tests = [None, '', '143', '146', '431', '433', '1200']
        for test in positive_tests:
            self.assertTrue(edi.Log.validate_band(test))
        for test in negative_tests:
            self.assertFalse(edi.Log.validate_band(test))

    @mock.patch('os.path.isfile')
    def test_rules_based_validate_band(self, mock_isfile):
        mock_isfile.return_value = True
        positive_tests = ['144', '145', '144mhz', '145mhz', '430', '432', '430mhz', '432mhz', '432.2']
        negative_tests = [None, '', '143', '146', '431', '433', '435']

        mo = mock.mock_open(read_data=VALID_RULES)
        with patch('builtins.open', mo, create=True):
            _rules = rules.Rules('some_rule_file.rules')
        for test in positive_tests:
            self.assertTrue(edi.Log.rules_based_validate_band(test, _rules))
        for test in negative_tests:
            self.assertFalse(edi.Log.rules_based_validate_band(test, _rules))
        self.assertRaisesRegex(ValueError, 'No contest rules provided !', edi.Log.rules_based_validate_band, positive_tests[0], None)

    def test_validate_category(self):
        positive_tests = {
            'single': ['so', 'sosb', 'somb', 'single', 'single op', 'single-op'],
            'multi': ['mo', 'mosb', 'momb', 'multi', 'multi op', 'multi-op'],
            'checklog': ['check', 'check-log', 'checklog', 'CHECklog']
        }
        negative_tests = [None, '', 'operator', 'band']
        for _category, test_list in positive_tests.items():
            for test in test_list:
                self.assertTupleEqual(edi.Log.validate_category(test), (True, _category))
        for test in negative_tests:
            self.assertTupleEqual(edi.Log.validate_category(test), (False, None))

    @mock.patch('os.path.isfile')
    def test_rules_based_validate_category(self, mock_isfile):
        mock_isfile.return_value = True
        positive_tests = {
            'Single Operator 144': ['so', 'sosb', 'somb', 'single', 'single op', 'single-op', 'single-operator', 'single operator'],
            'Multi Operator': ['mo', 'mosb', 'momb', 'multi', 'multi op', 'multi-op', 'multi-operator' 'multi operator'],
        }
        negative_tests = [None, '', 'operator', 'band']
        mo = mock.mock_open(read_data=VALID_RULES)
        with patch('builtins.open', mo, create=True):
            _rules = rules.Rules('some_rule_file.rules')
        for _category, test_list in positive_tests.items():
            for test in test_list:
                self.assertTupleEqual(edi.Log.rules_based_validate_category(test, _rules), (True, _category))
        for test in negative_tests:
            self.assertTupleEqual(edi.Log.rules_based_validate_category(test, _rules), (False, None))
        self.assertRaisesRegex(ValueError, 'No contest rules provided !', edi.Log.rules_based_validate_category, 'none', None)


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


class TestEdiOperator(TestCase):
    def test_init(self):
        op = edi.Operator('yo5pjb')
        self.assertEqual(op.callsign, 'yo5pjb')
        self.assertEqual(op.logs, [])

    def test_add_log(self):
        op = edi.Operator('yo5pjb')
        mo = mock.mock_open(read_data=valid_edi_log)
        with patch('builtins.open', mo, create=True):
            op.add_log_by_path('some_log_file.edi')
            self.assertEqual(len(op.logs), 1)
            op.add_log_by_path('some_log_file.edi')
            self.assertEqual(len(op.logs), 2)
            self.assertIsInstance(op.logs[0], edi.Log)
            self.assertIsInstance(op.logs[1], edi.Log)

    def test_add_log_instance(self):
        op = edi.Operator('yo5pjb')
        log = edi.Log('some_log_file.edi')

        self.assertEqual(op.logs, [])
        op.add_log_instance(log)
        self.assertEqual(op.logs, [log])

    def test_logs_by_band_regexp(self):
        op = edi.Operator('yo5pjb')
        log1 = edi.Log('log1.edi')
        log1.band = '144 Mhz'
        log1.valid_header = True
        log2 = edi.Log('log2.edi')
        log2.band = '432 MHz'
        log2.valid_header = True
        log3 = edi.Log('log3.edi')
        log3.band = '2m'
        log3.valid_header = True
        log4 = edi.Log('log4_invalid.edi')
        log4.band = '2m'

        op.add_log_instance(log1)
        op.add_log_instance(log2)
        op.add_log_instance(log3)
        op.add_log_instance(log4)

        self.assertListEqual(op.logs_by_band_regexp('144|145|2m'), [log1, log3])


class TestEdiHelperFunctions(TestCase):
    def test_dict_to_json(self):
        input = {'1': '2',
                 'Hello': 'World!'}
        output = '{"1": "2", "Hello": "World!"}'
        self.assertEqual(edi.dict_to_json(input), output)

    def test_dict_to_xml(self):
        input = {'1': '2',
                 'Hello': 'World!'}
        output = b'<?xml version="1.0" encoding="UTF-8" ?><root><n1 type="str">2</n1><Hello type="str">World!</Hello></root>'
        self.assertEqual(edi.dict_to_xml(input), output)

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
            edi.LogQso('130803;1800;YO5AAA;6;59;001;59;001;;KN16AA;1;;;;', 1, _rules),
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
            # qso with long serial (29)
            edi.LogQso('130803;1200;YO5AAA;6;59;0001;59;001;;KN16AA;1;;;;', 1, _rules),
            # qso with lowercase qthlocator (30)
            edi.LogQso('130803;1200;YO5AAA;6;59;0001;59;001;;KN16aa;1;;;;', 1, _rules),
        ]

        qso_test = (
            # test different date
            (qso_list[0], qso_list[1], None, ValueError, 'Other ham qso is invalid'),
            (qso_list[0], qso_list[2], None, ValueError, 'Other ham qso is invalid'),
            (qso_list[0], qso_list[3], None, ValueError, 'Other ham qso is invalid'),
            (qso_list[0], qso_list[4], None, ValueError, 'Other ham qso is invalid'),
            (qso_list[0], qso_list[5], None, ValueError, 'Other ham qso is invalid'),
            (qso_list[0], qso_list[6], None, ValueError, 'Other ham qso is invalid'),
            # reverse test of different date
            (qso_list[1], qso_list[0], None, ValueError, 'Qso date is invalid: before contest starts \(<130803\)'),
            (qso_list[2], qso_list[0], None, ValueError, 'Qso date is invalid: after contest ends \(>130806\)'),
            (qso_list[3], qso_list[0], None, ValueError, 'Qso date is invalid: before contest starts \(<130803\)'),
            (qso_list[4], qso_list[0], None, ValueError, 'Qso date is invalid: after contest ends \(>130806\)'),
            (qso_list[5], qso_list[0], None, ValueError, 'Qso date is invalid: before contest starts \(<130803\)'),
            (qso_list[6], qso_list[0], None, ValueError, 'Qso date/hour is invalid: not inside contest periods'),
            # test different time
            (qso_list[0], qso_list[7], None, ValueError, 'Other ham qso is invalid'),
            (qso_list[0], qso_list[8], None, ValueError, 'Other ham qso is invalid'),
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
            (qso_list[0], qso_list[12], None, ValueError, 'Callsign mismatch'),
            (qso_list[0], qso_list[13], None, ValueError, 'Other ham qso is invalid'),
            (qso_list[0], qso_list[14], None, ValueError, 'Callsign mismatch'),
            (qso_list[0], qso_list[15], None, ValueError, 'Other ham qso is invalid'),
            (qso_list[0], qso_list[16], None, ValueError, 'Callsign mismatch'),
            # reverse test of different callsign
            (qso_list[12], qso_list[0], None, ValueError, 'Callsign mismatch'),
            (qso_list[13], qso_list[0], None, ValueError, 'Callsign is invalid: YO5AAA-P'),
            (qso_list[14], qso_list[0], None, ValueError, 'Callsign mismatch'),
            (qso_list[15], qso_list[0], None, ValueError, 'Callsign is invalid: YO5AAA-M'),
            (qso_list[16], qso_list[0], None, ValueError, 'Callsign mismatch'),
            # test different modes
            (qso_list[0], qso_list[17], None, ValueError, 'Mode mismatch'),
            (qso_list[0], qso_list[18], None, ValueError, 'Other ham qso is invalid'),
            # reverse test of different modes
            (qso_list[17], qso_list[0], None, ValueError, 'Mode mismatch'),
            (qso_list[18], qso_list[0], None, ValueError, 'Qso mode is invalid: not in defined modes \(1,2,6\)'),
            # test different rst & serial
            (qso_list[0], qso_list[19], None, ValueError, 'Rst mismatch'),
            (qso_list[0], qso_list[20], None, ValueError, 'Serial number mismatch'),
            (qso_list[0], qso_list[21], None, ValueError, 'Rst mismatch \(other ham\)'),
            (qso_list[0], qso_list[22], None, ValueError, 'Serial number mismatch \(other ham\)'),
            # reverse test of differe rst & serial
            (qso_list[19], qso_list[0], None, ValueError, 'Rst mismatch \(other ham\)'),
            (qso_list[20], qso_list[0], None, ValueError, 'Serial number mismatch \(other ham\)'),
            (qso_list[21], qso_list[0], None, ValueError, 'Rst mismatch'),
            (qso_list[22], qso_list[0], None, ValueError, 'Serial number mismatch'),
            # test invalid rst & serial
            (qso_list[0], qso_list[23], None, ValueError, 'Other ham qso is invalid'),
            (qso_list[0], qso_list[24], None, ValueError, 'Other ham qso is invalid'),
            (qso_list[0], qso_list[25], None, ValueError, 'Other ham qso is invalid'),
            (qso_list[0], qso_list[26], None, ValueError, 'Other ham qso is invalid'),
            # reverse test of invalid rst & serial
            (qso_list[23], qso_list[0], None, ValueError, 'Rst is invalid: 00'),
            (qso_list[24], qso_list[0], None, ValueError, 'Rst is invalid: 00'),
            (qso_list[25], qso_list[0], None, ValueError, 'Qso field <rst send nr> has an invalid value \(00001\)'),
            (qso_list[26], qso_list[0], None, ValueError, 'Qso field <rst received nr> has an invalid value \(00001\)'),
            # test different qth
            (qso_list[0], qso_list[27], None, ValueError, 'Qth locator mismatch \(other ham\)'),
            (qso_list[27], qso_list[0], None, ValueError, 'Qth locator mismatch'),
            # test invalid qth
            (qso_list[0], qso_list[28], None, ValueError, 'Other ham qso is invalid'),
            (qso_list[28], qso_list[0], None, ValueError, 'Qso WWL is invalid: ZZ16ZZ'),
            # valid test with long serial
            (qso_list[0], qso_list[29], 1, None, None),
            (qso_list[29], qso_list[0], 1, None, None),
            # valid test with lowercase qthlocator
            (qso_list[0], qso_list[30], 1, None, None),
            (qso_list[30], qso_list[0], 1, None, None),

        )

        for q1, q2, distance, ex, ex_msg in qso_test:
            if distance:
                self.assertEqual(edi.compare_qso(_log, q1, _log, q2), distance)
            if ex:
                self.assertRaisesRegex(ex, '^'+ex_msg+'$', edi.compare_qso, _log, q1, _log, q2)

    @mock.patch('os.path.isfile')
    def test_crosscheck_logs(self, mck_isfile):
        """
        A test with hardcoded logs.
        It's hard to follow and understand this test and
        I assume that I've covered most of the important cases from 'crosscheck_logs'
        and in case something is changing this test should catch it
        """
        mck_isfile.return_value = True
        expected_result = ['True-[]-1',  # yo5aaa -> yo5bbb
                           'True-[]-1',  # yo5aaa -> yo5ccc
                           'True-[]-1',  # yo5bbb -> yo5aaa
                           'False-No qso found on YO5CCC log-None',                    # yo5bbb -> yo5ccc (yo5ccc : no qso with yo5bbb)
                           'False-Qso field <date> has an invalid value (1308)-None',  # yo5bbb -> yo5ddd (invalid date)
                           'False-No log from YO5EEE-None',                            # yo5bbb -> yo5eee (no log from yo5eee)
                           'False-No log for this band from YO5FFF-None',              # yo5bbb -> yo5fff (no log in 144mhz from yo5fff)
                           'False-No qso found on YO5AAA log-None', # yo5ccc -> yo5aaa (no qso match)
                           'True-[]-1',                             # yo5ccc -> yo5aaa
                           'False-Qso already confirmed-None',      # yo5ccc -> yo5aaa (duplicate into yo5ccc log)
                           'None-[]-None']                          # yo5fff -> yo5zzz (no log for 144mhz)

        mo_rules = mock.mock_open(read_data=VALID_RULES_BASIC)
        with patch('builtins.open', mo_rules, create=True):
            _rules = rules.Rules('some_rule_file.rules')

        log1_content = \
"""TName=Cupa Nasaud
TDate=20130803;20130806
PCall=YO5aaa
PWWLo=KN16ss
PSect=SOSB
PBand=144 MHz
[QSORecords;1]
130803;1200;YO5BBB;6;59;001;59;001;;KN16SS;1;;;;
130803;1201;YO5CCC;6;59;002;59;001;;KN16SS;1;;;;
"""
        op1 = edi.Operator('YO5AAA')  # fair player
        mo = mock.mock_open(read_data=log1_content)
        with patch('builtins.open', mo, create=True):
            op1.add_log_by_path('some_log_file.edi', rules=_rules)
            self.assertEqual(len(op1.logs), 1)

        log2_content = \
"""TName=Cupa Nasaud
TDate=20130803;20130806
PCall=YO5BBB
PWWLo=kn16ss
PSect=SOSB
PBand=144 MHz
[QSORecords;1]
130803;1200;YO5AAA;6;59;001;59;001;;kn16ss;1;;;;
130803;1201;YO5ccc;6;59;002;59;002;;KN16SS;1;;;;
1308;1202;YO5DDD;6;59;003;59;001;;KN16SS;1;;;;
130803;1203;yo5eee;6;59;004;59;001;;KN16SS;1;;;;
130803;1204;YO5FFF;6;59;005;59;001;;kn16ss;1;;;;
"""
        op2 = edi.Operator('YO5BBB')  # fair player with mistakes
        mo = mock.mock_open(read_data=log2_content)
        with patch('builtins.open', mo, create=True):
            op2.add_log_by_path('some_log_file.edi', rules=_rules)
            self.assertEqual(len(op2.logs), 1)

        log3_content = \
"""TName=Cupa Nasaud
TDate=20130803;20130806
PCall=yo5ccc
PWWLo=KN16SS
PSect=SOSB
PBand=144 MHz
[QSORecords;1]
130803;1200;YO5AAA;2;59;111;59;112;;KN16SS;2;;;;
130803;1200;YO5AAA;6;59;001;59;002;;KN16SS;2;;;;
130803;1200;YO5AAA;6;59;001;59;002;;KN16SS;3;;;;
"""
        op3 = edi.Operator('YO5CCC')  # unfair player
        mo = mock.mock_open(read_data=log3_content)
        with patch('builtins.open', mo, create=True):
            op3.add_log_by_path('some_log_file.edi', rules=_rules)
            self.assertEqual(len(op3.logs), 1)

        op4 = edi.Operator('YO5DDD')  # op without logs

        log5_content = \
"""TName=Cupa Nasaud
TDate=20130803;20130806
PCall=YO5FFF
PWWLo=KN16SS
PSect=SOSB
PBand=432 MHz
[QSORecords;1]
130803;1200;yo5zzz;6;59;001;59;001;;KN16SS;1;;;;
"""
        op5 = edi.Operator('YO5FFF')  # op with log on another band
        mo = mock.mock_open(read_data=log5_content)
        with patch('builtins.open', mo, create=True):
            op5.add_log_by_path('some_log_file.edi', rules=_rules)
            self.assertEqual(len(op5.logs), 1)

        op_inst = {
            'YO5AAA': op1,
            'YO5BBB': op2,
            'YO5CCC': op3,
            'YO5DDD': op4,
            'YO5FFF': op5,
        }

        edi.crosscheck_logs(op_inst, _rules, 1)

        result = []
        print("NIMIC")
        for op, op_inst in op_inst.items():
            for log in op_inst.logs:
                for qso in log.qsos:
                    result.append("{}-{}-{}".format(qso.cc_confirmed, qso.cc_error, qso.points))
        self.assertListEqual(result, expected_result)


    @mock.patch('os.path.isfile')
    def test_crosscheck_logs_custom_1(self, mck_isfile):
        """
        A test based on logs from CN 2022, when a bug in cross-check was found.
        The problem was with a duplicate form the 1st operator
        """
        mck_isfile.return_value = True
        expected_result = [
            'False-No qso found on YO4FYQ log-None',
            'True-[]-599',
            'True-[]-599',
            'True-[]-599',
            'True-[]-599']

        custom_rules = \
r"""
[contest]
name=CN2022
begindate=20220820
enddate=20220820
beginhour=1200
endhour=1759
bands=1
periods=2
categories=1
modes=1,2
[log]
format=edi
[band1]
band=144
regexp=144|145|2m
multiplier=1
[period1]
begindate=20220820
enddate=20220820
beginhour=1200
endhour=1459
bands=band1
[period2]
begindate=20220820
enddate=20220820
beginhour=1500
endhour=1759
bands=band1
[category1]
name=single
regexp=A
bands=band1
"""
        mo_rules = mock.mock_open(read_data=custom_rules)
        with patch('builtins.open', mo_rules, create=True):
            _rules = rules.Rules('some_rule_file.rules')

        log1_content = \
"""TName=Campionatul Național ȋn Unde Ultrascurte VHF (144 MHz)
TDate=20220820;20220820
PCall=YO2GL
PWWLo=KN05OS
PSect=A
PBand=144 MHz
[QSORecords;57]
220820;1204;YO4FYQ;1;59;003;59;002;;KN44FD;599;;;;
220820;1326;YO4FYQ;1;59;018;59;022;;KN44FD;0;;;;
220820;1507;YO4FYQ;1;59;033;59;037;;KN44FD;0;;;;
"""
        op1 = edi.Operator('YO2GL')
        mo = mock.mock_open(read_data=log1_content)
        with patch('builtins.open', mo, create=True):
            op1.add_log_by_path('some_log_file.edi', rules=_rules)
            self.assertEqual(len(op1.logs), 1)

        log2_content = \
"""TName=CNVHF2022
TDate=20220820;20220820
PCall=YO4FYQ
PWWLo=KN44FD
PSect=A
PBand=144 MHz
[QSORecords;67]
220820;1326;YO2GL;1;59;022;59;018;;KN05OS;599;;;;
220820;1507;YO2GL;1;59;037;59;033;;KN05OS;599;;;;
"""

        op2 = edi.Operator('YO4FYQ')
        mo = mock.mock_open(read_data=log2_content)
        with patch('builtins.open', mo, create=True):
            op2.add_log_by_path('some_log_file.edi', rules=_rules)
            self.assertEqual(len(op2.logs), 1)

        op_inst = {
            'YO2GL': op1,
            'YO4FYQ': op2
        }

        edi.crosscheck_logs(op_inst, _rules, 1)

        result = []
        for op, op_inst in op_inst.items():
            for log in op_inst.logs:
                for qso in log.qsos:
                    result.append("{}-{}-{}".format(qso.cc_confirmed, qso.cc_error, qso.points))

        self.assertListEqual(result, expected_result)
