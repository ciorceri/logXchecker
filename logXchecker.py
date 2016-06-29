import argparse


class Parser():

    def check_format_value(self, arg):
        validFormats = ('EDI', 'ADIF', 'CABRILLO')
        arg = arg.upper()
        if arg in validFormats:
            return arg
        raise argparse.ArgumentTypeError('Format "%s" is an invalid value' % arg)

    def check_output_value(self, arg):
        validOutput = ('TXT', 'TEXT', 'HTML', 'JSON', 'YML')
        arg = arg.upper()
        if arg in validOutput:
            return arg
        raise argparse.ArgumentTypeError('Output "%s" is an invalid value' % arg)

    def __init__(self):
        self.parser = argparse.ArgumentParser(description='log cross checker')
        self.parser.add_argument('-f', '--format', type=self.check_format_value, required=True, help="Log format: edi, adif, cabrillo")
        self.parser.add_argument('-r', '--rules', type=str, required=False, help='INI file with contest rules')
        self.parser.add_argument('-o', '--output', type=self.check_output_value, required=False, help='Output format: text, html, json, yml')
        group = self.parser.add_mutually_exclusive_group()
        group.add_argument('-slc', '--singlelogcheck', action='store_true', default=False)
        group.add_argument('-mlc', '--multilogcheck', action='store_true', default=False)


    def parse(self, commandLine):
        return self.parser.parse_args(commandLine)