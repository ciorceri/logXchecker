from unittest import TestCase
from logXchecker import ArgumentParser


class TestParser(TestCase):
    testcase_with_error_checks = (('', 2), ('hello', 2), ('-h', 2), ('--help', 2),
                                  (['-h'], 0), (['--help'], 0),
                                  (['-f=edi'], 0), (['-fedi'], 0), (['-f', 'edi'], 0),
                                  (['-f=adif'], 0), (['-fadif'], 0), (['-f', 'adif'], 0),
                                  (['-f=cabrillo'], 0), (['-fcabrillo'], 0), (['-f', 'cabrillo'], 0),
                                  (['-f'], 2), (['-f edi'], 2), (['-f hello'], 2),
                                  (['-f=edi', '-o=text'], 0), (['-f=edi', '-otext'], 0),
                                  (['-f=edi', '-o'], 2),
                                  (['-f=edi', '-o=hello'], 2), (['-f=edi', '-ohello'], 2),
                                  (['-f=edi', '-o', 'hello'], 2),
                                  (['-f=edi', '-slc'], 0),
                                  (['-f=edi', '--singlelogcheck'], 0),
                                  (['-f=edi', '-mlc'], 0),
                                  (['-f=edi', '--multilogcheck'], 0),
                                  (['-f=edi', '-slc', '-mlc'], 2),
                                  )
    testcase_with_success = ((['-f=edi'], 'EDI', False, False), (['-fedi'], 'EDI', False, False),
                             (['-f=edi', '-slc'], 'EDI', True, False),
                             (['-f=edi', '--singlelogcheck'], 'EDI', True, False),
                             (['-f=edi', '-mlc'], 'EDI', False, True),
                             (['-f=edi', '--multilogcheck'], 'EDI', False, True),
                             )

    def setUp(self):
        self.p = ArgumentParser()

    def test_parse(self):
        for (arg, exitCode) in self.testcase_with_error_checks:
            try:
                print('testing parser agument:', arg)
                parsed = self.p.parse(arg)
            except SystemExit as e:
                print('error code:', e.code, '| expected error code:', exitCode)
                self.assertEqual(e.code, exitCode)
            else:  # only tests with expected exitCode = 0 should get here
                if exitCode != 0:
                    raise ValueError('Should exit with exit code 0, but it didn\'t')

        for (arg, format, singlelogcheck, multilogcheck) in self.testcase_with_success:
            print('testing parser argument:', arg)
            result = self.p.parse(arg)
            self.assertEqual(result.format, format)
            self.assertEqual(result.singlelogcheck, singlelogcheck)
            self.assertEqual(result.multilogcheck, multilogcheck)
