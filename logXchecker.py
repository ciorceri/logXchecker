"""
Copyright 2016-2018 Ciorceri Petru Sorin (yo5pjb)

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
import rules as _rules
import version
from edi import crosscheck_logs_filter

# SORT_OUTPUT = False  # TODO : sort the results output


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
        self.parser.add_argument('-cl', '--checklogs', type=str, default=None, metavar='path_to_folder', help='Checklogs used for cross-check')
        self.parser.add_argument('-o', '--output', type=self.check_output_value, required=False, default='human-friendly',
                                 help='Output format: human-friendly, json, xml (default: human-friendly)')
        self.parser.add_argument('-v', '--verbose', action='store_true', help='More details for cross-check')

    def parse(self, args):
        return self.parser.parse_args(args)


# TODO : This function is not used at this moment since I have support only for 'edi format'
def load_log_format_module(module_name):
    """
    :param module_name: path to module who knows to parse & read a specified file format (edi, adif, cbr)
    :return:
    """
    module = importlib.import_module(module_name)
    return module

    # class Module(module):
    #     def __init__(self):
    #         pass
    #
    #     def validate_rules(self):
    #         pass


def print_human_friendly_output(output, verbose=False):
    """Will print a human-fiendly output for easy read"""
    # single log
    if output.get(edi.INFO_LOG, False):
        print_log_human_friendly(output)
    # multi logs
    if output.get(edi.INFO_MLC, False):
        print('Checking logs from folder : {}'.format(output[edi.INFO_MLC]))
        print('#########################')
        # print('Checking logs from folder : {}'.format(output[edi.INFO_MLC]))
        for log in output[edi.INFO_LOGS]:
            print_log_human_friendly(log)
            print('--------')
    # cross check
    if output.get(edi.INFO_CC, False):
        print('Cross check logs from folder : {}'.format(output[edi.INFO_CC]))
        print('#########################')
        for _call, _values in output[edi.INFO_OPERATORS].items():
            print('Callsign : {}'.format(_call))
            for _band, _details in _values['band'].items():
                if _details.get('checklog', False) is True:
                    print('   [checklog] band={} , valid={}'.format(_band, _details['valid']))
                else:
                    print('   band={} , valid={} , category={} , points={} , qsos_confirmed={}'.format(_band, _details['valid'], _details['category'], _details['points'], _details['qsos_confirmed']))
                if not verbose:
                    continue
                for err in _details['qso_errors']:
                    print('   - {}'.format(err))
            print('--------')


def print_log_human_friendly(output):
    """Will print human fiendly info for a log"""
    has_errors = False
    print('Checking log : {}'.format(output[edi.INFO_LOG]))
    if output[edi.ERR_IO]:
        print('Input/Output : {}'.format(output[edi.ERR_IO]))
        has_errors = True
        pass
    if output[edi.ERR_HEADER]:
        print('Header errors :')
        for err in output[edi.ERR_HEADER]:
            print('Line {} : {}'.format(err[0], err[1]))
        has_errors = True
    if output[edi.ERR_QSO]:
        print('QSO errors :')
        for err in output[edi.ERR_QSO]:
            print('Line {} : {} <- {}'.format(err[0], err[1], err[2]))
        has_errors = True

    if has_errors is False:
        print('No error found')

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
        print('Selected log type is unsupported : {}'.format(log_format))
        return 1

    operator = lfmodule.Operator
    log = lfmodule.Log
    logQso = lfmodule.LogQso

    output = {}

    # if 'validate one log'
    if args.singlelogcheck:
        output[edi.INFO_LOG] = args.singlelogcheck
        if not os.path.isfile(args.singlelogcheck):
            print('Cannot open file : {}'.format(args.singlelogcheck))
            return 1
        _log = log(args.singlelogcheck, rules=rules)
        output.update(_log.errors)

    # validate multiple logs
    elif args.multilogcheck:
        output[edi.INFO_MLC] = args.multilogcheck
        if not os.path.isdir(args.multilogcheck):
            print('Cannot open logs folder : {}'.format(args.multilogcheck))
            return 1
        logs_output = []
        for filename in os.listdir(args.multilogcheck):
            log_output = {}
            _log = log(os.path.join(args.multilogcheck, filename), rules=rules)
            log_output[edi.INFO_LOG] = filename
            log_output.update(_log.errors)
            logs_output.append(log_output)
        output[edi.INFO_LOGS] = logs_output
        # add also checklogs
        if args.checklogs:
            if os.path.isdir(args.checklogs):
                logs_output = []
                for filename in os.listdir(args.checklogs):
                    log_output = {}
                    _log = log(os.path.join(args.checklogs, filename), rules=rules, checklog=True)
                    log_output[edi.INFO_LOG] = filename
                    log_output.update(_log.errors)
                    logs_output.append(log_output)
                output[edi.INFO_LOGS].extend(logs_output)

    # crosscheck logs
    elif args.crosscheck:
        output[edi.INFO_CC] = args.crosscheck
        output[edi.INFO_OPERATORS] = {}
        op_instance = crosscheck_logs_filter(log, rules=rules, logs_folder=args.crosscheck, checklogs_folder=args.checklogs)
        for _call, _instance in op_instance.items():
            op_output = {}
            op_output[edi.INFO_BANDS] = {}
            for _log in _instance.logs:
                op_output[edi.INFO_BANDS][_log.band] = {
                    'path': _log.path,
                    'points': _log.qsos_points,
                    'qsos_confirmed': _log.qsos_confirmed,
                    'valid': _log.valid_header,
                    'category': _log.category,
                    'checklog': _log.use_as_checklog,
                }
                if args.verbose is True:
                    _cc_errors = []
                    for qso in _log.qsos:
                        if qso.cc_confirmed is False:
                            _cc_errors.append('{} : {}'.format(qso.qso_line, qso.cc_error))
                    op_output[edi.INFO_BANDS][_log.band]['qso_errors'] = _cc_errors

            output[edi.INFO_OPERATORS][_call] = op_output

    if args.output.upper() == 'HUMAN-FRIENDLY':
        print_human_friendly_output(output, verbose=args.verbose)
    elif args.output.upper() == 'JSON':
        print(edi.dict_to_json(output))
    elif args.output.upper() == 'XML':
        print(edi.dict_to_xml(output))

if __name__ == '__main__':
    main()
