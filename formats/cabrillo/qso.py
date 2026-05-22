"""
Copyright 2016-2026 Ciorceri Petru Sorin (yo5pjb)

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Cabrillo LogQso class.
"""
import re
from datetime import datetime, timedelta

from .constants import REGEX_CABRILLO_QSO, REGEX_CABRILLO_QSO_13F, normalize_cabrillo_mode


class LogQso(object):
    """
    Keep a single QSO (in Cabrillo format).

    Standard Cabrillo V2/V3 QSO format (space/tab separated):
        QSO: <freq> <mode> <date> <time> <call_sent> <rst_sent> <exch_sent> <call_recv> <rst_recv> <exch_recv> [tx_id]
    """

    REGEX_CABRILLO_QSO = REGEX_CABRILLO_QSO
    REGEX_CABRILLO_QSO_13F = REGEX_CABRILLO_QSO_13F

    def __init__(self, qso_line=None, qso_line_number=None, rules=None):
        self.qso_line = qso_line
        self.line_nr = qso_line_number
        self.rules = rules
        self.valid = True

        self.errors = []
        self.cc_confirmed = None
        self.cc_error = []
        self.points = None

        self.qso_fields = {'freq': None,
                           'date': None,
                           'hour': None,
                           'call': None,
                           'mode': None,
                           'rst_sent': None,
                           'nr_sent': None,
                           'rst_recv': None,
                           'nr_recv': None,
                           'wwl': '',
                           'points': None,
                           'new_exchange': None,
                           'new_wwl': None,
                           'new_dxcc': None,
                           'duplicate_qso': None,
                           }

        self.validate_qso_format()
        if not self.valid:
            return
        self.parse_qso_fields()

        self.generic_qso_validator()
        if not self.valid:
            return

        if self.rules:
            self.rules_based_qso_validator()

    def validate_qso_format(self):
        err = self.regexp_qso_validator(self.qso_line) or None
        if err:
            self.errors.append((self.line_nr, self.qso_line, err))
            self.valid = False

    def parse_qso_fields(self):
        tokens = self.qso_line.strip().split()
        data_tokens = tokens[1:]
        if len(data_tokens) >= 12:
            m = re.match(self.REGEX_CABRILLO_QSO_13F, self.qso_line, re.IGNORECASE)
            if m:
                self._assign_fields_13f(m)
                return
        m = re.match(self.REGEX_CABRILLO_QSO, self.qso_line, re.IGNORECASE)
        if m:
            self._assign_fields(m)

    def _assign_fields(self, m):
        freq = m.group(1)
        mode = m.group(2)
        date_raw = m.group(3)
        hour = m.group(4)
        call_a = m.group(5).upper()
        rst_a = m.group(6)
        exch_a = m.group(7)
        call_b = m.group(8).upper()
        rst_b = m.group(9)
        exch_b = m.group(10)
        t = m.group(11) or ''

        self.qso_fields['freq'] = freq
        self.qso_fields['call'] = call_b
        self.qso_fields['date'] = date_raw[2:4] + date_raw[5:7] + date_raw[8:10]
        self.qso_fields['hour'] = hour
        self.qso_fields['mode'] = normalize_cabrillo_mode(mode)
        self.qso_fields['rst_sent'] = rst_a
        self.qso_fields['nr_sent'] = exch_a
        self.qso_fields['rst_recv'] = rst_b
        self.qso_fields['nr_recv'] = exch_b

    def _assign_fields_13f(self, m):
        freq = m.group(1)
        mode = m.group(2)
        date_raw = m.group(3)
        hour = m.group(4)
        call_a = m.group(5).upper()
        rst_a = m.group(6)
        exch_a = m.group(7)
        call_b = m.group(8).upper()
        rst_b = m.group(9)
        exch_b = m.group(10)
        t = m.group(11) or ''

        self.qso_fields['freq'] = freq
        self.qso_fields['call'] = call_b
        self.qso_fields['date'] = date_raw[2:4] + date_raw[5:7] + date_raw[8:10]
        self.qso_fields['hour'] = hour
        self.qso_fields['mode'] = normalize_cabrillo_mode(mode)
        self.qso_fields['rst_sent'] = rst_a
        self.qso_fields['nr_sent'] = exch_a
        self.qso_fields['rst_recv'] = rst_b
        self.qso_fields['nr_recv'] = exch_b

    @classmethod
    def regexp_qso_validator(cls, line):
        if not line:
            return 'QSO line is empty'
        if not line.upper().startswith('QSO:'):
            return 'QSO line does not start with QSO:'
        m = re.match(cls.REGEX_CABRILLO_QSO, line, re.IGNORECASE)
        if m:
            return None
        m = re.match(cls.REGEX_CABRILLO_QSO_13F, line, re.IGNORECASE)
        if m:
            return None
        return 'Incorrect QSO line format'

    def generic_qso_validator(self):
        try:
            datetime.strptime(self.qso_fields['date'], '%y%m%d')
        except ValueError as why:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line, 'Qso date is invalid: {}'.format(str(why))))

        try:
            datetime.strptime(self.qso_fields['hour'], '%H%M')
        except ValueError as why:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line, 'Qso hour is invalid: {}'.format(str(why))))

        re_call = r'^\w+/?\w+$'
        result = re.match(re_call, self.qso_fields['call'])
        if not result:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line,
                                'Callsign is invalid: {}'.format(self.qso_fields['call'])))

        if not self.qso_fields['mode']:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line,
                                'Qso mode is invalid: {}'.format(self.qso_fields['mode'])))

        re_rst = r'^[1-5][1-9][1-9]?[aAsS]?$'
        result = re.match(re_rst, self.qso_fields['rst_sent'])
        if not result:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line,
                                'Rst is invalid: {}'.format(self.qso_fields['rst_sent'])))
        result = re.match(re_rst, self.qso_fields['rst_recv'])
        if not result:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line,
                                'Rst is invalid: {}'.format(self.qso_fields['rst_recv'])))

        re_exchange = r'^\w{1,6}$'
        re_exchange_combined = r'^\w{1,6}\s+\w{1,6}$'
        result = re.match(re_exchange, self.qso_fields['nr_sent'])
        if not result:
            result = re.match(re_exchange_combined, self.qso_fields['nr_sent'])
        if not result:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line,
                                'Sent exchange is invalid: {}'.format(self.qso_fields['nr_sent'])))
        result = re.match(re_exchange, self.qso_fields['nr_recv'])
        if not result:
            result = re.match(re_exchange_combined, self.qso_fields['nr_recv'])
        if not result:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line,
                                'Received exchange is invalid: {}'.format(self.qso_fields['nr_recv'])))

    def rules_based_qso_validator(self):
        if self.rules is None:
            return

        if self.qso_fields['mode'] not in self.rules.contest_qso_modes:
            self.valid = False
            modes_str = ','.join(self.rules.contest_qso_modes)
            self.errors.append((self.line_nr,
                                self.qso_line,
                                'Qso mode is invalid: not in defined modes ({})'.format(modes_str)))

        if self.qso_fields['date'] < self.rules.contest_begin_date[2:]:
            self.valid = False
            self.errors.append((self.line_nr,
                                self.qso_line,
                                'Qso date is invalid: before contest starts (<{})'.format(
                                    self.rules.contest_begin_date[2:])))
        if self.qso_fields['date'] > self.rules.contest_end_date[2:]:
            self.valid = False
            self.errors.append((self.line_nr,
                                self.qso_line,
                                'Qso date is invalid: after contest ends (>{})'.format(
                                    self.rules.contest_end_date[2:])))

        if self.qso_fields['date'] == self.rules.contest_begin_date[2:] and \
           self.qso_fields['hour'] < self.rules.contest_begin_hour:
            self.valid = False
            self.errors.append((self.line_nr,
                                self.qso_line,
                                'Qso hour is invalid: before contest start hour (<{})'.format(
                                    self.rules.contest_begin_hour)))
        if self.qso_fields['date'] == self.rules.contest_end_date[2:] and \
           self.qso_fields['hour'] > self.rules.contest_end_hour:
            self.valid = False
            self.errors.append((self.line_nr,
                                self.qso_line,
                                'Qso hour is invalid: after contest end hour (>{})'.format(
                                    self.rules.contest_end_hour)))

        inside_period, _ = self.qso_inside_period()
        if not inside_period:
            self.valid = False
            self.errors.append((self.line_nr,
                                self.qso_line,
                                'Qso date/hour is invalid: not inside contest periods'))

    def qso_inside_period(self):
        if not self.rules:
            return True, None

        for period in range(1, self.rules.contest_periods_nr + 1):
            if not (self.rules.contest_period(period)['begindate'][2:] <= self.qso_fields['date'] <=
                    self.rules.contest_period(period)['enddate'][2:]):
                continue
            _enddate = datetime.strptime(self.rules.contest_period(period)['enddate'], '%Y%m%d')
            _begindate = datetime.strptime(self.rules.contest_period(period)['begindate'], '%Y%m%d')
            delta_days = _enddate - _begindate
            if delta_days == timedelta(0) and \
               self.rules.contest_period(period)['beginhour'] <= self.qso_fields['hour'] <= \
               self.rules.contest_period(period)['endhour']:
                return True, period
            elif delta_days > timedelta(0):
                if self.rules.contest_period(period)['begindate'][2:] == self.qso_fields['date'] and \
                   self.rules.contest_period(period)['beginhour'] <= self.qso_fields['hour']:
                    return True, period
                if self.qso_fields['date'] == self.rules.contest_period(period)['enddate'][2:] and \
                   self.qso_fields['hour'] <= self.rules.contest_period(period)['endhour']:
                    return True, period
                if self.rules.contest_period(period)['begindate'][2:] < self.qso_fields['date'] < \
                   self.rules.contest_period(period)['enddate'][2:]:
                    return True, period
        return False, None
