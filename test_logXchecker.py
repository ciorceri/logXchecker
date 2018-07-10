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
import logXchecker

edi_log1 = """
TName=Cupa Nasaud
TDate=20130803;20130806
PCall=YO5AAA
PWWLo=KN16AA
PSect=SOMB
PBand=144 MHz
[QSORecords;3]
130803;1205;YO5BBB;6;59;001;59;001;;KN16BB;10;;;;
130803;1215;YO5CCC;6;59;002;59;002;;KN16CC;20;;;;
130803;1225;YO5DDD;6;59;003;59;003;;KN16DD;30;;;;
"""

edi_log2 = """
TName=Cupa Nasaud
TDate=20130803;20130806
PCall=YO5BBB
PWWLo=KN16BB
PSect=SOMB
PBand=144 MHz
[QSORecords;3]
130803;1205;YO5AAA;6;59;001;59;001;;KN16AA;10;;;;
130803;1215;YO5CCC;6;59;002;59;002;;KN16CC;20;;;;
130803;1225;YO5DDD;6;59;003;59;003;;KN16DD;30;;;;
"""

edi_log3 = """
TName=Cupa Nasaud
TDate=20130803;20130806
PCall=YO5CCC
PWWLo=KN16CC
PSect=SOMB
PBand=144 MHz
[QSORecords;3]
130803;1205;YO5AAA;6;59;001;59;001;;KN16AA;10;;;;
130803;1215;YO5CCC;6;59;002;59;002;;KN16CC;20;;;;
130803;1225;YO5DDD;6;59;003;59;003;;KN16DD;30;;;;
"""


class TestHelperMethods(unittest.TestCase):
    def test_qth_distance(self):
        distance = [('KN16SS', 'KN16SS', 1),
                    ('KN16SS', 'KN16SQ', 9),
                    ('KN16SS', 'KN17SS', 111)]
        for qth1, qth2, km in distance:
            self.assertEqual(logXchecker.qth_distance(qth1, qth2), km)

    def test_compare_qso(self):
        mo = mock.mock_open(read_data=edi_log1)
        with patch('builtins.open', mo, create=True):
            log1 = edi.Log('some_log_file1.edi')

        mo = mock.mock_open(read_data=edi_log2)
        with patch('builtins.open', mo, create=True):
            log2 = edi.Log('some_log_file2.edi')

        mo = mock.mock_open(read_data=edi_log3)
        with patch('builtins.open', mo, create=True):
            log3 = edi.Log('some_log_file3.edi')

        # TODO : continue this test !!!