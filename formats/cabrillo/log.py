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

Cabrillo Log class.
"""
import re
from datetime import datetime

from constants import ERR_IO, ERR_HEADER, ERR_QSO


class Log(object):
    """
    Keep a single Cabrillo log information.

    Supports both V2 (whitespace-separated) and V3 (semicolon-separated) QSO lines.
    """
    qsos_tuple = None

    def __init__(self, path, rules=None, checklog=False):
        self.use_as_checklog = checklog
        self.ignore_this_log = False
        self.path = path
        self.rules = rules
        self.log_lines = None
        self.valid_header = None
        self.valid_qsos = None
        self.errors = {ERR_IO: [],
                       ERR_HEADER: [],
                       ERR_QSO: []}
        self.callsign = None
        self.maidenhead_locator = None
        self.band = None
        self.category = None
        self.category_raw = None
        self.date = None
        self.email = None
        self.address = None
        self.name = None
        self.qsos = []
        self.qsos_points = None
        self.qsos_confirmed = None

        self._cabrillo_version = None

        self.validate_header()
        if not self.valid_header:
            return

        self.get_qsos()
        self.valid_qsos = True
        for qso in self.qsos:
            if qso.errors:
                self.errors[ERR_QSO].extend(qso.errors)
                self.valid_qsos = False

    @staticmethod
    def read_file_content(path):
        with open(path, 'r') as _file:
            content = _file.readlines()
        return content

    def validate_header(self):
        self.valid_header = False

        try:
            self.log_lines = self.read_file_content(self.path)
        except Exception as e:
            self.errors[ERR_IO].append((None, 'Cannot read Cabrillo log. Error: {}'.format(e)))
            return

        if len(self.log_lines) == 0:
            self.errors[ERR_IO].append((None, 'Log is empty'))
            return

        first_line = self.log_lines[0].strip()
        m = re.match(r'^START-OF-LOG:\s*(\d+\.\d+)', first_line, re.IGNORECASE)
        if not m:
            self.errors[ERR_HEADER].append((1, 'Missing or invalid START-OF-LOG header'))
            return
        self._cabrillo_version = m.group(1)
        if self._cabrillo_version not in ('2.0', '3.0'):
            self.errors[ERR_HEADER].append((1, 'Unsupported Cabrillo version: {}'.format(self._cabrillo_version)))
            return

        header_data = self._parse_cabrillo_header()
        if not header_data:
            return

        cs = header_data.get('callsign')
        if not cs:
            self.errors[ERR_HEADER].append((None, 'CALLSIGN field is not present'))
        else:
            if not self.validate_callsign(cs):
                self.errors[ERR_HEADER].append((None, 'CALLSIGN field content is not valid: {}'.format(cs)))
            else:
                self.callsign = cs.upper()

        cb = header_data.get('category_band', '').upper()
        if not cb:
            self.errors[ERR_HEADER].append((None, 'CATEGORY-BAND field is not present'))
        else:
            self.band = cb

        co = header_data.get('category_operator', '').upper()
        if not co:
            self.errors[ERR_HEADER].append((None, 'CATEGORY-OPERATOR field is not present'))
        else:
            self.category_raw = co
            if self.rules:
                _res, _cat = self.rules_based_validate_category(self.category_raw, self.rules)
                self.category = _cat
            else:
                _res, _cat = self.validate_category(self.category_raw)
                self.category = _cat

        self.date = self.rules.contest_begin_date if self.rules else None

        gl = header_data.get('grid_locator', '')
        if gl and self.validate_qth_locator(gl):
            self.maidenhead_locator = gl.upper()

        self.email = header_data.get('email', None)
        self.name = header_data.get('name', None)
        self.address = header_data.get('address', None)

        if all((self.callsign, self.band, self.category)):
            self.valid_header = True

    def _parse_cabrillo_header(self):
        data = {}
        for line in self.log_lines:
            stripped = line.strip()
            if stripped.upper().startswith('QSO:'):
                break
            if stripped.upper().startswith('END-OF-LOG:'):
                break
            if ':' in stripped:
                key, _, value = stripped.partition(':')
                key_upper = key.strip().upper()
                value = value.strip()

                if key_upper == 'CALLSIGN':
                    data['callsign'] = value
                elif key_upper == 'CATEGORY-OPERATOR':
                    data['category_operator'] = value
                elif key_upper == 'CATEGORY-BAND':
                    data['category_band'] = value
                elif key_upper == 'CATEGORY-MODE':
                    data['category_mode'] = value
                elif key_upper == 'CATEGORY-POWER':
                    data['category_power'] = value
                elif key_upper == 'EMAIL':
                    data['email'] = value
                elif key_upper == 'GRID-LOCATOR':
                    data['grid_locator'] = value
                elif key_upper == 'NAME':
                    data['name'] = value
                elif key_upper == 'ADDRESS':
                    data['address'] = value
                elif key_upper == 'OPERATORS':
                    data['operators'] = value
                elif key_upper == 'CONTEST':
                    data['contest'] = value
                elif key_upper == 'LOCATION':
                    data['location'] = value
                elif key_upper == 'CLUB':
                    data['club'] = value
                elif key_upper == 'CREATED-BY':
                    data['created_by'] = value
                elif key_upper == 'CLAIMED-SCORE':
                    data['claimedsorce'] = value
                elif key_upper == 'SOAPBOX':
                    data['soapbox'] = value
                elif key_upper == 'CATEGORY-ASSISTED':
                    data['category_assisted'] = value
                elif key_upper == 'CATEGORY-STATION':
                    data['category_station'] = value
                elif key_upper == 'CATEGORY-TIME':
                    data['category_time'] = value
                elif key_upper == 'CATEGORY-TRANSMITTER':
                    data['category_transmitter'] = value
                elif key_upper == 'CATEGORY-OVERLAY':
                    data['category_overlay'] = value

                if key_upper == 'CATEGORY':
                    parts = value.split(':', 1)
                    if len(parts) == 2:
                        sub_key = parts[0].strip().lower()
                        sub_val = parts[1].strip()
                        if sub_key == 'operator':
                            data['category_operator'] = sub_val
                        elif sub_key == 'band':
                            data['category_band'] = sub_val
                        elif sub_key == 'mode':
                            data['category_mode'] = sub_val
                        elif sub_key == 'power':
                            data['category_power'] = sub_val
                        elif sub_key == 'assisted':
                            data['category_assisted'] = sub_val
                        elif sub_key == 'station':
                            data['category_station'] = sub_val
                        elif sub_key == 'transmitter':
                            data['category_transmitter'] = sub_val
                        elif sub_key == 'overlay':
                            data['category_overlay'] = sub_val
                        elif sub_key == 'time':
                            data['category_time'] = sub_val
        return data

    def get_qsos(self):
        from .qso import LogQso

        qso_lines = []
        for index, line in enumerate(self.log_lines):
            stripped = line.strip()
            if stripped.upper().startswith('QSO:'):
                qso_lines.append((index + 1, stripped))

        self.qsos = []
        for line_nr, qso_line in qso_lines:
            self.qsos.append(LogQso(qso_line, line_nr, self.rules))

    def get_field(self, field):
        return None, None

    @staticmethod
    def validate_callsign(callsign):
        if not callsign:
            return False
        regex_pcall = r'^\s*(\w+\/{1})?(\w+[0-9]+)\w+(\/?)\w*\s*$'
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
    def validate_band(band_value):
        if not band_value:
            return False
        return True

    @staticmethod
    def rules_based_validate_band(band_value, rules):
        if not band_value:
            return False
        if rules is None:
            raise ValueError('No contest rules provided!')
        for _nr in range(1, rules.contest_bands_nr + 1):
            _regex = r'\s*(' + rules.contest_band(_nr)['regexp'] + r')\s*'
            res = re.match(_regex, band_value, re.IGNORECASE)
            if res:
                return True
        return False

    @staticmethod
    def validate_category(category_value):
        if not category_value:
            return False, None
        regexp_categories = {
            'single': ['.*SINGLE.*', '.*SO.*'],
            'multi': ['.*MULTI.*', '.*MO.*', '.*MULTI-OP.*'],
            'checklog': ['check', 'checklog', 'check-log'],
        }
        for _cat, _regex_list in regexp_categories.items():
            for _regex in _regex_list:
                res = re.match(_regex, category_value, re.IGNORECASE)
                if res:
                    return True, _cat
        return False, None

    @staticmethod
    def rules_based_validate_category(category_value, rules):
        if not category_value:
            return False, None
        if rules is None:
            raise ValueError('No contest rules provided!')
        for _nr in range(1, rules.contest_categories_nr + 1):
            _regex = r'\s*(' + rules.contest_category(_nr)['regexp'] + r')\s*'
            res = re.match(_regex, category_value, re.IGNORECASE)
            if res:
                return True, rules.contest_category(_nr)['name']
        return False, None

    @staticmethod
    def validate_date(date_value):
        if not date_value:
            return False
        try:
            datetime.strptime(date_value, '%Y-%m-%d')
            return True
        except ValueError:
            return False

    @staticmethod
    def validate_email(email):
        if not email:
            return False
        import validate_email as ve
        return ve.validate_email(email)

    def rules_based_validate_date(self, date_value, rules):
        if rules is None:
            raise ValueError('No contest rules provided!')
        _begin_date = rules.contest_begin_date
        _end_date = rules.contest_end_date
        date_compact = date_value.replace('-', '')
        if _begin_date <= date_compact <= _end_date:
            return True
        return False
