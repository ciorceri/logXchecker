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

Cabrillo V2 / V3 log parser.

Supports both Cabrillo 2.0 (whitespace-separated QSO lines) and
Cabrillo 3.0 (semicolon-separated QSO lines) formats.

References:
    https://wwrof.org/cabrillo/cabrillo-v3-header/
    https://wwrof.org/cabrillo/cabrillo-qso-data/
"""
import json
import math
import os
import re
from datetime import datetime, timedelta

from dicttoxml import dicttoxml

from constants import ERR_IO, ERR_HEADER, ERR_QSO


# ── Helper: Maidenhead distance (used by compare_qso in cross-check) ───

def qth_distance(qth1, qth2):
    # TODO : this will be implemented in a future version, for now we return 1
    # TODO : it's possible also to rename this to get_points() since for HF contents the distance is not relevant and points are awarded based other rules
    return 1


# ── DRACULA helpers ────────────────────────────────────────────────────

# Romanian county abbreviations per YO district
YO_COUNTIES = {
    'YO2': ['AR', 'CS', 'HD', 'TM'],
    'YO3': ['BU', 'IF'],
    'YO4': ['CT', 'BR', 'GL', 'TL', 'VN'],
    'YO5': ['AB', 'BH', 'BN', 'CJ', 'SM', 'SJ', 'MM'],
    'YO6': ['BV', 'CV', 'HR', 'MS', 'SB'],
    'YO7': ['AG', 'DJ', 'GJ', 'MH', 'OT', 'VL'],
    'YO8': ['BC', 'BT', 'IS', 'NT', 'SV', 'VS'],
    'YO9': ['BZ', 'CL', 'DB', 'GR', 'IL', 'PH', 'TR'],
}
ALL_YO_COUNTIES = {c for counties in YO_COUNTIES.values() for c in counties}


def is_yo_callsign(callsign):
    """Check if a callsign is a Romanian (YO) station."""
    if not callsign:
        return False
    cs = callsign.upper().strip()
    # YO prefix (standard Romanian callsigns)
    if cs.startswith('YO') or cs.startswith('YP') or cs.startswith('YQ') or cs.startswith('YR'):
        return True
    return False


def is_dracula_special(callsign, rules):
    """Check if a callsign is in the DRACULA special station list."""
    if not rules or not callsign:
        return False
    cs = callsign.upper().strip()
    return cs in rules.contest_special_callsign


def is_yo_county(exchange):
    """Check if an exchange value is a Romanian county abbreviation."""
    if not exchange:
        return False
    return exchange.upper().strip() in ALL_YO_COUNTIES


def is_dracula_contest(rules):
    """Check if the contest has DRACULA custom scoring."""
    return rules is not None and rules.contest_custom_scoring == 'DRACULA'



# ── Operator ───────────────────────────────────────────────────────────

class Operator(object):
    """Keep operator callsign, info and logs path."""

    def __init__(self, callsign):
        self.callsign = callsign
        self.logs = []  # list with Log() instances

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


# ── Log ────────────────────────────────────────────────────────────────

HEADER_FIELDS_CABRILLO = {
    'callsign': 'CALLSIGN',
    'category_operator': 'CATEGORY-OPERATOR',
    'category_assisted': 'CATEGORY-ASSISTED',
    'category_band': 'CATEGORY-BAND',
    'category_mode': 'CATEGORY-MODE',
    'category_power': 'CATEGORY-POWER',
    'category_station': 'CATEGORY-STATION',
    'category_transmitter': 'CATEGORY-TRANSMITTER',
    'category_overlay': 'CATEGORY-OVERLAY',
    'category_time': 'CATEGORY-TIME',
    'claimedsorce': 'CLAIMED-SCORE',
    'club': 'CLUB',
    'contest': 'CONTEST',
    'created_by': 'CREATED-BY',
    'email': 'EMAIL',
    'grid_locator': 'GRID-LOCATOR',
    'location': 'LOCATION',
    'name': 'NAME',
    'operators': 'OPERATORS',
    'address': 'ADDRESS',
    'soapbox': 'SOAPBOX',
}

CABRILLO_MODE_ALIASES = {
    'SSB': 'SSB',
    'PHONE': 'SSB',
    'PH': 'SSB',
    'LSB': 'SSB',
    'USB': 'SSB',
    'CW': 'CW',
    'RTTY': 'RTTY',
    'FM': 'FM',
    'AM': 'AM',
    'SSTV': 'SSTV',
    'ATV': 'ATV',
    'PSK': 'DIGI',
    'PSK31': 'DIGI',
    'PSK63': 'DIGI',
    'JT65': 'DIGI',
    'JT9': 'DIGI',
    'FT4': 'DIGI',
    'FT8': 'DIGI',
    'FT10': 'DIGI',
    'JS8': 'DIGI',
    'MFSK': 'DIGI',
    'OLIVIA': 'DIGI',
    'RTTYM': 'DIGI',
    'RTTY': 'DIGI',
    'CONTESTI': 'DIGI',
    'DIGI': 'DIGI',
    'PACKET': 'DIGI',
    'PAX': 'DIGI',
    'PAX2': 'DIGI',
    'THROB': 'DIGI',
    'WINMOR': 'DIGI',
    'DOMINO': 'DIGI',
    'MT63': 'DIGI',
    'FSK441': 'DIGI',
    'JTMS': 'DIGI',
    'ISCAT': 'DIGI',
    'JT4': 'DIGI',
    'JT6M': 'DIGI',
    'QRA64': 'DIGI',
    'FSK315': 'DIGI',
}


def normalize_cabrillo_mode(mode):
    """Normalise a Cabrillo mode string to one of the standard modes
    (CW, SSB, FM, AM, DIGI, RTTY, SSTV, ATV)."""
    m = mode.strip().upper()
    return CABRILLO_MODE_ALIASES.get(m, m)


class Log(object):
    """
    Keep a single Cabrillo log information.

    Supports both V2 (whitespace-separated) and V3 (semicolon-separated) QSO lines.

    errors format:
    {
        'file': [(line or None, 'error: Cannot open file'), ...],
        'header': [(line or None, 'error: message'), ...],
        'qso': [(line, 'error: message'), ...],
    }
    """
    qsos_tuple = None  # unused, kept for interface compatibility

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
        self.qsos = []  # list with LogQso instances
        self.qsos_points = None
        self.qsos_confirmed = None

        self._cabrillo_version = None  # '2.0' or '3.0'

        self.validate_header()
        if not self.valid_header:
            return

        self.get_qsos()
        self.valid_qsos = True
        for qso in self.qsos:
            if qso.errors:
                self.errors[ERR_QSO].extend(qso.errors)
                self.valid_qsos = False

    # ── File I/O ───────────────────────────────────────────────────────

    @staticmethod
    def read_file_content(path):
        with open(path, 'r') as _file:
            content = _file.readlines()
        return content

    # ── Header validation ──────────────────────────────────────────────

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

        # Detect Cabrillo version
        first_line = self.log_lines[0].strip()
        m = re.match(r'^START-OF-LOG:\s*(\d+\.\d+)', first_line, re.IGNORECASE)
        if not m:
            self.errors[ERR_HEADER].append((1, 'Missing or invalid START-OF-LOG header'))
            # TODO : is possible that some logs will not have 'START-OF-LOG', in this case I should create an euristic that will try to detect the version based on the QSO format
            return
        self._cabrillo_version = m.group(1)
        if self._cabrillo_version not in ('2.0', '3.0'):
            self.errors[ERR_HEADER].append((1, 'Unsupported Cabrillo version: {}'.format(self._cabrillo_version)))
            return

        # Extract header fields
        header_data = self._parse_cabrillo_header()
        if not header_data:
            return

        # Validate callsign
        cs = header_data.get('callsign')
        if not cs:
            self.errors[ERR_HEADER].append((None, 'CALLSIGN field is not present'))
        else:
            if not self.validate_callsign(cs):
                self.errors[ERR_HEADER].append((None, 'CALLSIGN field content is not valid: {}'.format(cs)))
            else:
                self.callsign = cs.upper()

        # Validate band from CATEGORY-BAND
        cb = header_data.get('category_band', '').upper()
        if not cb:
            self.errors[ERR_HEADER].append((None, 'CATEGORY-BAND field is not present'))
        else:
            self.band = cb

        # Validate category from CATEGORY-OPERATOR
        co = header_data.get('category_operator', '').upper()
        if not co:
            self.errors[ERR_HEADER].append((None, 'CATEGORY-OPERATOR field is not present'))
        else:
            self.category_raw = co
            # Normalise category using rules if available, else generic
            if self.rules:
                _res, _cat = self.rules_based_validate_category(self.category_raw, self.rules)
                self.category = _cat
            else:
                _res, _cat = self.validate_category(self.category_raw)
                self.category = _cat

        # The DATE is extracted from the first QSO line (or we take contest begin date)
        # For Cabrillo logs, we'll use the contest dates from rules if available,
        # or leave date as None and set it from the first QSO
        self.date = self.rules.contest_begin_date if self.rules else None

        # Maidenhead locator is optional in Cabrillo
        gl = header_data.get('grid_locator', '')
        if gl and self.validate_qth_locator(gl):
            self.maidenhead_locator = gl.upper()

        # Email
        self.email = header_data.get('email', None)
        # Name
        self.name = header_data.get('name', None)
        # Address
        self.address = header_data.get('address', None)

        # Are all mandatory fields valid?
        if all((self.callsign, self.band, self.category)):
            self.valid_header = True

    def _parse_cabrillo_header(self):
        """Parse Cabrillo header fields into a dictionary."""
        data = {}
        for line in self.log_lines:
            stripped = line.strip()
            if stripped.upper().startswith('QSO:'):
                break  # QSO section starts
            if stripped.upper().startswith('END-OF-LOG:'):
                break
            if ':' in stripped:
                key, _, value = stripped.partition(':')
                key_upper = key.strip().upper()
                value = value.strip()

                # Map the known header fields
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

                # Handle V3 "CATEGORY: BAND: value" format
                if key_upper == 'CATEGORY':
                    # V3 format: CATEGORY: BAND: ALL
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

    # ── QSO parsing ────────────────────────────────────────────────────

    def get_qsos(self):
        qso_lines = []
        for index, line in enumerate(self.log_lines):
            stripped = line.strip()
            if stripped.upper().startswith('QSO:'):
                qso_lines.append((index + 1, stripped))

        self.qsos = []
        for line_nr, qso_line in qso_lines:
            self.qsos.append(LogQso(qso_line, line_nr, self.rules))

    # ── Field helpers ──────────────────────────────────────────────────

    def get_field(self, field):
        """Mimic EDI interface — not used directly by Cabrillo header
        but kept for interface compatibility."""
        return None, None

    # ── Validation methods ─────────────────────────────────────────────

    @staticmethod
    def validate_callsign(callsign):
        if not callsign:
            return False
        regex_pcall = r'^\s*(\w+[0-9]+\w+/?\w*)\s*$'
        res = re.match(regex_pcall, callsign)
        return True if res else False

    @staticmethod
    def validate_qth_locator(qth):
        # TODO : this should not exist in HF contests, I need to double-check this !
        if not qth:
            return False
        regex_maidenhead = r'^\s*([a-rA-R]{2}\d{2}[a-xA-X]{2})\s*$'
        res = re.match(regex_maidenhead, qth, re.IGNORECASE)
        return True if res else False

    @staticmethod
    def validate_band(band_value):
        """Generic band validation (used when no rules provided)."""
        # TODO : this is not called yet !
        if not band_value:
            return False
        # Accept ANY non-empty CATEGORY-BAND value as valid since the rules can redefine the bands names.
        return True

    @staticmethod
    def rules_based_validate_band(band_value, rules):
        """Validate CATEGORY-BAND against contest rules."""
        # TODO : this is not called yet !
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
        """Generic category validation."""
        if not category_value:
            return False, None
        # For Cabrillo, accept standard CATEGORY-OPERATOR values
        regexp_categories = {
            # TODO : I need to check what's the standard set of categories for Cabrillo logs, for now I just use the VHF ones as example
            'single': ['.*SINGLE.*', '.*SO.*', '.*CHECKLOG.*'],
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
        """Validate CATEGORY-OPERATOR against contest rules."""
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
        # TODO : this is not called yet !
        """Validate date in YYYY-MM-DD format (Cabrillo)."""
        if not date_value:
            return False
        try:
            datetime.strptime(date_value, '%Y-%m-%d')
            return True
        except ValueError:
            return False

    @staticmethod
    def validate_email(email):
        # TODO : this is not called yet !
        if not email:
            return False
        import validate_email as ve
        return ve.validate_email(email)

    def rules_based_validate_date(self, date_value, rules):
        # TODO : this is not called yet !
        if rules is None:
            raise ValueError('No contest rules provided!')
        # For Cabrillo, date_value is YYYY-MM-DD format
        # Rules store dates in YYYYMMDD format
        _begin_date = rules.contest_begin_date
        _end_date = rules.contest_end_date
        # Convert YYYY-MM-DD -> YYYYMMDD for comparison
        date_compact = date_value.replace('-', '')
        if _begin_date <= date_compact <= _end_date:
            return True
        return False


# ── LogQso ─────────────────────────────────────────────────────────────

class LogQso(object):
    """
    Keep a single QSO (in Cabrillo format).

    Standard Cabrillo V2 QSO format (space/tab separated):
        QSO: <freq> <mode> <date> <time> <call_sent> <rst_sent> <exch_sent> <call_recv> <rst_recv> <exch_recv> [tx_id]

    Standard Cabrillo V3 QSO format (semicolon separated):
        QSO: <freq>;<mode>;<date>;<time>;<call_sent>;<rst_sent>;<exch_sent>;<call_recv>;<rst_recv>;<exch_recv>[;<tx_id>]
        where trailing fields after the transmitter ID are ignored.
    """

    # Standard Cabrillo QSO regex (11 groups — no non-standard county fields)
    REGEX_CABRILLO_QSO = (
        r'^QSO:\s+'                           # QSO: marker
        r'(\d+(?:\.\d+)?)\s+'                 # 1  frequency (Hz or MHz)
        r'(\S+)\s+'                           # 2  mode
        r'(\d{4}-\d{2}-\d{2})\s+'             # 3  date YYYY-MM-DD
        r'(\d{4})\s+'                         # 4  time HHMM
        r'(\S+)\s+'                           # 5  station A callsign (our station)
        r'(\S+)\s+'                           # 6  rst sent
        r'(\S+)\s+'                           # 7  exchange sent (serial, county, or contest code)
        r'(\S+)\s+'                           # 8  station B callsign (other station)
        r'(\S+)\s+'                           # 9  rst recv
        r'(\S+)'                              # 10 exchange recv (serial, county, or contest code)
        r'(?:\s+(.*))?$'                      # 11 optional transmitter ID
    )


    def __init__(self, qso_line=None, qso_line_number=None, rules=None):
        self.qso_line = qso_line
        self.line_nr = qso_line_number
        self.rules = rules
        self.valid = True

        self.errors = []
        self.cc_confirmed = None
        self.cc_error = []
        self.points = None

        self.qso_fields = {'date': None,
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

        # 1st validation: parse and validate format
        self.validate_qso_format()
        if not self.valid:
            return
        self.parse_qso_fields()

        # 2nd validation: generic field validation
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
        """Parse QSO fields from the matched regex groups."""
        m = re.match(self.REGEX_CABRILLO_QSO, self.qso_line, re.IGNORECASE)
        if m:
            self._assign_fields(m)

    def _assign_fields(self, m):
        """
        Standard Cabrillo field assignment (11 capture groups).

        Regex captures:
            group 1:  frequency
            group 2:  mode
            group 3:  date (YYYY-MM-DD)
            group 4:  time (HHMM)
            group 5:  station A callsign (our station)
            group 6:  rst sent
            group 7:  exchange sent (nr_sent)
            group 8:  station B callsign (the other station)
            group 9:  rst recv
            group 10: exchange recv (nr_recv)
            group 11: optional transmitter ID
        """
        freq = m.group(1)       # frequency in KHz (for HF) or MHz (for VHF), GHz (for microwaves)
        mode = m.group(2)       # mode string (e.g. SSB, CW, RTTY, etc.)
        date_raw = m.group(3)   # YYYY-MM-DD
        hour = m.group(4)       # HHMM
        call_a = m.group(5).upper()  # station A callsign (only A-Z, 0-9 and / permitted)
        rst_a = m.group(6)      # contest rst (ex: 59, 599)
        exch_a = m.group(7)     # contest exchange sent (serial number, county code, etc.)
        call_b = m.group(8).upper()  # station B callsign
        rst_b = m.group(9)      # contest rst (ex: 59, 599)
        exch_b = m.group(10)    # contest exchange recv (serial number, county code, etc.)
        t = m.group(11) or ''   # transmitter ID (optional)

        # The "call" field in qso_fields is the OTHER station's callsign
        self.qso_fields['call'] = call_b
        # Convert YYYY-MM-DD to YYMMDD for cross-check compatibility
        self.qso_fields['date'] = date_raw[2:4] + date_raw[5:7] + date_raw[8:10]
        self.qso_fields['hour'] = hour
        # Normalise mode
        self.qso_fields['mode'] = normalize_cabrillo_mode(mode)
        self.qso_fields['rst_sent'] = rst_a
        self.qso_fields['nr_sent'] = exch_a
        self.qso_fields['rst_recv'] = rst_b
        self.qso_fields['nr_recv'] = exch_b


    @classmethod
    def regexp_qso_validator(cls, line):
        """Validate the QSO line format against the standard Cabrillo regex."""
        if not line:
            return 'QSO line is empty'
        if not line.upper().startswith('QSO:'):
            return 'QSO line does not start with QSO:'
        # Must match the standard Cabrillo regex
        m = re.match(cls.REGEX_CABRILLO_QSO, line, re.IGNORECASE)
        if not m:
            return 'Incorrect QSO line format'
        return None

    # ── Generic QSO validation ─────────────────────────────────────────

    def generic_qso_validator(self):
        """Validate parsed QSO fields using generic rules."""

        # Validate date format (YYMMDD)
        try:
            datetime.strptime(self.qso_fields['date'], '%y%m%d')
        except ValueError as why:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line, 'Qso date is invalid: {}'.format(str(why))))

        # Validate time format
        try:
            datetime.strptime(self.qso_fields['hour'], '%H%M')
        except ValueError as why:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line, 'Qso hour is invalid: {}'.format(str(why))))

        # Validate callsign format
        re_call = r'^\w+/?\w+$'
        result = re.match(re_call, self.qso_fields['call'])
        if not result:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line,
                                'Callsign is invalid: {}'.format(self.qso_fields['call'])))

        # Validate mode format (should be a non-empty string from the normalised set)
        if not self.qso_fields['mode']:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line,
                                'Qso mode is invalid: {}'.format(self.qso_fields['mode'])))

        # Validate RST (sent & recv) format
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

        # Validate NR (sent & recv) format
        # Accept alphanumeric exchange values (1-6 chars).
        # This covers: numeric serial numbers, county codes, "DRC", etc.
        re_exchange = r'^\w{1,6}$'
        result = re.match(re_exchange, self.qso_fields['nr_sent'])
        if not result:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line,
                                'Sent exchange is invalid: {}'.format(self.qso_fields['nr_sent'])))
        result = re.match(re_exchange, self.qso_fields['nr_recv'])
        if not result:
            self.valid = False
            self.errors.append((self.line_nr, self.qso_line,
                                'Received exchange is invalid: {}'.format(self.qso_fields['nr_recv'])))


    # ── Rules-based QSO validation ─────────────────────────────────────

    def rules_based_qso_validator(self):
        """Validate QSO fields using contest rules."""
        if self.rules is None:
            return

        # Validate qso mode (string comparison)
        if self.qso_fields['mode'] not in self.rules.contest_qso_modes:
            self.valid = False
            modes_str = ','.join(self.rules.contest_qso_modes)
            self.errors.append((self.line_nr,
                                self.qso_line,
                                'Qso mode is invalid: not in defined modes ({})'.format(modes_str)))

        # Validate qso date (YYMMDD format, compare as string like EDI)
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

        # Validate qso hour
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

        # Validate date & hour based on period
        inside_period, _ = self.qso_inside_period()
        if not inside_period:
            self.valid = False
            self.errors.append((self.line_nr,
                                self.qso_line,
                                'Qso date/hour is invalid: not inside contest periods'))

    # ── Period check ───────────────────────────────────────────────────

    def qso_inside_period(self):
        """
        :return: (True, period_number) or (False, None)
        """
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


# ── Cross-check functions ──────────────────────────────────────────────

def crosscheck_logs_filter(log_class, rules=None, logs_folder=None, checklogs_folder=None):
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
            continue
        callsign = log.callsign.upper()
        if not operator_instances.get(callsign, None):
            operator_instances[callsign] = Operator(callsign)
        operator_instances[callsign].add_log_instance(log)
    
    # if we find multiple logs for a ham on a band
    # we set Log.ignore_this_log for older files
    for band in range(1, rules.contest_bands_nr + 1):
        for _, _ham in operator_instances.items():
            _logs = _ham.logs_by_band_regexp(rules.contest_band(band)['regexp'])
            mark_older_logs(_logs)

    # do the corss-check over filtered logs
    confirmed_pairs = set()
    for band in range(1, rules.contest_bands_nr + 1):
        crosscheck_logs(operator_instances, rules, band, confirmed_pairs)

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

    # ── Multiplier processing -> [rules][scoring]multiplier_enabled=true ────────────────
    if rules.contest_multiplier_enabled:
        exchange_field = rules.contest_multiplier_exchange_field
        special_exchange = rules.contest_multiplier_special_exchange
        is_dracula = is_dracula_contest(rules)
        per_band_mult = rules.contest_multiplier_per_band

        for op, op_inst in operator_instances.items():
            if per_band_mult:
                # Per-band multipliers: each band has its own multiplier set
                for log in op_inst.logs:
                    band_unique_mult = set()
                    for qso in log.qsos:
                        if not qso.cc_confirmed or not (qso.points and qso.points > 0):
                            continue
                        if is_dracula:
                            # DRACULA: multipliers are DXCC entities + YO counties + DRC
                            partner_call = qso.qso_fields.get('call', '').upper()
                            exchange_val = qso.qso_fields.get(exchange_field, '').strip().upper()
                            if not partner_call:
                                continue
                            if is_dracula_special(partner_call, rules):
                                # DRC multiplier (special station callsign)
                                band_unique_mult.add(('DRC', partner_call))
                            elif is_yo_callsign(partner_call):
                                # YO station: use their exchange value (county) as multiplier
                                if exchange_val:
                                    band_unique_mult.add(('YO_COUNTY', exchange_val))
                            else:
                                # Non-YO station: DXCC entity (use callsign prefix as approximation)
                                dxcc_prefix = partner_call[:2]
                                band_unique_mult.add(('DXCC', dxcc_prefix))
                        else:
                            # Standard (RRO-style) multiplier processing
                            exchange_val = qso.qso_fields.get(exchange_field, '').strip().upper()
                            if not exchange_val:
                                continue
                            if special_exchange and exchange_val == special_exchange:
                                partner_call = qso.qso_fields.get('call', '').upper()
                                if partner_call:
                                    band_unique_mult.add(('CAT_A', partner_call))
                            else:
                                band_unique_mult.add(('COUNTY', exchange_val))
                    log.multiplier_count = len(band_unique_mult)
                    log.final_score = log.qsos_points * log.multiplier_count if log.qsos_points else 0
            else:
                # Global multipliers (across all bands)
                unique_multipliers = set()
                for log in op_inst.logs:
                    for qso in log.qsos:
                        if not qso.cc_confirmed or not (qso.points and qso.points > 0):
                            continue
                        if is_dracula:
                            partner_call = qso.qso_fields.get('call', '').upper()
                            exchange_val = qso.qso_fields.get(exchange_field, '').strip().upper()
                            if not partner_call:
                                continue
                            if is_dracula_special(partner_call, rules):
                                unique_multipliers.add(('DRC', partner_call))
                            elif is_yo_callsign(partner_call):
                                if exchange_val:
                                    unique_multipliers.add(('YO_COUNTY', exchange_val))
                            else:
                                dxcc_prefix = partner_call[:2]
                                unique_multipliers.add(('DXCC', dxcc_prefix))
                        else:
                            exchange_val = qso.qso_fields.get(exchange_field, '').strip().upper()
                            if not exchange_val:
                                continue
                            if special_exchange and exchange_val == special_exchange:
                                partner_call = qso.qso_fields.get('call', '').upper()
                                if partner_call:
                                    unique_multipliers.add(('CAT_A', partner_call))
                            else:
                                unique_multipliers.add(('COUNTY', exchange_val))
                for log in op_inst.logs:
                    log.multiplier_count = len(unique_multipliers)
                    log.final_score = log.qsos_points * log.multiplier_count if log.qsos_points else 0

    return operator_instances


# ── Custom scoring dispatcher ─────────────────────────────────────────

def apply_custom_scoring(callsign1, callsign2, rules, qso1, confirmed_pairs,
                         band_nr, qso_points_normal, qso_points_special,
                         special_callsign_list, distance):
    """
    Apply custom (DRACULA) or standard scoring based on rules.contest_custom_scoring.

    Sets qso1.points. For future custom contests, add a new _xxx_scoring()
    function and a new elif branch here.

    :return: (cc_confirmed, cc_error) tuple
    """
    custom_type = rules.contest_custom_scoring if rules else None
    if custom_type == 'DRACULA':
        return _dracula_scoring(callsign1, callsign2, rules, qso1)
    elif custom_type is None:
        return _standard_scoring(callsign1, callsign2, rules, qso1, confirmed_pairs,
                                 band_nr, qso_points_normal, qso_points_special,
                                 special_callsign_list, distance)
    else:
        raise NotImplementedError('Custom scoring type "{}" is not implemented'.format(custom_type))


def _dracula_scoring(callsign1, callsign2, rules, qso1):
    """
    DRACULA contest scoring logic.

    Rules:
      - Anyone working a special DRACULA station = 10 points
      - YO-YO QSO = 0 points (not allowed per rules)
      - YO working non-YO = 5 points
      - Non-YO working YO = 5 points
      - Non-YO working non-YO same country = 1 point
      - Non-YO working non-YO different DXCC = 2 points
    """
    if is_dracula_special(callsign2, rules):
        qso1.points = rules.contest_non_yo_to_special_points
    elif is_yo_callsign(callsign1):
        # YO station
        if is_yo_callsign(callsign2):
            qso1.points = 0
        else:
            qso1.points = rules.contest_yo_to_nonyo_points
    else:
        # Non-YO station
        if is_dracula_special(callsign2, rules):
            qso1.points = rules.contest_non_yo_to_special_points
        elif is_yo_callsign(callsign2):
            qso1.points = rules.contest_non_yo_to_yo_points
        else:
            prefix1 = callsign1[:2].upper()
            prefix2 = callsign2[:2].upper()
            if prefix1 == prefix2:
                qso1.points = rules.contest_non_yo_same_country_points
            else:
                qso1.points = rules.contest_non_yo_dxcc_points
    return True, []


def _standard_scoring(callsign1, callsign2, rules, qso1, confirmed_pairs,
                      band_nr, qso_points_normal, qso_points_special,
                      special_callsign_list, distance):
    """
    Standard (RRO-style) contest scoring logic.

    Rules:
      - QSO with a special callsign (e.g. YR20RRO) = special points (10)
      - QSO with a nominated station = normal points (5), once per mode
      - Default: distance * band multiplier
    """
    if callsign2.upper() in special_callsign_list:
        qso1.points = qso_points_special
    elif qso_points_normal != 1:
        pair_key = (qso1.qso_fields['mode'], min(callsign1, callsign2), max(callsign1, callsign2))
        if pair_key not in confirmed_pairs:
            confirmed_pairs.add(pair_key)
            qso1.points = qso_points_normal
        else:
            qso1.points = 0
    else:
        qso1.points = distance * int(rules.contest_band(band_nr)['multiplier'])
    return True, []


def crosscheck_logs(operator_instances, rules, band_nr, confirmed_pairs):
    """Cross-check QSOs between operators on a given band."""
    special_callsign_list = rules.contest_special_callsign
    qso_points_normal = rules.contest_qso_points
    qso_points_special = rules.contest_special_qso_points
    for callsign1, ham1 in operator_instances.items():
        _had_qso_with = []
        _logs1 = ham1.logs_by_band_regexp(rules.contest_band(band_nr)['regexp'])
        if not _logs1:
            continue

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
                continue

            callsign2 = qso1.qso_fields['call'].upper()

            _, inside_period_nr1 = qso1.qso_inside_period()
            if '{}-period{}'.format(callsign2, inside_period_nr1) in _had_qso_with:
                qso1.cc_confirmed = False
                qso1.cc_error = 'Qso already confirmed'
                continue

            ham2 = operator_instances.get(callsign2, None)
            if not ham2:
                qso1.cc_confirmed = False
                qso1.cc_error = 'No log from {}'.format(callsign2)
                continue

            _logs2 = ham2.logs_by_band_regexp(rules.contest_band(band_nr)['regexp'])
            if not _logs2:
                qso1.cc_confirmed = False
                qso1.cc_error = 'No log for this band from {}'.format(callsign2)
                continue

            for log2 in _logs2:
                if all((log2.ignore_this_log is False,
                        log2.valid_header is True)):
                    break
            else:
                qso1.cc_confirmed = False
                qso1.cc_error = 'No valid log from {}'.format(callsign2)
                continue

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

                _had_qso_with.append('{}-period{}'.format(callsign2, inside_period_nr2))

                # Apply scoring (custom or standard) via dispatcher
                qso1.cc_confirmed, qso1.cc_error = apply_custom_scoring(
                    callsign1, callsign2, rules, qso1, confirmed_pairs,
                    band_nr, qso_points_normal, qso_points_special,
                    special_callsign_list, distance)
                break
            else:
                qso1.cc_confirmed = False
                qso1.cc_error = 'No qso found on {} log'.format(callsign2)


def compare_qso(log1, qso1, log2, qso2):
    """
    Generic comparison of 2 QSOs (Cabrillo version).

    Returns distance (km) if QSOs match.
    Since Cabrillo does not provide Maidenhead locators, distance = 1 km
    for a valid match (as per requirements).

    :raises ValueError: if QSOs do not match
    """
    if qso1.valid is False:
        raise ValueError(qso1.errors[0][2])

    if qso2.valid is False:
        raise ValueError('Other ham qso is invalid')

    # compare callsign
    if log1.callsign != qso2.qso_fields['call'] or log2.callsign != qso1.qso_fields['call']:
        raise ValueError('Callsign mismatch')

    # calculate absolute date+time
    REGEX_DATE = r'(?P<year>\d{2})(?P<month>\d{2})(?P<day>\d{2})'
    REGEX_HOUR = r'(?P<hour>\d{2})(?P<minute>\d{2})'

    date_res1 = re.match(REGEX_DATE, qso1.qso_fields['date'])
    if not date_res1:
        raise ValueError('Date format is invalid : {}'.format(qso1.qso_fields['date']))
    hour_res1 = re.match(REGEX_HOUR, qso1.qso_fields['hour'])
    if not hour_res1:
        raise ValueError('Hour format is invalid : {}'.format(qso1.qso_fields['hour']))
    absolute_time1 = datetime(
        int(date_res1.group('year')), int(date_res1.group('month')),
        int(date_res1.group('day')),
        int(hour_res1.group('hour')), int(hour_res1.group('minute')))

    date_res2 = re.match(REGEX_DATE, qso2.qso_fields['date'])
    if not date_res2:
        raise ValueError('Date format is invalid : {}'.format(qso2.qso_fields['date']))
    hour_res2 = re.match(REGEX_HOUR, qso2.qso_fields['hour'])
    if not hour_res2:
        raise ValueError('Hour format is invalid : {}'.format(qso2.qso_fields['hour']))
    absolute_time2 = datetime(
        int(date_res2.group('year')), int(date_res2.group('month')),
        int(date_res2.group('day')),
        int(hour_res2.group('hour')), int(hour_res2.group('minute')))

    # check if time1 and time2 difference is less than 5 minutes
    if abs(absolute_time1 - absolute_time2) > timedelta(minutes=5):
        raise ValueError('Different date/time between qso\'s')

    # compare mode (string comparison for Cabrillo)
    if qso1.qso_fields['mode'] != qso2.qso_fields['mode']:
        raise ValueError('Mode mismatch')
    # compare rst
    if qso1.qso_fields['rst_sent'] != qso2.qso_fields['rst_recv']:
        raise ValueError('Rst mismatch (other ham)')
    if qso1.qso_fields['rst_recv'] != qso2.qso_fields['rst_sent']:
        raise ValueError('Rst mismatch')

    # compare serial number / exchange
    # For DRACULA, exchanges can be non-numeric (county codes, "DRC", etc.)
    # so we skip the exchange comparison for DRACULA contests
    if not is_dracula_contest(qso1.rules):
        if qso1.qso_fields['nr_sent'] != qso2.qso_fields['nr_recv']:
            raise ValueError('Serial number mismatch (other ham)')
        if qso1.qso_fields['nr_recv'] != qso2.qso_fields['nr_sent']:
            raise ValueError('Serial number mismatch')

    # No Maidenhead locator for Cabrillo — distance is 1 km per requirement
    return 1


def mark_older_logs(log_list):
    """Mark older log files (by timestamp) with ignore_this_log."""
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


# ── Serialisation helpers ──────────────────────────────────────────────

def dict_to_json(dictionary):
    return json.dumps(dictionary)


def dict_to_xml(dictionary):
    return dicttoxml(dictionary)
