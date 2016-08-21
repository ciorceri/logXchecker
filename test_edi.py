from unittest import TestCase
from unittest.mock import mock_open, patch

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
130804;0657;YO8SSB;6;59;015;59;035;;KN27OD;133;;;;

"""


class TestEdi(TestCase):
    def test_read_file_content(self):
        # test 'read_file_content', the buildins.open is mocked
        mo = mock_open(read_data=valid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
        self.assertEqual(valid_edi_log, ''.join(log.log_content))

        # test 'read_file_content' exceptions
        self.assertRaises(FileNotFoundError, edi.Log, 'non-existing-log-file.edi')

    def test_get_field(self):
        mo = mock_open(read_data=valid_edi_log)
        with patch('builtins.open', mo, create=True):
            log = edi.Log('some_log_file.edi')
            self.assertEqual('YO5PJB', log.get_field('PCall')[0])
            self.assertEqual('YO5PJB', log.get_field('pcall')[0])
            self.assertNotEqual('yo5pjb', log.get_field('pcall')[0])
            self.assertNotEqual('INVALID_CALLSIGN', log.get_field('PCall')[0])
