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
import math
import os
import re
import datetime
from collections import namedtuple
import json
from datetime import datetime, timedelta

from dicttoxml import dicttoxml
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
    info = {}           # FIXME : no idea what was this for :(
    logs = []           # list with Log() instances

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
    """
    Keep a single EDI log information:
    log path, log raw content, callsign, qth, band, category(section), qsos tuple (raw content)
    and a list with LogQso() instances

    errors format :
    {
        'file': [ (line or None, 'error: Cannot open file'), ... ],
        'header': [ (line or None, 'error: message'), ... ],
        'qso': [ (line, 'error: message'), ...],
    }
    """
    use_as_checklog = False
    ignore_this_log = None  # if flag is set this log will not be used in cross-check

    path = None
    rules = None
    log_lines = None
    valid_header = None
    valid_qsos = None
    errors = None
    callsign = None
    maidenhead_locator = None
    band = None
    category = None  # section
    category_raw = None
    date = None
    email = None
    address = None
    name = None

    qsos_tuple = namedtuple('qso_tuple', ['linenr', 'qso', 'valid', 'errors']) # REMOVE
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

        self.validate_header()
        if not self.valid_header:
            return

        self.get_qsos()
        self.valid_qsos = True
        for qso in self.qsos:
            if qso.errors:
                self.errors[ERR_QSO].extend(qso.errors)
                self.valid_qsos = False

    def validate_header(self):
        """ Validate edi log header.
        If errors are found they will be written in self.errors dictionary
        """
        self.valid_header = False

        try:
            self.log_lines = self.read_file_content(self.path)
        except Exception as e:
            self.errors[ERR_IO].append((None, 'Cannot read edi log. Error: {}'.format(e)))
            return

        if len(self.log_lines) == 0:
            self.errors[ERR_IO].append((None, 'Log is empty'))
            return


        # get & validate callsign
        _callsign, line_nr = self.get_field('PCall')
        call_regexp = None
        if self.rules and self.rules.contest_extra_field_value('callregexp'):
            call_regexp = '^\s*(' + self.rules.contest_extra_field_value('callregexp') + ').*'

        if not _callsign:
            self.errors[ERR_HEADER].append((line_nr, 'PCall field is not present'))
        elif len(_callsign) > 1:
            self.errors[ERR_HEADER].append((line_nr, 'PCall field is present multiple times'))
        elif not self.validate_callsign(_callsign[0]):
            self.errors[ERR_HEADER].append((line_nr, 'PCall field content is not valid'))
        elif call_regexp and not re.match(call_regexp, _callsign[0], re.IGNORECASE):
            self.errors[ERR_HEADER].append((line_nr, 'PCall field content doesn\'t match \'callregexp\' value from rules'))
        else:
            self.callsign = _callsign[0].upper()

        # get & validate maidenhead locator
        _qthlocator, line_nr = self.get_field('PWWLo')
        if not _qthlocator:
            self.errors[ERR_HEADER].append((line_nr, 'PWWLo field is not present'))
        elif len(_qthlocator) > 1:
            self.errors[ERR_HEADER].append((line_nr, 'PWWLo field is present multiple times'))
        elif not self.validate_qth_locator(_qthlocator[0]):
            self.errors[ERR_HEADER].append((line_nr, 'PWWLo field value is not valid'))
        else:
            self.maidenhead_locator = _qthlocator[0].upper()

        # get & validate band based on generic rules and by custom rules if provided (rules.contest_band['regexp'])
        _band, line_nr = self.get_field('PBand')
        if not _band:
            self.errors[ERR_HEADER].append((line_nr, 'PBand field is not present'))
        elif len(_band) > 1:
            self.errors[ERR_HEADER].append((line_nr, 'PBand field is present multiple times'))
        elif not self.rules and not self.validate_band(_band[0]):
            self.errors[ERR_HEADER].append((line_nr, 'PBand field value is not valid'))
        elif self.rules and not self.rules_based_validate_band(_band[0], self.rules):
            self.errors[ERR_HEADER].append((line_nr, 'PBand field value has an invalid value ({}). '
                                                  'Not as defined in contest rules'.format(_band[0])))
        else:
            self.band = _band[0]

        # get & validate PSect based on generic rules and by custom rules if provided (rules.contest_category['regexp']
        _category, line_nr = self.get_field('PSect')
        if not _category:
            self.errors[ERR_HEADER].append((line_nr, 'PSect field is not present'))
        elif len(_category) > 1:
            self.errors[ERR_HEADER].append((line_nr, 'PSect field is present multiple times'))
        elif not self.rules and self.validate_category(_category[0]) == (False, None):
            self.errors[ERR_HEADER].append((line_nr, 'PSect field value is not valid ({})'.format(_category[0])))
        elif self.rules and self.rules_based_validate_category(_category[0], self.rules) == (False, None):
            self.errors[ERR_HEADER].append((line_nr, 'PSect field value has an invalid value ({}). '
                                          'Not as defined in contest rules'.format(_category[0])))
        else:
            self.category_raw = _category[0]
            # normalize self.category_raw
            if self.rules:
                _res, _cat = self.rules_based_validate_category(self.category_raw, self.rules)
                self.category = _cat
            else:
                _res, _cat = self.validate_category(self.category_raw)
                self.category = _cat


        # get & validate TDate based on generic rules format and by custom rules if provided
        # (rules.contest_begin_date & rules.contest_end_date)
        _date, line_nr = self.get_field('TDate')
        if not _date:
            self.errors[ERR_HEADER].append((line_nr, 'TDate field is not present'))
        elif len(_date) > 1:
            self.errors[ERR_HEADER].append((line_nr, 'TDate field is present multiple times'))
        elif not self.validate_date(_date[0]):
            self.errors[ERR_HEADER].append((line_nr, 'TDate field value is not valid ({})'.format(_date[0])))
        elif self.rules and not self.rules_based_validate_date(_date[0], self.rules):
            self.errors[ERR_HEADER].append((line_nr, 'TDate field value has an invalid value ({}). '
                                                  'Not as defined in contest rules'.format(_date[0])))
        else:
            self.date = _date[0]

        # are all mandatory fields valid ?
        if all((self.callsign, self.maidenhead_locator, self.band, self.category, self.date)):
            self.valid_header = True

        # validate email from [extra] @ rules
        _email, line_nr = self.get_field('RHBBS')
        _email_valid = False
        if self.rules and 'email' in self.rules.contest_extra_fields:
            if not _email:
                self.errors[ERR_HEADER].append((line_nr, 'RHBBS field is not present'))
            elif len(_email) > 1:
                self.errors[ERR_HEADER].append((line_nr, 'RHBBS is present multiple times'))
            elif not self.validate_email(_email[0]):
                self.errors[ERR_HEADER].append((line_nr, 'RHBBS field value is not valid ({})'.format(_email[0])))
            else:
                self.email = _email[0]
                _email_valid = True
            if not _email_valid:
                self.valid_header = False

        # validate address from [extra] @ rules
        _address, line_nr = self.get_field('PAdr1')
        _address_valid = False
        if self.rules and 'address' in self.rules.contest_extra_fields:
            if not _address:
                self.errors[ERR_HEADER].append((line_nr, 'PAdr1 field is not present'))
            elif len(_address) > 1:
                self.errors[ERR_HEADER].append((line_nr, 'PAdr1 is present multiple times'))
            elif not self.validate_address(_address[0]):
                self.errors[ERR_HEADER].append((line_nr, 'PAdr1 field is too short ({})'.format(_address[0])))
            else:
                self.address = _address[0]
                _address_valid = True
            if not _address_valid:
                self.valid_header = False

        # validate name from [extra] @ rules
        _name, line_nr = self.get_field('RName')
        _name_valid = False
        if self.rules and 'name' in self.rules.contest_extra_fields:
            if not _name:
                self.errors[ERR_HEADER].append((line_nr, 'RName field is not present'))
            elif len(_name) > 1:
                self.errors[ERR_HEADER].append((line_nr, 'RName is present multiple times'))
            elif len(_name[0]) < 8:
                self.errors[ERR_HEADER].append((line_nr, 'RName field is too short ({})'.format(_name[0])))
            else:
                self.name = _name[0]
                _name_valid = True
            if not _name_valid:
                self.valid_header = False

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

    def get_field(self, field):
        """
        Search log content for a field
        :param field: field name (PCall, TDate, ...)
        :return: tuple(value, line_number or None)
        """
        value = []
        line_nr = None
        _field = str(field).upper() + '='
        for (nr, line_content) in enumerate(self.log_lines):
            if line_content.upper().startswith(_field):
                value.append(line_content.split('=', 1)[1].strip())
                line_nr = nr+1
        return value, line_nr

    def get_qsos(self):
        """
        Will read the self.log_content and will return a list of LogQso
        """
        qso_record_start = "[QSORECORDS"
        qso_record_end = "[END"
        qso_lines = []
        do_read_qso = False

        # read qso lines
        for (index, line) in enumerate(self.log_lines):
            if line.upper().startswith(qso_record_start):
                do_read_qso = True
                continue
            if line.upper().startswith(qso_record_end):
                do_read_qso = False
                continue
            if do_read_qso:
                qso_lines.append((index+1, line.strip().upper()))

        # validate qso lines
        self.qsos = list()
        for qso in qso_lines:
            self.qsos.append(
                # REMOVE self.qsos_tuple(linenr=qso[0], qso=qso[1], valid=False if message else True, error=message)
                LogQso(qso[1], qso[0], self.rules)  # LogQso(qso_line, qso_line_number_in_log)
            )

    @staticmethod
    def validate_callsign(callsign):
        if not callsign:
            return False
        regex_pcall = '^\s*(\w+[0-9]+\w+/?\w*)\s*$'  # \s*(\w+\d+[a-zA-Z]+(/(M|AM|P|MM))?)\s*$"
        res = re.match(regex_pcall, callsign)
        return True if res else False

    @staticmethod
    def validate_qth_locator(qth):
        if not qth:
            return False
        regex_maidenhead = r'^\s*([a-rA-R]{2}\d{2}[a-xA-X]{2})\s*$'
        res = re.match(regex_maidenhead, qth, re.IGNORECASE)
        return True if res else False

    @staticmethod
    def get_band(band):
        """
        This will parse the 'PBand=' field value
        and return the proper band
        :param band: the content of 'PBand=' field
        :return: The detected band (144,432,1296) or None
        """
        if not band:
            return None

        regexp_band = {'144': ['144.*', '145.*'],
                       '432': ['430.*', '432.*', '435.*'],
                       '1296': ['1296.*', '1[.,][23].*']}
        for _band in regexp_band:
            for regexp in regexp_band[_band]:
                res = re.match(regexp, band)
                if res:
                    return _band
        return None

    @staticmethod
    def validate_band(band_value):
        """
        This will validate PBand based on generic rules
        """
        is_valid = False
        if not band_value:
            return is_valid

        regexp_band_check = ['144.*', '145.*',
                             '430.*', '432.*', '435.*',
                             '1296.*', '1[.,][23].*']
        for _regex in regexp_band_check:
            res = re.match(_regex, band_value)
            if res:
                is_valid = True
        return is_valid

    @staticmethod
    def rules_based_validate_band(band_value, rules):
        """
        This will validate PBand based on Rules class instance
        """
        is_valid = False
        if not band_value:
            return is_valid

        if rules is None:
            raise ValueError('No contest rules provided !')
        for _nr in range(1, rules.contest_bands_nr+1):
            _regex = r'\s*(' + rules.contest_band(_nr)['regexp'] + r')\s*'
            res = re.match(_regex, band_value)
            if res:
                is_valid = True
        return is_valid

    @staticmethod
    def validate_category(category_value):
        """
        This will validate PSect based on generic rules
        """
        if not category_value:
            return False, None

        regexpCategories = {
            'single': ['.*SOSB.*', '.*SOMB.*', '.*Single.*', '^SO$'],
            'multi': ['.*MOSB.*', '.*MOMB.*', '.*Multi.*', '^MO$'],
            'checklog': ['check', 'checklog', 'check log']
        }
        for _cat, _regex_list in regexpCategories.items():
            for _regex in _regex_list:
                res = re.match(_regex, category_value, re.IGNORECASE)
                if res:
                    return True, _cat
        return False, None

    @staticmethod
    def rules_based_validate_category(category_value, rules):
        """
        This will validate PSect based on Rules class instance
        """
        if not category_value:
            return False, None

        if rules is None:
            raise ValueError('No contest rules provided !')
        for _nr in range(1, rules.contest_categories_nr+1):
            _regex = r'\s*(' + rules.contest_category(_nr)['regexp'] + r')\s*'
            res = re.match(_regex, category_value, re.IGNORECASE)
            if res:
                return True, rules.contest_category(_nr)['name']
        return False, None

    @staticmethod
    def normalize_category(category_value, rules):
        pass

    @staticmethod
    def validate_date(date_value):
        """
        This will validate TDate based on generic rules
        """
        is_valid = False
        dates = date_value.split(';')
        if len(dates) != 2:
            return is_valid
        is_valid = True
        for _date in dates:
            try:
                datetime.strptime(_date, '%Y%m%d')
            except ValueError:
                is_valid = False
                break
        return is_valid

    @staticmethod
    def validate_email(email):
        if not email:
            return False
        return validate_email(email)

    @staticmethod
    def validate_address(address):
        """
        Small validation that we have some address.
        We check to have at least 10 characters
        and address to contain char: space or commma or period
        """
        if not address:
            return False
        if len(address) < 10:
            return False
        chars_to_search = (' ', ',', '.')
        res = list(filter(lambda x: x in chars_to_search, address.strip()))
        if not res:
            return False
        return True

    def rules_based_validate_date(self, date_value, rules):
        """
        This will validate TDate based on Ruless class instance
        """
        is_valid = False

        if rules is None:
            raise ValueError('No contest rules provided !')
        _begin_date, _end_date = date_value.split(';')
        if _begin_date >= rules.contest_begin_date and _end_date <= rules.contest_end_date:
            is_valid = True

        return is_valid


class LogQso(object):
    """
    Keep a single QSO (in EDI format) and some info:
    qso line number, raw qso, is valid ? , error message if !valid, all qso fields
    """
    REGEX_MINIMAL_QSO_CHECK = '(?P<date>.*?);(?P<hour>.*?);(?P<call>.*?);(?P<mode>.*?);' \
                              '(?P<rst_sent>.*?);(?P<nr_sent>.*?);(?P<rst_recv>.*?);(?P<nr_recv>.*?);' \
                              '(?P<exchange_recv>.*?);(?P<wwl>.*?);(?P<points>.*?);' \
                              '(?P<new_exchange>.*?);(?P<new_wwl>.*?);(?P<new_dxcc>.*?);(?P<duplicate_qso>.*?)'
    REGEX_MEDIUM_QSO_CHECK = '\d{6};\d{4};.*?;.?;\d{2,3}.?;\d{1,4};\d{2,3}.?;\d{1,4};.*?;' \
                             '[a-zA-Z]{2}\d{2}[a-zA-Z]{2};.*?;.*?;.*?;.*?;.*?'
    #                          date  time   id  m    rst       nr      rst       nr    .  qth  km  .   .   .   .

    def __init__(self, qso_line=None, qso_line_number=None, rules=None):
        self.qso_line = qso_line
        self.line_nr = qso_line_number
        self.rules = rules
        self.valid = True

        self.errors = []
        self.cc_confirmed = None  # possible values: True, False
        self.cc_error = []  # here we store errors from cross-check
        self.points = None  # if qso is confirmed we store here the calculated points (multiplier included)

        self.qso_fields = {'date': None,
                           'hour': None,
                           'call': None,
                           'mode': None,
                           'rst_sent': None,
                           'nr_sent': None,
                           'rst_recv': None,
                           'nr_recv': None,
                           'exchange_recv': None,
                           'wwl': None,
                           'points': None,
                           'new_exchange': None,
                           'new_wwl': None,
                           'new_dxcc': None,
                           'duplicate_qso': None,
                           }

        # 1st validation
        self.validate_qso_format()
        if not self.valid:
            return
        self.parse_qso_fields()

        # 2nd validation
        self.generic_qso_validator()
        if not self.valid:
            return

        if self.rules:
            self.rules_based_qso_validator()

    def validate_qso_format(self):
        """ Validate qso line.
        If errors are found they will be written in self.errors string
        """
        err = self.regexp_qso_validator(self.qso_line) or None
        if err:
            self.errors.append((self.line_nr, self.qso_line, err))
            self.valid = False

    def parse_qso_fields(self):
        """
        This should parse a qso based on log format
        """
        res = re.match(self.REGEX_MINIMAL_QSO_CHECK, self.qso_line)
        if res:
            for key in self.qso_fields:
                self.qso_fields[key] = res.group(key)

    @classmethod
    def regexp_qso_validator(cls, line):
        """
        This will validate the a line of qso from .edi log
        :param line:
        :return: None or error message
        """
        qso_min_line_length = 40
        field_names = ('date', 'hour', 'callsign', 'mode', 'rst sent', 'rst send nr', 'rst received', 'rst received nr',
                       'exchange received', 'wwl', 'points', 'new exchange', 'new wwl', 'new dxcc', 'duplicate_qso')

        if len(line) < qso_min_line_length:
            return 'Qso line is too short'
        res = re.match(cls.REGEX_MINIMAL_QSO_CHECK, line)
        if not res:
            return 'Incorrect Qso line format (incorrect number of fields).'
        res = re.match(cls.REGEX_MEDIUM_QSO_CHECK, line)
        if not res:
            for (regex, field, name) in zip(cls.REGEX_MEDIUM_QSO_CHECK.split(';'),
                                            line.split(';'),
                                            field_names):
                if not re.match('^'+regex+'$', field):
                    return 'Qso field <{}> has an invalid value ({})'.format(name, field)
        return None

    def generic_qso_validator(self):
        """
        This will validate a parsed qso based on generic rules
        :return:
        """

        # validate date format
        try:
            datetime.strptime(self.qso_fields['date'], '%y%m%d')
        except ValueError as why:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line, 'Qso date is invalid: {}'.format(str(why))))

        # validate time format
        try:
            datetime.strptime(self.qso_fields['hour'], '%H%M')
        except ValueError as why:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line, 'Qso hour is invalid: {}'.format(str(why))))

        # validate callsign format
        re_call = r'^\w+/?\w+$'
        result = re.match(re_call, self.qso_fields['call'])
        if not result:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line, 'Callsign is invalid: {}'.format(self.qso_fields['call'])))

        # validate mode format
        re_mode = "^[0-9]$"
        result = re.match(re_mode, self.qso_fields['mode'])
        if not result:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line, 'Qso mode is invalid: {}'.format(self.qso_fields['mode'])))

        # validate RST (sent & recv) format
        re_rst = "^[1-5][1-9][1-9]?[aAsS]?$"
        result = re.match(re_rst, self.qso_fields['rst_sent'])
        if not result:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line, 'Rst is invalid: {}'.format(self.qso_fields['rst_sent'])))
        result = re.match(re_rst, self.qso_fields['rst_recv'])
        if not result:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line, 'Rst is invalid: {}'.format(self.qso_fields['rst_recv'])))

        # validate NR (sent & recv) format
        re_sent_recv_nr = r'^\d{1,4}$'
        result = re.match(re_sent_recv_nr, self.qso_fields['nr_sent'])
        if not result:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line, 'Sent Qso number is invalid: {}'.format(self.qso_fields['nr_sent'])))
        result = re.match(re_sent_recv_nr, self.qso_fields['nr_recv'])
        if not result:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line, 'Received Qso number is invalid: {}'.format(self.qso_fields['nr_recv'])))

        # validate 'exchange_recv' format
        re_exchange = r'^\w{0,6}$'
        result = re.match(re_exchange, self.qso_fields['exchange_recv'])
        if not result:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line, 'Received exchange is invalid: {}'.format(self.qso_fields['exchange_recv'])))

        # validate QTH locator format
        if not Log.validate_qth_locator(self.qso_fields['wwl']):
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line, 'Qso WWL is invalid: {}'.format(self.qso_fields['wwl'])))

        # validate 'duplicate_qso' format
        if self.qso_fields['duplicate_qso'].upper() == 'D':
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line, 'Qso marked as duplicate'))

        return None

    def rules_based_qso_validator(self):
        """
        This will validate the self.qsoFields based on Rules class instance
        :param rules:
        :return:
        """
        if self.rules is None:
            return

        # if field 'callregexp' from rules file is present, will filter the accepted callsigns in the contest
        # this is usefull for national contests
        if self.rules.contest_extra_field_value('callregexp'):
            call_regexp = '^\s*' + self.rules.contest_extra_field_value('callregexp')
            if not re.match(call_regexp, self.qso_fields['call'], re.IGNORECASE):
                self.valid = False
                self.errors.append((self.line_nr,
                                    self.qso_line,
                                    'Qso callsign is not accepted based on \'callregexp\' from rules files'))

        # validate qso date
        if self.qso_fields['date'] < self.rules.contest_begin_date[2:]:
            self.valid = False
            self.errors.append((self.line_nr,
                                self.qso_line,
                                'Qso date is invalid: before contest starts (<{})'.format(self.rules.contest_begin_date[2:])))
        if self.qso_fields['date'] > self.rules.contest_end_date[2:]:
            self.valid = False
            self.errors.append((self.line_nr,
                                self.qso_line,
                                'Qso date is invalid: after contest ends (>{})'.format(self.rules.contest_end_date[2:])))

        # validate qso hour
        if self.qso_fields['date'] == self.rules.contest_begin_date[2:] and \
           self.qso_fields['hour'] < self.rules.contest_begin_hour:
            self.valid = False
            self.errors.append((self.line_nr,
                                self.qso_line,
                                'Qso hour is invalid: before contest start hour (<{})'.format(self.rules.contest_begin_hour)))
        if self.qso_fields['date'] == self.rules.contest_end_date[2:] and self.qso_fields['hour'] > self.rules.contest_end_hour:
            self.valid = False
            self.errors.append((self.line_nr,
                                self.qso_line,
                                'Qso hour is invalid: after contest end hour (>{})'.format(self.rules.contest_end_hour)))

        # validate date & hour based on period
        inside_period, _ = self.qso_inside_period()

        if not inside_period:
            self.valid = False
            self.errors.append((self.line_nr,
                                self.qso_line,
                                'Qso date/hour is invalid: not inside contest periods'))

        # validate qso mode
        if int(self.qso_fields['mode']) not in self.rules.contest_qso_modes:
            self.valid = False
            modes_str = ','.join(map(str, self.rules.contest_qso_modes))
            self.errors.append((self.line_nr,
                                self.qso_line,
                                'Qso mode is invalid: not in defined modes ({})'.format(modes_str)))
        return None

    def qso_inside_period(self):
        """
        :return: True, period_number
                 False, None
        """
        inside_period = False
        inside_period_nr = None

        if not self.rules:
            return True, None

        for period in range(1, self.rules.contest_periods_nr + 1):
            # if date is not in period, check next period
            if not (self.rules.contest_period(period)['begindate'][2:] <= self.qso_fields['date'] <= self.rules.contest_period(period)['enddate'][2:]):
                continue
            _enddate = datetime.strptime(self.rules.contest_period(period)['enddate'], '%Y%m%d')
            _begindate = datetime.strptime(self.rules.contest_period(period)['begindate'], '%Y%m%d')
            delta_days = _enddate - _begindate
            # if period is in same day
            if delta_days == timedelta(0) and self.rules.contest_period(period)['beginhour'] <= self.qso_fields['hour'] <= self.rules.contest_period(period)['endhour']:
                    inside_period = True
                    inside_period_nr = period
                    break
            # if period is in multiple days
            elif delta_days > timedelta(0):
                if self.rules.contest_period(period)['begindate'][2:] == self.qso_fields['date'] and self.rules.contest_period(period)['beginhour'] <= self.qso_fields['hour']:
                    inside_period = True
                    inside_period_nr = period
                    break
                if self.qso_fields['date'] == self.rules.contest_period(period)['enddate'][2:] and self.qso_fields['hour'] <= self.rules.contest_period(period)['endhour']:
                    inside_period = True
                    inside_period_nr = period
                    break
                # if begin_period < qso_date < end_period
                if self.rules.contest_period(period)['begindate'][2:] < self.qso_fields['date'] < self.rules.contest_period(period)['enddate'][2:]:
                    inside_period = True
                    inside_period_nr = period
                    break
        return inside_period, inside_period_nr


class LogException(Exception):
    def __init__(self, message, line):
        self.message = message
        self.line = line


def crosscheck_logs_filter(log_class, rules=None, logs_folder=None, checklogs_folder=None):

    ignored_logs = []

    if not rules:
        print('No rules were provided')
        return {}
    # create instances for all logs
    logs_instances = []
    if not logs_folder:
        print('Logs folder was not provided')
        return {}
    if logs_folder and not os.path.isdir(logs_folder):
        print('Cannot open logs folder : {}'.format(logs_folder))
        return {}
    for filename in os.listdir(logs_folder):
        logs_instances.append(log_class(os.path.join(logs_folder, filename), rules=rules))

    if checklogs_folder:
        if os.path.isdir(checklogs_folder):
            for filename in os.listdir(checklogs_folder):
                logs_instances.append(log_class(os.path.join(checklogs_folder, filename), rules=rules, checklog=True))
        else:
            print('Cannot open checklogs folder : {}'.format(checklogs_folder))
            return {}

    # create instances for all hams and add logs with valid header
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
    # we set Log.ignore_this_log for older files
    for band in range(1, rules.contest_bands_nr+1):
        for _, _ham in operator_instances.items():
            _logs = _ham.logs_by_band_regexp(rules.contest_band(band)['regexp'])
            mark_older_logs(_logs)

    # do the corss-check over filtered logs
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

    return operator_instances


def crosscheck_logs(operator_instances, rules, band_nr):
    """
    :param operator_instances: dictionary {key=callsign, value=Operator(callsign)}
    :param band_nr: number of contest band
    """
    for callsign1, ham1 in operator_instances.items():
        # set a list for this ham with already made contacts
        _had_qso_with = []
        # get logs for band
        _logs1 = ham1.logs_by_band_regexp(rules.contest_band(band_nr)['regexp'])
        if not _logs1:
            continue

        # use 1st log that : is not checklog , is not to ignore & has valid header
        for log1 in _logs1:
            if all((log1.use_as_checklog is False,
                    log1.ignore_this_log is False,
                    log1.valid_header is True)):
                break
        else:
            continue

        for qso1 in log1.qsos:
            if qso1.valid is False:
                qso1.cc_confirmed = False
                if len(qso1.errors) >= 1:
                    qso1.cc_error = qso1.errors[0][2]
                else:
                    qso1.cc_error = 'Qso is not valid'
                continue

            if qso1.cc_confirmed is True:
                # code should never reach here
                continue

            callsign2 = qso1.qso_fields['call'].upper()

            # validate that this qso isn't an duplicate for current period
            _, inside_period_nr1 = qso1.qso_inside_period()
            if '{}-period{}'.format(callsign2, inside_period_nr1) in _had_qso_with:
                qso1.cc_confirmed = False
                qso1.cc_error = 'Qso already confirmed'
                continue

            # check if we have some logs from 2nd ham
            ham2 = operator_instances.get(callsign2, None)
            if not ham2:
                qso1.cc_confirmed = False
                qso1.cc_error = 'No log from {}'.format(callsign2)
                continue

            # check if we have proper band logs from 2nd ham
            _logs2 = ham2.logs_by_band_regexp(rules.contest_band(band_nr)['regexp'])
            if not _logs2:
                qso1.cc_confirmed = False
                qso1.cc_error = 'No log for this band from {}'.format(callsign2)
                continue

            # use 1st log that : is not to ignore & has valid header
            for log2 in _logs2:
                if all((log2.ignore_this_log is False,
                        log2.valid_header is True)):
                    break
            else:
                qso1.cc_confirmed = False
                qso1.cc_error = 'No valid log from {}'.format(callsign2)
                continue

            # get 2nd ham qsos and compare them with 1st ham qso
            for qso2 in log2.qsos:
                if qso2.valid is False:
                    continue

                _callsign2 = qso2.qso_fields['call'].upper()
                if callsign1 != _callsign2:
                    continue

                _, inside_period_nr2 = qso2.qso_inside_period()
                if inside_period_nr1 != inside_period_nr2:
                    continue

                distance = None
                try:
                    distance = compare_qso(log1, qso1, log2, qso2)
                except ValueError as e:
                    qso1.cc_confirmed = False
                    qso1.cc_error = e

                if distance is None:
                    continue

                # add this qso in _had_qso_with list
                _had_qso_with.append('{}-period{}'.format(callsign2, inside_period_nr2))
                qso1.points = distance * int(rules.contest_band(band_nr)['multiplier'])
                qso1.cc_confirmed = True
                qso1.cc_error = []
                break
            else:
                qso1.cc_confirmed = False
                qso1.cc_error = 'No qso found on {} log'.format(callsign2)


def compare_qso(log1, qso1, log2, qso2):
    """
    Generic comparision of 2 QSO's
    :param qso1:
    :param qso2:
    :return: distance if QSO's are valid or -1/None
    """

    if qso1.valid is False:
        # pass only 1st error message
        raise ValueError(qso1.errors[0][2])

    if qso2.valid is False:
        raise(ValueError('Other ham qso is invalid'))

    # compare callsign
    if log1.callsign != qso2.qso_fields['call'] or log2.callsign != qso1.qso_fields['call']:
        raise ValueError('Callsign mismatch')  # this is never raised

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
    if qso1.qso_fields['rst_sent'] != qso2.qso_fields['rst_recv']:
        raise ValueError('Rst mismatch (other ham)')
    if qso1.qso_fields['rst_recv'] != qso2.qso_fields['rst_sent']:
        raise ValueError('Rst mismatch')

    # compare serial number
    if int(qso1.qso_fields['nr_sent']) != int(qso2.qso_fields['nr_recv']):
        raise ValueError('Serial number mismatch (other ham)')
    if int(qso1.qso_fields['nr_recv']) != int(qso2.qso_fields['nr_sent']):
        raise ValueError('Serial number mismatch')

    # compare qth
    if log1.maidenhead_locator.upper() != qso2.qso_fields['wwl'].upper():
        raise ValueError('Qth locator mismatch (other ham)')
    if log2.maidenhead_locator.upper() != qso1.qso_fields['wwl'].upper():
        raise ValueError('Qth locator mismatch')

    # calculate & return distance
    return qth_distance(log1.maidenhead_locator.upper(), log2.maidenhead_locator.upper())


def mark_older_logs(log_list):
    """
    Will iterate the log list and based on log file timestamp will mark older ones
    by setting the .ignore_this_log flag.
    """
    maxDate = 0
    maxDateLogId = None
    for log in log_list:
        date = os.path.getmtime(log.path)
        if date > maxDate:
            maxDate = date
            maxDateLogId = id(log)
    for log in log_list:
        if maxDateLogId != id(log):
            log.ignore_this_log = True


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


def conv_maidenhead_to_latlong(maiden):
    """
    Will convert he Maidenhead location to Latitude/Longitude location
    """
    long = -180.0 + 20 * delta_ord(maiden[0]) + 2.0 * delta_ord(maiden[2]) + 5.0 * delta_ord(maiden[4]) / 60.0
    lat = -90.0 + 10 * delta_ord(maiden[1]) + 1.0 * delta_ord(maiden[3]) + 2.5 * delta_ord(maiden[5]) / 60.0
    return long, lat


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


def dict_to_json(dictionary):
    return json.dumps(dictionary)


def dict_to_xml(dictionary):
    return dicttoxml(dictionary)
