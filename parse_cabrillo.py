"""
Copyright 2016-2024 Ciorceri Petru Sorin (yo5pjb)

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
from cabrillo.parser import parse_log_file
from cabrillo.errors import InvalidLogException, InvalidQSOException
from validate_email import validate_email

INFO_MLC = 'multi_logs_folder'
INFO_CC = 'cross_check_folder'
INFO_LOG = 'log'
INFO_LOGS = 'logs'
INFO_BANDS = 'band'
INFO_OPERATORS = 'operators'
ERR_IO = 'io'
ERR_HEADER = 'header'
ERR_QSO = 'qso'

class Operator(object):
    """
    Keep operator callsign, info and logs path
    """
    callsign = None
    logs = []           # list with Log() instances
    points_multipliers = 1

    def __init__(self, callsign):
        self.callsign = callsign
        self.logs = []

    def add_log_by_path(self, path, rules=None, checklog=False):
        self.logs.append(Log(path, rules=rules, checklog=checklog))

    def add_log_instance(self, log):
        self.logs.append(log)

    def logs_by_band_regexp(self, band_regexp):
        logs = []
        for log in self.logs:
            if not log.valid_header:
                continue
            res = re.match(band_regexp, log.band, re.IGNORECASE)
            if res:
                logs.append(log)
        return logs


class Log(object):
    use_as_checklog = False
    ignore_this_log = None  # if flag is set this log will not be used in cross-check
    errors = None
    valid_header = None
    valid_qsos = None

    callsign = None
    band = None
    mode = None
    operator = None
    email = None
    category = None

    qsos = list()   # list with LogQso instances
    qsos_points = None
    qsos_confirmed = None

    def __init__(self, path, rules=None, checklog=False):
        self.path = path
        self.rules = rules
        self.use_as_checklog = checklog
        self.ignore_this_log = False
        self.errors = {ERR_IO: [],
                       ERR_HEADER: [],
                       ERR_QSO: []}

        # do header validation
        cab = self.validate_header_and_qsos()
        if not self.valid_header or cab == None:
            return

        # get qso's
        self.get_qsos(cab.valid_qso)
        self.valid_qsos = True
        for qso in self.qsos:
            if qso.errors:
                self.errors[ERR_QSO].extend(qso.errors)
                self.valid_qsos = False


    @staticmethod
    def read_file_content(path):
        try:
            with open(path, 'r') as _file:
                content = _file.readlines()
        except IOError:
            raise
        except Exception:
            raise
        return content

    def validate_header_and_qsos(self):
        """ Validate cabrillo log header.
        If errors are found they will be written in self.errors dictionary
        """
        self.valid_header = False
        try:
            self.log_lines = self.read_file_content(self.path)
        except Exception as e:
            self.errors[ERR_IO].append(('-', 'Cannot read cabrillo log. Error: {}'.format(e)))
            return None
        
        if len(self.log_lines) == 0:
            self.errors[ERR_IO].append(('-', 'Log is empty'))
            return None
        
        for line in self.log_lines:
            if 'START-OF-LOG' in line and '3.0' not in line:
                self.errors[ERR_HEADER].append(('-', 'Only Cabrillo v3 supprted'))
                return None
        try:
            cab = parse_log_file(self.path, ignore_order=True)
        except InvalidLogException as e:
            self.errors[ERR_HEADER].append(('-', str(e)))
            return None
        except InvalidQSOException as e:
            self.errors[ERR_QSO].append(('-', '-', str(e)))
            return None
        except ValueError as e:
            self.errors[ERR_QSO].append(('-', '-', str(e)))
            return None

        # validate 'CALLSIGN:'
        call_regexp = None
        if self.rules and self.rules.contest_extra_field_value('callregexp'):
            call_regexp = '^\s*(' + self.rules.contest_extra_field_value('callregexp') + ').*'

        if not cab.callsign:
            self.errors[ERR_HEADER].append(('-', 'CALLSIGN field is empty'))
        # TODO : "elif..." check if callsign field is present multiple times
        # TODO : not possible with current 'cabrillo' lib implementation
        elif not self.validate_callsign(cab.callsign):
            self.errors[ERR_HEADER].append(('-', 'CALLSIGN field content is not valid'))
        elif call_regexp and not re.match(call_regexp, cab.callsign, re.IGNORECASE):
            self.errors[ERR_HEADER].append(('-', 'CALLSIGN field content doesn\'t match \'callregexp\' value from rules'))
        else:
            self.callsign = cab.callsign.upper()

        # validate 'CATEGORY-BAND:'
        if not cab.category_band:
            self.errors[ERR_HEADER].append(('-', 'CATEGORY-BAND field is empty'))
        # TODO : "elif..." check if band field is present multiple times, not possible...
        self.band = cab.category_band

        # validate 'CATEGORY-MODE:' (CW, FM, SSB, MIXED, ...)
        if not cab.category_mode:
            self.errors[ERR_HEADER].append(('-', 'CATEGORY-MODE field is empty'))
        # TODO : "elif..." check if mode field is present multiple times, not possible...
        self.mode = cab.category_mode

        # validate 'CATEGORY-OPERATOR:' (SINGLE-OP, MULTI-OP, CHECKLOG)
        if not cab.category_operator:
            self.errors[ERR_HEADER].append(('-', 'CATEGORY-OPERATOR field is empty'))
        # TODO : "elif..." check if operator field is present multiple times, not possible...
        self.operator = cab.category_operator

        # validate 'EMAIL:'
        if self.rules and 'email' in self.rules.contest_extra_fields:
            if not cab.email:
                self.errors[ERR_HEADER].append(('-', 'EMAIL field is empty'))
            # TODO : "elif.." check if email fiels is present multiple times, not possible...
            elif not self.validate_email(cab.email):
                self.errors[ERR_HEADER].append(('-', 'EMAIL field value is not valid ({})'.format(cab.email)))
        self.email = cab.email

        # are all mandatory fields valid ?
        if all((self.callsign, self.band, self.mode, self.operator)):
            self.valid_header = True

        # return the intance of cabrillo log
        return cab

    def get_qsos(self, cab_qsos):
        """
        Input : cabrillo library qso's
        Output : will return a list of LogQso
        """
        self.qsos = list()
        for _qso_nr, _qso in enumerate(cab_qsos):
            # print("DEBUG QSOS :", _qso, _qso_nr)
            self.qsos.append(LogQso(_qso, _qso_nr, self.rules))

    @staticmethod
    def validate_callsign(callsign):
        if not callsign:
            return False
        regex_pcall = '^\s*(\w+[0-9]+\w+/?\w*)\s*$'  # \s*(\w+\d+[a-zA-Z]+(/(M|AM|P|MM))?)\s*$"
        res = re.match(regex_pcall, callsign)
        return True if res else False
    
    @staticmethod
    def get_band(band):
        pass
        # TODO : to impl
    
    @staticmethod
    def validate_band(band_value):
        pass
        # TODO : to impl
    
    @staticmethod
    def rules_based_validate_band(band_value, rules):
        pass
        # TODO : to impl
    
    @staticmethod
    def validate_category(category_value):
        pass
        # TODO : to impl
    
    @staticmethod
    def rules_based_validate_category(category_value, rules):
        pass
        # TODO : to impl
    
    @staticmethod
    def validate_date(date_value):
        pass
        # TODO : to impl
    
    @staticmethod
    def validate_email(email):
        if not email:
            return False
        return validate_email(email)
    
    @staticmethod
    def validate_address(address):
        pass
        # TODO : to impl
    
    @staticmethod
    def rules_based_validate_date(self, date_value, rules):
        pass
        # TODO : to impl

class LogQso(object):
    def __init__(self, qso_cabrillo_lib=None, qso_line_number=None, rules=None):
        self.qso_line = qso_cabrillo_lib
        self.line_nr = qso_line_number
        self.rules = rules
        self.valid = True

        self.errors = []
        self.cc_confirmed = None  # possible values: True, False
        self.cc_error = []  # here we store errors from cross-check
        self.points = None  # if qso is confirmed we store here the calculated points (multiplier included)

        self.qso_fields = {'freq': None,
                           'mode': None,
                           'date': None,
                           'hour': None,
                           'call': None,
                           'rst_sent': None,
                           'nr_sent': None,
                           'exch_sent': None,
                           'rst_recv': None,
                           'nr_recv': None,
                           'exch_recv': None
                           }
        # 1st validation
        self.validate_qso_format()
        if not self.valid:
            return
        self.parse_qso_fields()

    def validate_qso_format(self):
    # TODO : need to implement this valiation, at this moment I trus the validation from cabrillo library 
        # just a single validation, check if we have 13 fields into each QSL line
        nr_of_fields = len(str(self.qso_line).split())
        if nr_of_fields != 13:
            self.errors.append((self.line_nr, self.qso_line, "QSO number of fields is not 13"))
            self.valid = False


    def parse_qso_fields(self):
        # print("QSO F DIR :", dir(self.qso_line))
        # print("QSO DICT :", self.qso_line.__dict__)
        self.qso_fields['freq'] = self.qso_line.freq
        self.qso_fields['mode'] = self.qso_line.mo
        self.qso_fields['date'] = self.qso_line.date.strftime('%Y-%m-%d')
        self.qso_fields['hour'] = self.qso_line.date.strftime('%H%M')
        self.qso_fields['call'] = self.qso_line.dx_call
        self.qso_fields['rst_sent'] = self.qso_line.de_exch[0]
        self.qso_fields['nr_sent'] = self.qso_line.de_exch[1]
        self.qso_fields['exch_sent'] = self.qso_line.de_exch[2]
        self.qso_fields['rst_recv'] = self.qso_line.dx_exch[0]
        self.qso_fields['nr_recv'] = self.qso_line.dx_exch[1]
        self.qso_fields['exch_recv'] = self.qso_line.dx_exch[2]
        # print("DEBUG QSO_FIELDS:", self.qso_fields)


def crosscheck_logs_filter(log_class, rules=None, logs_folder=None, checklogs_folder=None):
    ignored_logs = []

    if not rules:
        print('No rules were provided')
        return {}
    logs_instances = []
    if not logs_folder:
        print('Logs folder was not provided')
        return {}
    if logs_folder and not os.path.isdir(logs_folder):
        print('Cannot open logs folder : {}'.format(logs_folder))
        return {}
    for filename in os.listdir(logs_folder):
        logs_instances.append(log_class(os.path.join(logs_folder, filename), rules=rules))
    # print("DEBUG LOG_INST :", logs_instances)

    # if checklogs_folder ....
        # TODO : implement the case when checklogs are provided (not needed now, later...)

    # create instances for all hamd and add logs with valid header
    operator_instances = {}
    for log in logs_instances:
        if not log.valid_header:
            log.ignore_this_log = True
            ignored_logs.append(log)
            continue
        callsign = log.callsign.upper()
        if not operator_instances.get(callsign, None):
            operator_instances[callsign] = Operator(callsign)
        operator_instances[callsign].add_log_instance(log)

    # if we find multiple logs for a ham on a band
    # we set Log.ignore_this_logs for older files
        # TODO : will not implement this now... later

    # do the cross-check over filered logs
    for band in range(1, rules.contest_bands_nr+1):
        crosscheck_logs(operator_instances, rules, band)

    # calculate points in every logs
    for op, op_inst in operator_instances.items():
        for log in op_inst.logs:
            points = 0
            confirmed = 0
            for qso in log.qsos:
                if qso.points and qso.points > 0:
                    points += qso.points
                    confirmed += 1
            log.qsos_points = points
            log.qsos_confirmed = confirmed
            # print("DEBUG callsign multi :", operator_instances[op].callsign, operator_instances[op].points_multipliers)

    return operator_instances


def crosscheck_logs(operator_instances, rules, band_nr):
    """
    :param operator_instances: dictionary {key=callsign, value=Operator(callsign)}
    :param band_nr: number of contest band
    """
    for callsign1, ham1 in operator_instances.items():
        # print("DEBUG CL1 :", callsign1, ham1.callsign, ham1.logs)
        # set a liwt for this ham with already made contacts
        _had_qso_with = []
        # get logs for band
        _logs1 = ham1.logs_by_band_regexp(rules.contest_band(band_nr)['regexp'])
        if not _logs1:
            continue

        # use logs that : is not checklog , is not to ignore & has valid header
        for log1 in _logs1:
            if all((log1.use_as_checklog is False,
                    log1.ignore_this_log is False,
                    log1.valid_header is True)):
                break
        else:
            continue

        for qso1 in log1.qsos:
            # print("DEBUG QSO_1", qso1, qso1.valid)
            if qso1.valid is False:
                qso1.cc_confirmed = False
                qso1.cc_error = 'Qso is not valid (Sorin: REFINE THIS ERROR)'
                continue
            
            if qso1.cc_confirmed is True:
                # code should never reach here
                continue

            callsign2 = qso1.qso_fields['call'].upper()

            # validate that this qso isn't an duplicate for current period
            # TODO : later

            # check if we have some logs from 2nd ham
            ham2 = operator_instances.get(callsign2, None)
            if not ham2:
                qso1.cc_confirmed = False
                qso1.cc_error = 'No log from {}'.format(callsign2)
                continue

            # check if we have the proper and logs from 2nd ham
            _logs2 = ham2.logs_by_band_regexp(rules.contest_band(band_nr)['regexp'])
            if not _logs2:
                qso1.cc_confirmed = False
                qso1.cc_error = 'No log for this band from {}'.format(callsign2)
                continue

            # use the 1st log that : is not to ignore & has valid header
            for log2 in _logs2:
                if all((log2.ignore_this_log is False,
                        log2.valid_header is True)):
                    break
            else:
                qso1.cc_confirmed = False
                qso1.cc_error = 'No valid log from {}'.format(callsign2)
                continue

            # get the 2nd ham qsos and compare them with the 1st ham qso
            for qso2 in log2.qsos:
                if qso2.valid is False:
                    continue
                
                _callsign2 = qso2.qso_fields['call'].upper()
                if callsign1 != _callsign2:
                    continue

                # TODO : check qso is inside period (doing this later)
                confirmed = qso1.qso_line.match_against(qso2.qso_line)
                # print("DEBUG CONFIRMED :", confirmed, callsign1, callsign2, qso1.qso_fields['call'], qso2.qso_fields['call'])
                if confirmed:
                    qso1.cc_confirmed = True
                    qso1.points = int(rules.contest_band(band_nr)['multiplier'])
                    multiplier_callsign_list = rules.contest_band(band_nr)['multiplier_stations'].split(',')
                    if _callsign2 in multiplier_callsign_list:
                        operator_instances[callsign1].points_multipliers += 1
                    qso1.cc_error = []
            else:
                qso1.cc_confirmed = False
                qso1.cc_error = 'No qso found on {} log'.format(callsign2)                    

    
def compare_qso(log1, qso1, log2, qso2):
    # TODO : no need to implement this since I'm using the implementation from cabrillo library
    pass

def is_multiplicator(call_sign):
    # TODO : take in consideration how the multiplicators
    #        will be handlded
    pass