"""
Copyright 2016-2022 Ciorceri Petru Sorin (yo5pjb)

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
from logXchecker import ArgumentParser


class TestParser(TestCase):
    testcase_with_error_checks = (('', 2), ('hello', 2), ('-h', 2), ('--help', 2),
                                  (['-h'], 0), (['--help'], 0),
                                  (['-f=edi'], 2), (['-fedi'], 2), (['-f', 'edi'], 2),
                                  (['-f=adif'], 2), (['-fadif'], 2), (['-f', 'adif'], 2),
                                  (['-f=cabrillo'], 2), (['-fcabrillo'], 2), (['-f', 'cabrillo'], 2),
                                  (['-f'], 2), (['-f edi'], 2), (['-f hello'], 2),
                                  (['-f=edi', '-o=text'], 2), (['-f=edi', '-otext'], 2),
                                  (['-f=edi', '-o'], 2),
                                  (['-f=edi', '-o=hello'], 2), (['-f=edi', '-ohello'], 2),
                                  (['-f=edi', '-o', 'hello'], 2),
                                  (['-f=edi', '-slc=xxx.edi'], 0),
                                  (['-f=edi', '-slc', 'xxx.edi'], 0),
                                  (['-f=edi', '--singlelogcheck=xxx.edi'], 0),
                                  (['-f=edi', '--singlelogcheck', 'xxx.edi'], 0),
                                  (['-f=edi', '-mlc=xxx'], 0),
                                  (['-f=edi', '--multilogcheck=xxx'], 0),
                                  (['-f=edi', '-slc', '-mlc'], 2),
                                  )
    testcase_with_success = (
                             (['-f=edi', '-slc=xxx.edi'], 'EDI', 'xxx.edi', False),
                             (['-fedi', '-slc=xxx.edi'], 'EDI', 'xxx.edi', False),
                             (['-f=edi', '-slc=xxx.edi'], 'EDI', 'xxx.edi', False),
                             (['-f=edi', '--singlelogcheck=xxx.edi'], 'EDI', 'xxx.edi', False),
                             (['-f=edi', '-mlc=xxx.edi'], 'EDI', False, 'xxx.edi'),
                             (['-f=edi', '--multilogcheck=xxx.edi'], 'EDI', False, 'xxx.edi'),
                             )

    def setUp(self):
        self.p = ArgumentParser()

    def test_parse(self):
        for (arg, exitCode) in self.testcase_with_error_checks:
            try:
                parsed = self.p.parse(arg)
            except SystemExit as e:
                self.assertEqual(e.code, exitCode,
                                 f"Parser should exit with code {exitCode} for args {arg}, got {e.code}")
            else:  # only tests with expected exitCode = 0 should get here
                if exitCode != 0:
                    raise ValueError(f"Parser should have exited for args {arg} with code {exitCode}")

        for (arg, format, singlelogcheck, multilogcheck) in self.testcase_with_success:
            result = self.p.parse(arg)
            self.assertEqual(result.format.upper(), format.upper(),
                             f"Parsed format should match expected {format} for args {arg}")
            self.assertEqual(result.singlelogcheck, singlelogcheck,
                             f"Parsed singlelogcheck should match expected {singlelogcheck} for args {arg}")
            self.assertEqual(result.multilogcheck, multilogcheck,
                             f"Parsed multilogcheck should match expected {multilogcheck} for args {arg}")
