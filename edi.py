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

import re
from collections import namedtuple
from datetime import datetime


class Operator(object):
    """
    This will keep the info & logs for each ham operator (team)
    """
    callsign = None
    info = {}
    logs = []

    def __init__(self, callsign):
        self.callsign = callsign
        self.logs = []

    def add_log(self, path):
        self.logs.append(Log(path))


class Log(object):
    """
    This will keep a single log information (header + list of LogQso instances)
    """
    path = None
    log_content = None  # full content of the log
    callsign = None
    maidenhead_locator = None
    band = None
    section = None
    qsos_tuple = namedtuple('qso_tuple', ['linenr', 'qso', 'valid', 'error'])
    qsos = []   # list with LogQso instances

    def __init__(self, path, checklog=False):
        self.path = path
        self.log_content = self.read_file_content(self.path)

        # _temp = self.get_field('PCall')
        # if _temp is None:
        #     raise ValueError('The PCall field is not present')
        # if len(_temp) > 1:
        #     raise ValueError('The PCall field is present multiple times')
        # self.callsign = _temp[0]

        self.qsos = []
        self.get_qsos()

    def read_file_content(self, path):
        try:
            with open(self.path, 'r') as f:
                content = f.readlines()
        except IOError as why:
            raise
        except Exception as why:
            raise
        return content

    def validate_log_content(self):
        pass

    def get_field(self, field):
        """
        Will read the log_content and will return field value
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
        Will read the log_content and will return a list of LogQso
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
                LogQso(qso[1], qso[0])
            )

    def dump_summary(self):
        """
        Based on the output format (text, html...) this will output a summary of the log
        """
        pass


class LogQso(object):
    """
    This will keep a single QSO
    """
    regexMinimalQsoCheck = '(?P<date>.*?);(?P<hour>.*?);(?P<call>.*?);(?P<mode>.*?);' \
                           '(?P<rst_sent>.*?);(?P<nr_sent>.*?);(?P<rst_recv>.*?);(?P<nr_recv>.*?);' \
                           '(?P<exchange_recv>.*?);(?P<wwl>.*?);(?P<points>.*?);' \
                           '(?P<new_exchange>.*?);(?P<new_wwl>.*?);(?P<new_dxcc>.*?);(?P<duplicate_qso>.*?)'
    regexMediumQsoCheck = '^\d{6};\d{4};.*?;\d;\d{2,3}.?;\d{2,4};\d{2,3}.?;\d{2,4};.*?;.*?;.*?;.*?;.*?;.*?;.*?'
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

        # validate RST format
        reRST = "^[1-5][1-9][aA]?$"
        result = re.match(reRST, self.qsoFields['rst_sent'])
        if not result:
            return 'RST is invalid: %s' % (self.qsoFields['rst_sent'])
        result = re.match(reRST, self.qsoFields['rst_recv'])
        if not result:
            return 'RST is invalid: %s' % (self.qsoFields['rst_recv'])

        # validate QTH locator format
        rePWWLo = "^\s*([a-rA-R]{2}\d{2}[a-xA-X]{2})\s*$"
        result = re.match(rePWWLo, self.qsoFields['wwl'], re.IGNORECASE)
        if not result:
            return 'Qso WWL is invalid'

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

        # validate qso hour
        if self.qsoFields['date'] == rules.contest_begin_date[2:] and \
           self.qsoFields['hour'] < rules.contest_begin_hour:
            return 'Qso hour is invalid: before contest start hour (<%s)' % rules.contest_begin_hour
        if self.qsoFields['date'] == rules.contest_end_date[2:] and \
           self.qsoFields['hour'] > rules.contest_end_hour:
            return 'Qso hour is invalid: after contest end hour (>%s)' % rules.contest_end_hour

        # validate qso mode
        # TODO: I have to add 'modes' in rules.py


class LogException(Exception):
    def __init__(self, message, line):
        self.message = message
        self.line = line
