import argparse
import importlib
import os
import sys

import edi
import version


class ArgumentParser():
    """
    Parses the parameters from command line
    """

    def check_format_value(self, arg):
        """
        :param arg: specifies log file format (edi, adif, cbr)
        :return: arg
        :raise: ArgumentTypeError
        """
        valid_formats = ('EDI', 'ADIF', 'CABRILLO')
        if arg.upper() in valid_formats:
            return arg.upper()
        raise argparse.ArgumentTypeError('Format "%s" is an invalid value' % arg)

    def check_output_value(self, arg):
        """
        :param arg: specifies the output format (text, html, json, yml)
        :return: arg
        :raise: ArgumentTypeError
        """
        valid_output = ('TXT', 'TEXT', 'HTML', 'JSON', 'YML')
        if arg.upper() in valid_output:
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
        group.add_argument('-slc', '--singlelogcheck', type=str, default=False, help='single log check')
        group.add_argument('-mlc', '--multilogcheck', type=str, default=False, help='multiple log check')

    def parse(self, args):
        return self.parser.parse_args(args)


class Contest(object):
    """
    This is the main contest class which will held an instance of 'Rules' class.
    It will create a list of instances of 'Operator' class
    and each 'Operator' instance will have a list of 'Log' class
    and each 'Log' instance will keep a lot of instances of 'LogQso'
    """


class Rules(object):
    """
    Will read and parse the contest rule files.
    Rule example: contest date, contest bands, contest categories.
    Rule file format : https://en.wikipedia.org/wiki/INI_file
    """
    path = None

    def __init__(self, path):
        pass

    def read_rules(self, path):
        """
        :param path: path to ini rule file
        :return: ???
        """
        pass

    def validate_rules(self):
        """
        :return: ???
        """
        pass

    def _validate_log_name(self):
        """
        Based on ...
        :return:
        """
        pass

    def _validate_log_xyz(self):
        pass


class Operator(edi.Operator):
    """
    This will keep the info & logs for each ham operator (team)
    """
    callsign = None
    info = {}
    logs = []

    def __init__(self):
        pass


class Log(edi.Log):
    """
    This will keep a single log information (header + list of LogQso instances)
    """
    path = None

    def __init__(self):
        pass

    def validate_log_name(self):
        pass

    def validate_log_content(self):
        pass

    def get_summary(self):
        """
        Based on the output format (text, html...) this will output a summary of the log
        """
        pass


class LogQso(edi.LogQso):
    """
    This will keep a single QSO
    """
    qsoFields = {}

    def __init__(self):
        pass

    def qso_parser(self):
        """
        This should parse a qso based on log format
        """
        pass

    def validate_qso(self):
        """
        This will validate a parsed qso based on generic rules (simple validation) or based on rules
        """
        pass


# This function is not used at this moment since I have support only for 'edi format'
def load_log_format_module(module_name):
    """
    :param module_name: path to module who knows to parse & read a specified file format (edi, adif, cbr)
    :return:
    """
    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        print("ERROR:", e)
        sys.exit(1)
    return module

    # class Module(module):
    #     def __init__(self):
    #         pass
    #
    #     def validate_rules(self):
    #         pass


def main():
    print(version.__project__,  version.__version__)
    args = ArgumentParser().parse(sys.argv[1:])
    if args.format:
        # lfmodule = load_log_format_module(args.format)
        lfmodule = edi

    # if 'validate one log'
    if args.slc:
        print('Validate log: ', args.slc)
        if not os.path.isfile(args.slc):
            raise FileNotFoundError(args.slc)

    elif args.mlc:
        print('Validate folder: ', args.mlc)
        if not os.path.isdir(args.mlc):
            raise FileNotFoundError(args.mlc)

if __name__ == '__main__':
    main()
