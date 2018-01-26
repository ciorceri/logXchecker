"""
Copyright 2016-2017 Ciorceri Petru Sorin

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

import re
import datetime
from collections import namedtuple


class Operator(object):
    """
    Keep operator callsign, info and logs path
    """
    callsign = None
    info = {}           # no idea what was this for :(
    logs = []           # list with Log() instances

    def __init__(self, callsign):
        self.callsign = callsign
        self.logs = []

    def add_log(self, path):
        self.logs.append(Log(path))


class Log(object):
    """
    Keep a single EDI log information:
    log path, log raw content, callsign, qth, band, section, qsos tuple (raw content)
    and a list with LogQso() instances
    """
    path = None
    log_content = None  # a list with log lines
    callsign = None
    maidenhead_locator = None
    band = None
    section = None
    qsos_tuple = namedtuple('qso_tuple', ['linenr', 'qso', 'valid', 'error'])
    qsos = []   # list with LogQso instances

    def __init__(self, path, rules=None, checklog=False):
        self.path = path
        self.log_content = self.read_file_content(self.path)

        # get & validate callsign
        _callsign = self.get_field('PCall')
        if not _callsign:
            raise ValueError('The PCall field is not present')
        if len(_callsign) > 1:
            raise ValueError('The PCall field is present multiple times')
        self.callsign = _callsign[0]

        # get & validate maidenhead locator
        _qthlocator = self.get_field('PWWLo')
        if not _qthlocator:
            raise ValueError('The PWWLo field is not present')
        if len(_qthlocator) > 1:
            raise ValueError('The PWWLo field is present multiple times')
        if not self.validate_qth_locator(_qthlocator[0]):
            raise ValueError('The PWWLo field value is not valid')
        self.maidenhead_locator = _qthlocator

        # get & validate band based on generic rules and by custom rules if provided (rules.contest_band['regexp'])
        _band = self.get_field('PBand')
        if not _band:
            raise ValueError('The PBand field is not present')
        if len(_band) > 1:
            raise ValueError('The PBand field is present multiple times')
        if not rules and not self.validate_band(_band[0]):
            raise ValueError('The PBand field value is not valid')
        elif rules and not self.rules_based_validate_band(_band[0], rules):
            raise ValueError('The PBand field value has an invalid value ({}). Not as defined in contest '
                             'rules'.format(_band[0]))
        self.band = _band

        # get & validate PSect based on generic rules and by custom rules if provided (rules.contest_category['regexp']
        _section = self.get_field('PSect')
        if not _section:
            raise ValueError('The PSect field is not present')
        if len(_section) > 1:
            raise ValueError('The PSect field is present multiple times')
        if not rules and not self.validate_section(_section[0]):
            raise ValueError('The PSect field value is not valid')
        elif rules and not self.rules_based_validate_section(_section[0], rules):
            raise ValueError('The PSect field value has an invalid value ({}). Not as defined in contest '
                             'rules'.format(_section[0]))
        self.section = _section

        # get & validate TDate based on generic rules format and by custom rules if provided
        # (rules.contest_begin_date & rules.contest_end_date)
        _date = self.get_field('TDate')
        if not _date:
            raise ValueError('The TDate field is not present')
        if len(_date) > 1:
            raise ValueError('The TDate field is present multiple times')
        if not self.validate_date(_date[0]):
            raise ValueError('The TDate field value is not valid ({})'.format(_date[0]))
        if rules and not self.rules_based_validate_date(_date[0], rules):
            raise ValueError('The TDate field value has an invalid value ({}). Not as defined in contest '
                             'rules'.format(_date[0]))

        self.qsos = []
        self.get_qsos()

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

    def validate_log_content(self):
        # TODO: to see later if we have to do a generic validation or not
        pass

    def get_field(self, field):
        """
        Will read the log_content and will return field value in a list
        """

        if self.log_content is None:
            raise FileNotFoundError("Log content is not available")

        value = []
        _field = str(field).upper() + '='
        for line in self.log_content:
            if line.upper().startswith(_field):
                value.append(line.split('=', 1)[1].strip())
        return value

    def get_qsos(self):
        """
        Will read the self.log_content and will return a list of LogQso
        """
        qso_record_start = "[QSORECORDS"
        qso_record_end = "[END;"
        qso_lines = []
        do_read_qso = False

        # read qso lines
        for (index, line) in enumerate(self.log_content):
            if line.upper().startswith(qso_record_start):
                do_read_qso = True
                continue
            if line.upper().startswith(qso_record_end):
                do_read_qso = False
                continue
            if do_read_qso:
                qso_lines.append((index, line.strip()))

        # validate qso lines
        for qso in qso_lines:
            message = LogQso.regexp_qso_validator(qso[1])
            self.qsos.append(
                # self.qsos_tuple(linenr=qso[0], qso=qso[1], valid=False if message else True, error=message)
                LogQso(qso[1], qso[0])  # LogQso(qso_line, qso_line_number_in_log)
            )

    @staticmethod
    def validate_qth_locator(qth):
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

        regexp_band = {144: ['144.*', '145.*'],
                       432: ['430.*', '432.*', '435.*'],
                       1296: ['1296.*', '1[.,][23].*']}
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
        validated = False

        regexp_band_check = ['144.*', '145.*',
                             '430.*', '432.*', '435.*',
                             '1296.*', '1[.,][23].*']
        for _regex in regexp_band_check:
            res = re.match(_regex, band_value)
            if res:
                validated = True
        return validated

    @staticmethod
    def rules_based_validate_band(band_value, rules):
        """
        This will validate PBand based on Rules class instance
        """
        validated = False

        if rules is None:
            raise ValueError('No contest rules provided !')
        for _nr in range(1, rules.contest_bands_nr+1):
            _regex = r'\s*(' + rules.contest_band(_nr)['regexp'] + r')\s*'
            res = re.match(_regex, band_value)
            if res:
                validated = True
        return validated

    @staticmethod
    def validate_section(section_value):
        """
        This will validate PSect based on generic rules
        """
        validated = False

        regexpSectCheck = ['.*SOSB.*', '.*SOMB.*', '.*Single.*', '^SO$',
                           '.*MOSB.*', '.*MOMB.*', '.*Multi.*', '^MO$',
                           'check', 'checklog', 'check log']
        for _regex in regexpSectCheck:
            res = re.match(_regex, section_value, re.IGNORECASE)
            if res:
                validated = True
        return validated

    @staticmethod
    def rules_based_validate_section(section_value, rules):
        """
        This will validate PSect based on Rules class instance
        """
        validated = False

        if rules is None:
            raise ValueError('No contest rules provided !')
        for _nr in range(1, rules.contest_categories_nr+1):
            _regex = r'\s*(' + rules.contest_category(_nr)['regexp'] + r')\s*'
            res = re.match(_regex, section_value, re.IGNORECASE)
            if res:
                validated = True
        return validated

    @staticmethod
    def validate_date(date_value):
        """
        This will validate TDate based on generic rules
        """
        validated = False
        dates = date_value.split(';')
        if len(dates) != 2:
            return validated
        for _date in dates:
            try:
                datetime.datetime.strptime(_date, '%Y%m%d')
                validated = True
            except ValueError:
                break
        return validated

    def rules_based_validate_date(self, date_value, rules):
        """
        This will validate TDate based on Ruless class instance
        """
        validated = False

        if rules is None:
            raise ValueError('No contest rules provided !')
        _begin_date, _end_date = date_value.split(';')
        if _begin_date == rules.contest_begin_date and _end_date == rules.contest_end_date:
            validated = True
        return validated

    def dump_summary(self):
        """
        Based on the output format (text, html...) this will output a summary of the log
        """
        pass


class LogQso(object):
    """
    Keep a single QSO (in EDI format) and some info:
    qso line number, raw qso, is valid ? , error message if !valid, all qso fields
    """
    regexMinimalQsoCheck = '(?P<date>.*?);(?P<hour>.*?);(?P<call>.*?);(?P<mode>.*?);' \
                           '(?P<rst_sent>.*?);(?P<nr_sent>.*?);(?P<rst_recv>.*?);(?P<nr_recv>.*?);' \
                           '(?P<exchange_recv>.*?);(?P<wwl>.*?);(?P<points>.*?);' \
                           '(?P<new_exchange>.*?);(?P<new_wwl>.*?);(?P<new_dxcc>.*?);(?P<duplicate_qso>.*?)'
    regexMediumQsoCheck = r'^\d{6};\d{4};.*?;.?;\d{2,3}.?;\d{2,4};\d{2,3}.?;\d{2,4};.*?;' \
                          '[a-zA-Z]{2}\d{2}[a-zA-Z]{2};.*?;.*?;.*?;.*?;.*?'
    #                       date  time   id  m    rst       nr      rst       nr    .  qth  km  .   .   .   .

    qso_line_number = 0
    qso_line = None
    valid_qso = False
    error_message = None

    qsoFields = {'date': None,
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

    def __init__(self, qso_line, qso_line_number, rules=None):
        self.qso_line = qso_line
        self.qso_line_number = qso_line_number
        self.error_message = self.regexp_qso_validator(qso_line) or None
        self.valid_qso = False if self.error_message else True

        if self.valid_qso:
            self.qso_parser()
            self.error_message = self.generic_qso_validator()
            if (self.error_message is None) and (rules is not None):
                self.error_message = self.rules_based_qso_validator(rules)
            self.valid_qso = False if self.error_message else True

    def qso_parser(self):
        """
        This should parse a qso based on log format
        """
        res = re.match(self.regexMinimalQsoCheck, self.qso_line)
        if res:
            for key in self.qsoFields:
                self.qsoFields[key] = res.group(key)

    @classmethod
    def regexp_qso_validator(cls, line):
        """
        This will validate the a line of qso from .edi log
        :param line:
        :return: None or error message
        """
        qso_min_line_length = 40

        if len(line) < qso_min_line_length:
            return 'QSO line is too short'
        res = re.match(cls.regexMinimalQsoCheck, line)
        if not res:
            return 'Minimal QSO checks didn\'t pass'
        res = re.match(cls.regexMediumQsoCheck, line)
        if not res:
            return 'QSO checks didn\'t pass'
        return None

    def generic_qso_validator(self):
        """
        This will validate a parsed qso based on generic rules
        :return:
        """

        # validate date format
        try:
            datetime.datetime.strptime(self.qsoFields['date'], '%y%m%d')
        except ValueError as why:
            return 'Qso date is invalid: {}'.format(str(why))

        # validate time format
        try:
            datetime.datetime.strptime(self.qsoFields['hour'], '%H%M')
        except ValueError as why:
            return 'Qso hour is invalid: {}'.format(str(why))

        # validate callsign format
        re_call = r'^\w+/?\w+$'
        result = re.match(re_call, self.qsoFields['call'])
        if not result:
            return 'Callsign is invalid: {}'.format(self.qsoFields['call'])

        # validate mode format
        re_mode = "^[0-9]$"
        result = re.match(re_mode, self.qsoFields['mode'])
        if not result:
            return 'QSO mode is invalid: {}'.format(self.qsoFields['mode'])

        # validate RST (sent & recv) format
        re_rst = "^[1-5][1-9][aA]?$"
        result = re.match(re_rst, self.qsoFields['rst_sent'])
        if not result:
            return 'RST is invalid: {}'.format(self.qsoFields['rst_sent'])
        result = re.match(re_rst, self.qsoFields['rst_recv'])
        if not result:
            return 'RST is invalid: {}'.format(self.qsoFields['rst_recv'])

        # validate NR (sent & recv) format
        re_sent_recv_nr = r'^\d{1,4}$'
        result = re.match(re_sent_recv_nr, self.qsoFields['nr_sent'])
        if not result:
            return 'Sent Qso number is invalid: {}'.format(self.qsoFields['nr_sent'])
        result = re.match(re_sent_recv_nr, self.qsoFields['nr_recv'])
        if not result:
            return 'Received Qso number is invalid: {}'.format(self.qsoFields['nr_recv'])

        # validate 'exchange_recv' format
        re_exchange = r'^\w{0,6}$'
        result = re.match(re_exchange, self.qsoFields['exchange_recv'])
        if not result:
            return 'Received exchange is invalid: {}'.format(self.qsoFields['exchange_recv'])

        # validate QTH locator format
        if not Log.validate_qth_locator(self.qsoFields['wwl']):
            return 'Qso WWL is invalid: {}'.format(self.qsoFields['wwl'])

        # validate 'duplicate_qso' format
        # TODO
        return None

    def rules_based_qso_validator(self, rules):
        """
        This will validate the self.qsoFields based on Rules class instance
        :param rules:
        :return:
        """
        if rules is None:
            return

        # validate qso date
        if self.qsoFields['date'] < rules.contest_begin_date[2:]:
            return 'Qso date is invalid: before contest starts (<{})'.format(rules.contest_begin_date[2:])
        if self.qsoFields['date'] > rules.contest_end_date[2:]:
            return 'Qso date is invalid: after contest ends (>{})'.format(rules.contest_end_date[2:])

        # validate qso hour
        if self.qsoFields['date'] == rules.contest_begin_date[2:] and \
           self.qsoFields['hour'] < rules.contest_begin_hour:
            return 'Qso hour is invalid: before contest start hour (<{})'.format(rules.contest_begin_hour)
        if self.qsoFields['date'] == rules.contest_end_date[2:] and \
           self.qsoFields['hour'] > rules.contest_end_hour:
            return 'Qso hour is invalid: after contest end hour (>{})'.format(rules.contest_end_hour)

        # validate date & hour based on period
        inside_period = False
        for period in range(1, rules.contest_periods_nr + 1):
            # if date is not in period, check next period
            if not (rules.contest_period(period)['begindate'][2:] <= self.qsoFields['date'] <= rules.contest_period(period)['enddate'][2:]):
                continue
            _enddate = datetime.datetime.strptime(rules.contest_period(period)['enddate'], '%Y%m%d')
            _begindate = datetime.datetime.strptime(rules.contest_period(period)['begindate'], '%Y%m%d')
            delta_days = _enddate - _begindate
            # if period is in same day
            if delta_days == datetime.timedelta(0) and \
               rules.contest_period(period)['beginhour'] <= self.qsoFields['hour'] <= rules.contest_period(period)['endhour']:
                    inside_period = True
                    break
            # if period is in multiple days
            elif delta_days > datetime.timedelta(0):
                if rules.contest_period(period)['begindate'][2:] == self.qsoFields['date'] and \
                                rules.contest_period(period)['beginhour'] <= self.qsoFields['hour']:
                    inside_period = True
                    break
                if self.qsoFields['date'] == rules.contest_period(period)['enddate'][2:] and \
                                self.qsoFields['hour'] <= rules.contest_period(period)['endhour']:
                    inside_period = True
                    break
                # if begin_period < qso_date < end_period
                if rules.contest_period(period)['begindate'][2:] < self.qsoFields['date'] < rules.contest_period(period)['enddate'][2:]:
                    inside_period = True
                    break
        if not inside_period:
            return 'Qso date/hour is invalid: not inside contest periods'

        # validate qso mode
        if int(self.qsoFields['mode']) not in rules.contest_qso_modes:
            return 'Qso mode is invalid: not in defined modes ({})'.format(rules.contest_qso_modes)

        return None


class LogException(Exception):
    def __init__(self, message, line):
        self.message = message
        self.line = line
