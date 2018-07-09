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

import logXchecker


class TestHelperMethods(unittest.TestCase):
    def test_qth_distance(self):
        distance = [('KN16SS', 'KN16SS', 1),
                    ('KN16SS', 'KN16SQ', 9),
                    ('KN16SS', 'KN17SS', 111)]
        for qth1, qth2, km in distance:
            self.assertEqual(logXchecker.qth_distance(qth1, qth2), km)
