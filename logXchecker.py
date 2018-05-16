"""
Copyright 2016 Ciorceri Petru Sorin

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

import argparse
import importlib
import os
import sys

import edi
import version
import rules as _rules


class ArgumentParser(object):
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
        raise argparse.ArgumentTypeError('Format "{}" is an invalid value'.format(arg))

    def check_output_value(self, arg):
        """
        :param arg: specifies the output format (json, xml)
        :return: arg
        :raise: ArgumentTypeError
        """
        valid_output = ('HUMAN-FRIENDLY', 'JSON', 'XML')
        if arg.upper() in valid_output:
            return arg
        raise argparse.ArgumentTypeError('Output "{}" is an invalid value. Use: {}'.format(arg, ','.join(valid_output)))

    def __init__(self):
        self.parser = argparse.ArgumentParser(description='log cross checker')
        group1 = self.parser.add_mutually_exclusive_group(required=True)
        group1.add_argument('-f', '--format', type=self.check_format_value,
                            help="Log format: edi, adif, cabrillo")
        group1.add_argument('-r', '--rules', type=str, help='INI file with contest rules')
        group2 = self.parser.add_mutually_exclusive_group(required=True)
        group2.add_argument('-slc', '--singlelogcheck', type=str, default=False, metavar='path_to_log', help='Check a single log')
        group2.add_argument('-mlc', '--multilogcheck', type=str, default=False, metavar='path_to_folder', help='Check multiple logs')
        group2.add_argument('-cc', '--crosscheck', type=str, default=False, metavar='path_to_folder', help='Cross-check multiple logs')
        self.parser.add_argument('-cl', '--checklogs', type=str, default=False, metavar='path_to_folder', help='Checklogs used for cross-check')
        self.parser.add_argument('-o', '--output', type=self.check_output_value, required=False, default='human-friendly',
                                 help='Output format: human-friendly, json, xml (default: human-friendly)')

    def parse(self, args):
        return self.parser.parse_args(args)


class Contest(object):
    """
    This is the main contest class which will held an instance of 'Rules' class.
    It will create a list of instances of 'Operator' class
    and each 'Operator' instance will have a list of 'Log' class
    and each 'Log' instance will keep a lot of instances of 'LogQso'
    """


# class Log(edi.Log):
#     """
#     This will keep a single log information (header + list of LogQso instances)
#     """
#     path = None
#
#     def __init__(self):
#         pass
#
#     def validate_log_name(self):
#         pass
#
#     def validate_log_content(self):
#         pass
#
#     def get_summary(self):
#         """
#         Based on the output format (text, html...) this will output a summary of the log
#         """
#         pass
#
#
# class LogQso(edi.LogQso):
#     """
#     This will keep a single QSO
#     """
#     qsoFields = {}
#
#     def __init__(self):
#         pass
#
#     def qso_parser(self):
#         """
#         This should parse a qso based on log format
#         """
#         pass
#
#     def validate_qso(self):
#         """
#         This will validate a parsed qso based on generic rules (simple validation) or based on rules
#         """
#         pass


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


def print_human_friendly(output):
    """Will print a human-fiendly output for easy read"""
    # single log
    if output.get(edi.INFO_LOG, False):
        print_log_human_friendly(output)
    # multi logs
    if output.get(edi.INFO_FOLDER, False):
        print('Checking logs from folder : {}'.format(output[edi.INFO_FOLDER]))
        for log in output[edi.INFO_FOLDER_LOGS]:
            print_log_human_friendly(log)
            print('-------------')


def print_log_human_friendly(output):
    """Will print human fiendly info for a log"""
    print('Checking log : {}'.format(output[edi.INFO_LOG]))
    if output[edi.ERR_IO]:
        print('Input/Output : {}'.format(output[edi.ERR_IO]))
        pass
    if output[edi.ERR_HEADER]:
        print('Header errors :')
        for err in output[edi.ERR_HEADER]:
            print('Line {} : {}'.format(err[0], err[1]))
    if output[edi.ERR_QSO]:
        print('QSO errors :')
        for err in output[edi.ERR_QSO]:
            print('Line {} : {}'.format(err[0], err[1]))


def main():
    print('{} - v{}'.format(version.__project__,  version.__version__))
    args = ArgumentParser().parse(sys.argv[1:])

    operator = None
    log = None
    logQso = None

    rules = None
    if args.rules:
        rules = _rules.Rules(args.rules)
        log_format = rules.contest_log_format
    elif args.format:
        log_format = args.format

    if log_format == 'EDI':
        lfmodule = edi
    else:
        print('Unsupported log type selected : {}'.format(log_format))
        return 1

    operator = lfmodule.Operator
    log = lfmodule.Log
    logQso = lfmodule.LogQso

    # TODO : move upper 3 lines here based on log type
    # TODO : and use the proper log type checks

    output = {}
    # if 'validate one log'
    if args.singlelogcheck:
        output[edi.INFO_LOG] = args.singlelogcheck
        if not os.path.isfile(args.singlelogcheck):
            print('Cannot open file: {}'.format(args.singlelogcheck))
            return 1
        _log = log(args.singlelogcheck, rules=rules)
        output.update(_log.errors)
    # validate multiple logs
    elif args.multilogcheck:
        output[edi.INFO_FOLDER] = args.multilogcheck
        if not os.path.isdir(args.multilogcheck):
            print('Cannot open folder: {}'.format(args.multilogcheck))
            return 1
        logs_output = []
        for filename in os.listdir(args.multilogcheck):
            log_output = {}
            _log = log(os.path.join(args.multilogcheck, filename), rules=rules)
            log_output[edi.INFO_LOG] = filename
            log_output.update(_log.errors)
            logs_output.append(log_output)
        output[edi.INFO_FOLDER_LOGS] = logs_output
    # add also checklogs
    if args.multilogcheck and args.checklogs:
        if os.path.isdir(args.checklogs):
            logs_output = []
            for filename in os.listdir(args.checklogs):
                log_output = {}
                _log=log(os.path.join(args.checklogs, filename), rules=rules, checklog=True)
                log_output[edi.INFO_LOG] = filename
                log_output.update(_log.errors)
                logs_output.append(log_output)
            output[edi.INFO_FOLDER_LOGS].extend(logs_output)

    if args.output.upper() == 'HUMAN-FRIENDLY':
        print_human_friendly(output)
    elif args.output.upper() == 'JSON':
        print(edi.dict_to_json(output))
    elif args.output.upper() == 'XML':
        print(edi.dict_to_xml(output))

if __name__ == '__main__':
    main()
