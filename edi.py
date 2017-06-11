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
from collections import namedtuple
from datetime import datetime


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
        if _callsign is None:
            raise ValueError('The PCall field is not present')
        if len(_callsign) > 1:
            raise ValueError('The PCall field is present multiple times')
        self.callsign = _callsign[0]

        # get & validate maidenhead locator
        _qthlocator = self.get_field('PWWLo')
        if _qthlocator is None:
            raise ValueError('The PWWLo field is not present')
        if len(_qthlocator) > 1:
            raise ValueError('The PWWLo field is present multiple times')
        if not self.validate_qth_locator(_qthlocator[0]):
            raise ValueError('The PWWLo field value is not valid')
        self.maidenhead_locator = _qthlocator

        # get & validate band based on generic rules and by custom rules if provided (rules.contest_band['regexp'])
        # TODO : rule validation
        _band = self.get_field('PBand')
        if _band is None:
            raise ValueError('The PBand field is not present')
        if len(_band) > 1:
            raise ValueError('The PBand field is present muliple times')
        if not self.validate_band(_band[0]):
            raise ValueError('The PBand field value is not valids')
        self.band = _band

        # get & validate PSect based on generic rules and by custom rules if provided (rules.contest_category['regexp']
        # TODO : both

        # get & validate TDate based on generic rules format and by custom rules if provided (rules.contest_begin_date & rules.contest_end_date)
        # TODO : both



        self.qsos = []
        self.get_qsos()

    @staticmethod
    def read_file_content(path):
        try:
            with open(path, 'r') as f:
                content = f.readlines()
        except IOError as why:
            raise
        except Exception as why:
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
        return value or None

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
        regexMaidenhead = '^\s*([a-rA-R]{2}\d{2}[a-xA-X]{2})\s*$'

        res = re.match(regexMaidenhead, qth, re.IGNORECASE)
        return True if res else False

    @staticmethod
    def get_band(band):
        """
        This will parse the 'PBand=' field content
        and return the proper band
        :param band: the content of 'PBand=' field
        :return: The detected band (144,432,1296) or None
        """

        regexpBand = {144: ['144.*', '145.*'],
                      432: ['430.*', '432.*', '435.*'],
                      1296: ['1296.*', '1[.,][23].*']}
        for _band in regexpBand:
            for regexp in regexpBand[_band]:
                res = re.match(regexp, band)
                if res:
                    return _band
        return None

    # TODO: this will be deprecated, I should remove it in the future
    @staticmethod
    def validate_band(band):
        """
        This will validate PBand based on generic rules
        """
        validated = False
        regexpBandCheck = ['144.*', '145.*',
                           '430.*', '432.*', '435.*',
                           '1296.*', '1[.,][23].*']
        for _regex in regexpBandCheck:
            res = re.match(_regex, band)
            if res:
                validated = True

        return validated

    def rules_based_validate_band(self, band, rules):
        """
        This will validate PBand based on Rules class instance
        """
        validated = False

        if rules is None:
            raise ValueError('TODO : nu avem rules ! tre fixat cum se da eroarea !')

        for _nr in range(rules.contest_bands_nr):
            _regex = '^\s*(' + rules.contest_band(_nr)['regexp'] + ')\s*$'
            res = re.match(_regex, band)
            if res:
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
    regexMediumQsoCheck = '^\d{6};\d{4};.*?;\d;\d{2,3}.?;\d{2,4};\d{2,3}.?;\d{2,4};.*?;[a-zA-Z]{2}\d{2}[a-zA-Z]{2};' \
                          '.*?;.*?;.*?;.*?;.*?'
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
            # TODO : make this qso validator smarter ! This .. or .. or is useless !
            self.error_message = self.generic_qso_validator() or self.rules_based_qso_validator(rules) or None

    def qso_parser(self):
        """
        This should parse a qso based on log format
        """
        res = re.match(self.regexMinimalQsoCheck, self.qso_line)
        if res:
            for key in self.qsoFields.keys():
                self.qsoFields[key] = res.group(key)

    @classmethod
    def regexp_qso_validator(cls, line):
        """
        This will validate the a line of qso from .edi log
        :param line:
        :return: None or error message
        """
        qso_min_line_lenght = 40

        if len(line) < qso_min_line_lenght:
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
            datetime.strptime(self.qsoFields['date'], '%y%m%d')
        except ValueError as e:
            return 'Qso date is invalid: %s' % (str(e))

        # validate time format
        try:
            datetime.strptime(self.qsoFields['hour'], '%H%M')
        except ValueError as e:
            return 'Qso hour is invalid: %s' % (str(e))

        # validate callsign format
        # TODO

        # validate mode format
        # TODO

        # validate RST (sent & recv) format
        reRST = "^[1-5][1-9][aA]?$"
        result = re.match(reRST, self.qsoFields['rst_sent'])
        if not result:
            return 'RST is invalid: %s' % (self.qsoFields['rst_sent'])
        result = re.match(reRST, self.qsoFields['rst_recv'])
        if not result:
            return 'RST is invalid: %s' % (self.qsoFields['rst_recv'])

        # validate NR (sent & recv) format
        # TODO

        # validate 'exchange_recv' format
        # TODO

        # validate QTH locator format
        if not Log.validate_qth_locator(self.qsoFields['wwl']):
            return 'Qso WWL is invalid'

        # validate 'duplicate_qso' format
        # TODO

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
            return 'Qso date is invalid: before contest starts (<%s)' % rules.contest_begin_date[2:]
        if self.qsoFields['date'] > rules.contest_end_date[2:]:
            return 'Qso date is invalid: after contest ends (>%s)' % rules.contest_end_date[2:]

        # TODO : validate qso date based on period (if exists !)

        # validate qso hour
        if self.qsoFields['date'] == rules.contest_begin_date[2:] and \
           self.qsoFields['hour'] < rules.contest_begin_hour:
            return 'Qso hour is invalid: before contest start hour (<%s)' % rules.contest_begin_hour
        if self.qsoFields['date'] == rules.contest_end_date[2:] and \
           self.qsoFields['hour'] > rules.contest_end_hour:
            return 'Qso hour is invalid: after contest end hour (>%s)' % rules.contest_end_hour

        # TODO : validate qso hour based on period (if exists !)

        # validate qso mode
        # TODO: I have to add 'modes' in rules.py


class LogException(Exception):
    def __init__(self, message, line):
        self.message = message
        self.line = line
