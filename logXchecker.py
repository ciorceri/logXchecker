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

import os
import re
import sys
import math
import argparse
import importlib
from datetime import datetime, timedelta

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
        self.parser.add_argument('-cl', '--checklogs', type=str, default=None, metavar='path_to_folder', help='Checklogs used for cross-check')
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
    module = importlib.import_module(module_name)
    return module

    # class Module(module):
    #     def __init__(self):
    #         pass
    #
    #     def validate_rules(self):
    #         pass


def print_human_friendly_output(output):
    """Will print a human-fiendly output for easy read"""
    # single log
    if output.get(edi.INFO_LOG, False):
        print_log_human_friendly(output)
    # multi logs
    if output.get(edi.INFO_MLC, False):
        print('Checking logs from folder : {}'.format(output[edi.INFO_MLC]))
        for log in output[edi.INFO_MLC]:
            print_log_human_friendly(log)
            print('--------')
    # cross check
    if output.get(edi.INFO_CC, False):
        print('Cross check logs from folder : {}'.format(output[edi.INFO_CC]))
        for _call, _values in output[edi.INFO_OPERATORS].items():
            print('Callsign : {}'.format(_call))
            for _band, _details in _values['band'].items():
                print('   Band {} : valid={} , category={} , points={}'.format(_band, _details['valid'], _details['category'], _details['points']))
            print('--------')


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


# TODO : move this to edi.log
def crosscheck_logs_filter(log_class, rules=None, logs_folder=None, checklogs_folder=None):

    ignored_logs = []

    # create instances for all logs
    logs_instances = []
    if not logs_folder:
        print('Logs folder was not provided')
        return 1
    if logs_folder and not os.path.isdir(logs_folder):
        print('Cannot open logs folder : {}'.format(logs_folder))
        return 1
    for filename in os.listdir(logs_folder):
        logs_instances.append(log_class(os.path.join(logs_folder, filename), rules=rules))

    if checklogs_folder:
        if os.path.isdir(checklogs_folder):
            for filename in os.listdir(checklogs_folder):
                logs_instances.append(log_class(os.path.join(checklogs_folder, filename), rules=rules, checklog=True))
        else:
            print('Cannot open checklogs folder : {}'.format(checklogs_folder))

    # create instances for all hams and add logs with valid header
    operator_instances = {}
    for log in logs_instances:
        if not log.valid_header:
            log.ignore_this_log = True
            ignored_logs.append(log)
            continue
        callsign = log.callsign.upper()
        if not operator_instances.get(callsign, None):
            operator_instances[callsign] = edi.Operator(callsign)
        operator_instances[callsign].add_log_instance(log)

    # TODO check for duplicate logs (on same band)
    # select one log from duplicate logs
    # set Log.ignore_this_log field to True for duplicate logs

    # TODO check if a ham has logs with different categories
    # but ignore

    for band in range(1, rules.contest_bands_nr+1):
        crosscheck_logs(operator_instances, rules, band)

    # calculate points in every logs
    for op, op_inst in operator_instances.items():
        for log in op_inst.logs:
            points = 0
            for qso in log.qsos:
                if qso.points and qso.points > 0:
                    points += qso.points
            log.qsos_points = points

    return operator_instances


# TODO : move this to edi.log
def crosscheck_logs(operator_instances, rules, band_nr):
    """
    :param operator_instances: dictionary {key=callsign, value=edi.Operator(callsign)}
    :param band_nr: number of contest band
    :return: TODO
    """
    for callsign1, ham1 in operator_instances.items():
        # print('CHECK LOGS OF : ', callsign1, ham1.callsign)

        # get logs for band
        _logs1 = ham1.logs_by_band_regexp(rules.contest_band(band_nr)['regexp'])
        # print('  LOG PATH : ', [x.path for x in _logs1])

        if not _logs1:
            continue
        log1 = _logs1[0]  # use 1st log # TODO : for multi-period contests I have to use all logs !
        if log1.use_as_checklog is True:
            continue
        if log1.ignore_this_log is True:
            continue

        for qso1 in log1.qsos:
            # print('    LOG QSO : ', qso1.qso_line, qso1.qso_fields['call'])
            if qso1.valid is False:
                continue
            if qso1.confirmed is True:
                continue

            # TODO : ignore duplicate qso

            # check if we have some logs from 2nd ham
            callsign2 = qso1.qso_fields['call']
            ham2 = operator_instances.get(callsign2, None)
            if not ham2:
                qso1.confirmed = False
                continue

            # check if we have proper band logs from 2nd ham
            _logs2 = ham2.logs_by_band_regexp(rules.contest_band(band_nr)['regexp'])
            # print('      HAM2 LOGS : ', [x.path for x in _logs2])
            if not _logs2:
                qso1.confirmed = False
                continue
            log2 = _logs2[0]  # use 1st log # TODO : for multi-period contests I have to use all logs !

            # get 2nd ham qsos and compare them with 1st ham qso
            for qso2 in log2.qsos:
                if qso2.valid is False:
                    continue

                # TODO : ignore duplicate qso

                _callsign = qso2.qso_fields['call']
                if callsign1 != _callsign:
                    continue
                try:
                    distance = compare_qso(log1, qso1, log2, qso2)
                except ValueError as e:
                    qso1.errors.append(e)

                # print('      *** COMPARAM : {} vs {} SI {} cu {} = {}'.format(callsign1, callsign2, qso1.qso_line, qso2.qso_line, distance))
                if distance < 0:
                    continue
                qso1.points = distance * int(rules.contest_band(band_nr)['multiplier'])
                qso1.confirmed = True


# TODO : move this to edi.log
def compare_qso(log1, qso1, log2, qso2):
    """
    Generic comparision of 2 QSO's
    :param qso1:
    :param qso2:
    :return: distance if QSO's are valid or -1/None
    """

    if qso1.valid is False:
        # TODO : think if I should pass only the 1st error or all errors to ValueError
        raise ValueError(qso1.errors[0][1])

    # compare callsign
    if log1.callsign != qso2.qso_fields['call'] or log2.callsign != qso1.qso_fields['call']:
        return -1

    # calculate absolute date+time
    REGEX_DATE = '(?P<year>\d{2})(?P<month>\d{2})(?P<day>\d{2})'
    REGEX_HOUR = '(?P<hour>\d{2})(?P<minute>\d{2})'

    date_res1 = re.match(REGEX_DATE, qso1.qso_fields['date'])
    if not date_res1:
        raise ValueError('Date format is invalid : {}'.format(qso1.qso_fields['date']))
    hour_res1 = re.match(REGEX_HOUR, qso1.qso_fields['hour'])
    if not hour_res1:
        raise ValueError('Hour format is invalid : {}'.format(qso1.qso_fields['hour']))
    absolute_time1 = datetime(int(date_res1.group('year')), int(date_res1.group('month')), int(date_res1.group('day')),
                              int(hour_res1.group('hour')), int(hour_res1.group('minute')))

    date_res2 = re.match(REGEX_DATE, qso2.qso_fields['date'])
    if not date_res2:
        raise ValueError('Date format is invalid : {}'.format(qso2.qso_fields['date']))
    hour_res2 = re.match(REGEX_HOUR, qso2.qso_fields['hour'])
    if not hour_res2:
        raise ValueError('Hour format is invalid : {}'.format(qso2.qso_fields['hour']))
    absolute_time2 = datetime(int(date_res2.group('year')), int(date_res2.group('month')), int(date_res2.group('day')),
                              int(hour_res2.group('hour')), int(hour_res2.group('minute')))

    # check if time1 and time2 difference is less than 5 minutes
    if abs(absolute_time1 - absolute_time2) > timedelta(minutes=5):
        raise ValueError('Different date/time between qso\'s')

    # compare mode
    if qso1.qso_fields['mode'] != qso2.qso_fields['mode']:
        raise ValueError('Mode mismatch')
    # compare rst
    if (qso1.qso_fields['rst_sent'] != qso2.qso_fields['rst_recv'] or \
        qso1.qso_fields['rst_recv'] != qso2.qso_fields['rst_sent']):
        raise ValueError('Rst mismatch')
    if (qso1.qso_fields['nr_sent'] != qso2.qso_fields['nr_recv'] or \
        qso1.qso_fields['nr_recv'] != qso2.qso_fields['nr_sent']):
        raise ValueError('Serial number mismatch')

    # compare qth
    if (log1.maidenhead_locator != qso2.qso_fields['wwl'] or \
        log2.maidenhead_locator != qso1.qso_fields['wwl']):
        raise ValueError('Qth locator mismatch')

    # calculate & return distance
    return qth_distance(log1.maidenhead_locator, log2.maidenhead_locator)


# TODO : move this to edi.log
def delta_ord(letter):
    """
    This will return an character number in alphabet and same for numbers.
    The order number starts from 0.
    Ex: for input '5' will return '5'-'0' = 5
        for input 'C' will return 'C'-'A' = 3
    """
    if (letter>='0') & (letter<='9'):
        return ord(letter)-ord('0')
    if (letter>='A') & (letter<='Z'):
        return ord(letter)-ord('A')
    return -1


# TODO : move this to edi.log
def conv_maidenhead_to_latlong(maiden):
    """
    Will convert he Maidenhead location to Latitude/Longitude location
    """
    long = -180.0 + 20 * delta_ord(maiden[0]) + 2.0 * delta_ord(maiden[2]) + 5.0 * delta_ord(maiden[4]) / 60.0
    lat = -90.0 + 10 * delta_ord(maiden[1]) + 1.0 * delta_ord(maiden[3]) + 2.5 * delta_ord(maiden[5]) / 60.0
    return long, lat


# TODO : move this to edi.log
def qth_distance(qth1, qth2):
    """
    Math to calculate the distance (in kilometers) between 2 Maindehead locators
    see : https://en.wikipedia.org/wiki/Maidenhead_Locator_System
    """
    if qth1 == qth2:
        return 1

    # Convert Maidenhead to latitude and longitude
    long1, lat1 = conv_maidenhead_to_latlong(qth1)
    long2, lat2 = conv_maidenhead_to_latlong(qth2)

    # Convert latitude and longitude to
    # spherical coordinates in radians.
    degrees_to_radians = math.pi/180.0

    # phi = 90 - latitude
    phi1 = (90.0 - lat1)*degrees_to_radians
    phi2 = (90.0 - lat2)*degrees_to_radians

    # theta = longitude
    theta1 = long1*degrees_to_radians
    theta2 = long2*degrees_to_radians

    # Compute spherical distance from spherical coordinates.

    # For two locations in spherical coordinates
    # (1, theta, phi) and (1, theta, phi)
    # cosine( arc length ) =
    #    sin phi sin phi' cos(theta-theta') + cos phi cos phi'
    # distance = rho * arc length

    cos = (math.sin(phi1)*math.sin(phi2)*math.cos(theta1 - theta2) + math.cos(phi1)*math.cos(phi2))
    arc = math.acos( cos )

    # Remember to multiply arc by the radius of the earth
    # in your favorite set of units to get length.
    if 0.0 == round(arc*6373):
        return 1
    else:
        return int(round(arc*6373))
        #return arc*6373


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
        output[edi.INFO_MLC] = logs_output
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
                output[edi.INFO_MLC].extend(logs_output)

    elif args.crosscheck:
        output[edi.INFO_CC] = args.crosscheck
        output[edi.INFO_OPERATORS] = {}
        op_instance = crosscheck_logs_filter(log, rules=rules, logs_folder=args.crosscheck, checklogs_folder=args.checklogs)
        for _call, _instance in op_instance.items():
            op_output = {}
            op_output[edi.INFO_BANDS] = {}
            for _log in _instance.logs:
                op_output[edi.INFO_BANDS][_log.band] = {
                    'points': _log.qsos_points,
                    'valid': _log.valid_header,
                    'category': _log.category,
                }
            output[edi.INFO_OPERATORS][_call] = op_output

    if args.output.upper() == 'HUMAN-FRIENDLY':
        print_human_friendly_output(output)
    elif args.output.upper() == 'JSON':
        print(edi.dict_to_json(output))
    elif args.output.upper() == 'XML':
        print(edi.dict_to_xml(output))

if __name__ == '__main__':
    main()
