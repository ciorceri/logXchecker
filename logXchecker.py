import sys
import argparse
import importlib


class ArgumentParser():

    def check_format_value(self, arg):
        valid_formats = ('EDI', 'ADIF', 'CABRILLO')
        arg = arg.upper()
        if arg in valid_formats:
            return arg
        raise argparse.ArgumentTypeError('Format "%s" is an invalid value' % arg)

    def check_output_value(self, arg):
        valid_output = ('TXT', 'TEXT', 'HTML', 'JSON', 'YML')
        arg = arg.upper()
        if arg in valid_output:
            return arg
        raise argparse.ArgumentTypeError('Output "%s" is an invalid value' % arg)

    def __init__(self):
        self.parser = argparse.ArgumentParser(description='log cross checker')
        self.parser.add_argument('-f', '--format', type=self.check_format_value, required=True,
                                 help="Log format: edi, adif, cabrillo")
        self.parser.add_argument('-r', '--rules', type=str, required=False, help='INI file with contest rules')
        self.parser.add_argument('-o', '--output', type=self.check_output_value, required=False,
                                 help='Output format: text, html, json, yml')
        group = self.parser.add_mutually_exclusive_group()
        group.add_argument('-slc', '--singlelogcheck', action='store_true', default=False)
        group.add_argument('-mlc', '--multilogcheck', action='store_true', default=False)

    def parse(self, args):
        return self.parser.parse_args(args)


class Rules(object):
    path = None

    def __init__(self, path):
        pass

    def read_rules(self, path):
        pass

    def validate_rules(self):
        pass


class Log(object):
    path = None

    def __init__(self):
        pass

    def validate_log_name(self):
        pass

    def validate_log_content(self):
        pass

    def get_summary(self):
        pass


class LogQso(object):
    qsoFields = {}

    def __init__(self):
        pass

    def qso_parser(self):
        pass

    def validate_qso(self):
        pass


def load_module(module_name):
    module = importlib.import_module(module_name)

    class Module(module):
        def __init__(self):
            pass

        def validate_rules(self):
            pass
    return Module

def main():
    args = ArgumentParser.parse(sys.args)
    if args.format:
        module = load_module(args.format)

if __name__ == '__main__':
    main()

