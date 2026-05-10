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

import argparse
import importlib
import os
import sys

import rules as _rules
import version

# Import shared constants (no hard dependency on any optional format module)
from constants import (
    INFO_LOG, INFO_MLC, INFO_LOGS, INFO_CC, INFO_OPERATORS, INFO_BANDS,
    ERR_IO, ERR_HEADER, ERR_QSO,
    FORMAT_MODULE_MAP,
)

# Import output formatters from the output package.
from output import print_human_friendly_output, print_log_human_friendly, print_csv_output

# SORT_OUTPUT = False  # TODO : sort the results output


class ArgumentParser(object):
    """
    Parses the parameters from command line
    """

    @staticmethod
    def check_format_value(arg):
        """
        :param arg: specifies log file format (edi, adif, cbr)
        :return: arg
        :raise: ArgumentTypeError
        """
        valid_formats = tuple(FORMAT_MODULE_MAP.keys())
        if arg.upper() in valid_formats:
            return arg.upper()
        raise argparse.ArgumentTypeError(
            'Format "{}" is an invalid value. Supported: {}'.format(arg, ', '.join(valid_formats))
        )

    @staticmethod
    def check_output_value(arg):
        """
        :param arg: specifies the output format (json, xml, csv)
        :return: arg
        :raise: ArgumentTypeError
        """
        valid_output = ('HUMAN-FRIENDLY', 'JSON', 'XML', 'CSV')
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
                                 help='Output format: human-friendly, json, xml, csv (default: human-friendly)')
        self.parser.add_argument('-v', '--verbose', action='store_true', help='More details for cross-check')

    def parse(self, args):
        return self.parser.parse_args(args)


def load_log_format_module(module_name):
    """
    Lazy-load a log format module by name.
    :param module_name: Python module name (e.g., 'formats.edi', 'adif', 'cabrillo')
    :return: the loaded module
    :raises ImportError: if the module cannot be found
    """
    return importlib.import_module(module_name)


def _get_log_format_module(log_format):
    """
    Resolve a user-facing format name ('EDI', 'ADIF', etc.) to the matching
    Python module that can parse and validate that log format.

    :param log_format: uppercase format string (e.g. 'EDI')
    :return: loaded module
    :raises ValueError: if the format is not yet supported
    :raises ImportError: if the format module is not installed
    """
    module_name = FORMAT_MODULE_MAP.get(log_format)
    if not module_name:
        raise ValueError('Selected log type is unsupported: {}'.format(log_format))
    try:
        return load_log_format_module(module_name)
    except ImportError:
        raise ImportError(
            'Module for format "{}" ({}) is not available. '
            'Make sure the required package is installed.'.format(log_format, module_name)
        )


def main():
    args = ArgumentParser().parse(sys.argv[1:])
    if args.output.upper() == 'HUMAN-FRIENDLY':
        print('{} - v{}'.format(version.__project__, version.__version__))

    rules = None
    if args.rules:
        rules = _rules.Rules(args.rules)
        log_format = rules.contest_log_format
    elif args.format:
        log_format = args.format
    else:
        # Should not happen due to mutually exclusive group in argparse
        print('No format or rules specified')
        sys.exit(1)

    try:
        lfmodule = _get_log_format_module(log_format)
    except (ValueError, ImportError) as e:
        print(e)
        sys.exit(1)

    log = lfmodule.Log

    output = {}

    # validate one log
    if args.singlelogcheck:
        output[INFO_LOG] = args.singlelogcheck
        if not os.path.isfile(args.singlelogcheck):
            print('Cannot open file : {}'.format(args.singlelogcheck))
            sys.exit(1)
        _log = log(args.singlelogcheck, rules=rules)
        output.update(_log.errors)

    # validate multiple logs
    elif args.multilogcheck:
        output[INFO_MLC] = args.multilogcheck
        if not os.path.isdir(args.multilogcheck):
            print('Cannot open logs folder : {}'.format(args.multilogcheck))
            sys.exit(1)
        logs_output = []
        for filename in os.listdir(args.multilogcheck):
            log_output = {}
            _log = log(os.path.join(args.multilogcheck, filename), rules=rules)
            log_output[INFO_LOG] = filename
            log_output.update(_log.errors)
            logs_output.append(log_output)
        output[INFO_LOGS] = logs_output
        # add also checklogs
        if args.checklogs:
            if os.path.isdir(args.checklogs):
                logs_output = []
                for filename in os.listdir(args.checklogs):
                    log_output = {}
                    _log = log(os.path.join(args.checklogs, filename), rules=rules, checklog=True)
                    log_output[INFO_LOG] = filename
                    log_output.update(_log.errors)
                    logs_output.append(log_output)
                output[INFO_LOGS].extend(logs_output)

    # crosscheck logs
    elif args.crosscheck:
        if not rules:
            print("No rules were provided")
            sys.exit(1)
        output[INFO_CC] = args.crosscheck
        output[INFO_OPERATORS] = {}
        op_instance = lfmodule.crosscheck_logs_filter(
            log, rules=rules, logs_folder=args.crosscheck, checklogs_folder=args.checklogs
        )
        for _call, _instance in op_instance.items():
            op_output = {}
            op_output[INFO_BANDS] = {}
            for _log in _instance.logs:
                op_output[INFO_BANDS][_log.band] = {
                    'path': _log.path,
                    'points': _log.qsos_points,
                    'qsos_confirmed': _log.qsos_confirmed,
                    'valid': _log.valid_header,
                    'category': _log.category,
                    'checklog': _log.use_as_checklog,
                }
                if args.verbose is True:
                    _cc_errors = []
                    _cc_valid = []
                    for qso in _log.qsos:
                        if qso.cc_confirmed is False:
                            _cc_errors.append('{} : {}'.format(qso.qso_line, qso.cc_error))
                        else:
                            _cc_valid.append('{} : {} : {}'.format(qso.qso_line, qso.points, qso.cc_confirmed))
                    op_output[INFO_BANDS][_log.band]['qso_errors'] = _cc_errors
                    op_output[INFO_BANDS][_log.band]['qso_valid'] = _cc_valid

            output[INFO_OPERATORS][_call] = op_output

    if args.output.upper() == 'HUMAN-FRIENDLY':
        print_human_friendly_output(output, verbose=args.verbose)
    elif args.output.upper() == 'JSON':
        print(lfmodule.dict_to_json(output))
    elif args.output.upper() == 'XML':
        print(lfmodule.dict_to_xml(output))
    elif args.output.upper() == 'CSV':
        print_csv_output(output)


if __name__ == '__main__':
    main()
