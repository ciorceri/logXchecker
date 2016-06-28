from unittest import TestCase
from logXchecker import Parser


class TestParser(TestCase):
    testcase_with_errors = (('', 2), ('hello', 2), ('-h', 2), ('--help', 2),
                            (['-h'], 0), (['--help'], 0),
                            (['-f'], 2), (['-f edi'], 0), (['-f', 'edi'], 0),
                            (['-f=edi', '-slc'], 0),
                            (['-f=edi', '--singlelogcheck'], 0),
                            (['-f=edi', '-mlc'], 0),
                            (['-f=edi', '--multilogcheck'], 0),
                            (['-f=edi', '-slc', '-mlc'], 2),
                            )
    testcase_with_success = ((['-f=edi'], 'edi', False, False), (['-fedi'], 'edi', False, False),
                             (['-f=edi', '-slc'], 'edi', True, False),
                             (['-f=edi', '--singlelogcheck'], 'edi', True, False),
                             (['-f=edi', '-mlc'], 'edi', False, True),
                             (['-f=edi', '--multilogcheck'], 'edi', False, True),
                             )
    def setUp(self):
        self.p = Parser()

    def test_parse(self):
        for (arg,exitCode) in self.testcase_with_errors:
            try:
                print('testing parser agument:', arg)
                parsed = self.p.parse(arg)
            except SystemExit as e:
                print('error code:', e.code, '| expected error code:', exitCode)
                self.assertEqual(e.code, exitCode)

        for (arg,format,singlelogcheck,multilogcheck) in self.testcase_with_success:
            print('testing parser argument:', arg)
            result = self.p.parse(arg)
            print('result=', result)
            self.assertEqual(result.format, format)
            self.assertEqual(result.singlelogcheck, singlelogcheck)
            self.assertEqual(result.multilogcheck, multilogcheck)