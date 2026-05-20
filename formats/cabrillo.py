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
from typing import Dict, List, Optional, Any

from dicttoxml import dicttoxml

from constants import ERR_IO, ERR_HEADER, ERR_QSO


# ── DXCC Database ──────────────────────────────────────────────────────

# Global DXCC database: prefix -> DXCC entity info
# Built once at module load time from country.dat
DXCC_BY_PREFIX: Dict[str, Dict[str, str]] = {}


def _load_dxcc_database() -> Dict[str, Dict[str, str]]:
    """
    Load the DXCC database from the country.dat file.

    country.dat format (colon-separated, one line per DXCC entity):
        Country-Name: ITU-zone: CQ-zone: CONTINENT: GPS  main-prefix: prefix-list;

    Returns a dict mapping each prefix in the prefix-list and the main prefix
    to its entity info dict with keys:
        country, main_prefix, continent, itu, cq, gps
    """
    db: Dict[str, Dict[str, str]] = {}

    # Locate country.dat relative to this module
    dir_path = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(dir_path)
    country_dat_path = os.path.join(project_root, 'country.dat')

    if not os.path.isfile(country_dat_path):
        # Fallback: current working directory
        country_dat_path = os.path.join(os.getcwd(), 'country.dat')
        if not os.path.isfile(country_dat_path):
            return db  # empty database if file not found

    with open(country_dat_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line.endswith(';'):
                continue

            # Remove trailing semicolon, then split by colon
            content = line.rstrip(';')
            parts = content.split(':')
            if len(parts) < 6:
                continue

            country_name = parts[0].strip()
            itu_zone = parts[1].strip().lstrip('*').strip()
            cq_zone = parts[2].strip()
            continent = parts[3].strip()
            gps_and_main = parts[4].strip()
            prefix_str = parts[5].strip()

            # Parse "GPS  main-prefix" from e.g. "046/335  YO"
            gps_main_tokens = gps_and_main.split()
            if len(gps_main_tokens) >= 2:
                gps = ' '.join(gps_main_tokens[:-1])
                main_prefix = gps_main_tokens[-1]
            else:
                gps = ''
                main_prefix = gps_main_tokens[0] if gps_main_tokens else ''

            # Build prefix list (main prefix + all alternate prefixes)
            all_prefixes = []
            if prefix_str:
                # Split by comma and clean each entry
                raw_prefixes = [p.strip() for p in prefix_str.split(',')]
                for p in raw_prefixes:
                    p = p.strip()
                    if p and not p.startswith('*'):
                        all_prefixes.append(p)

            # Ensure main prefix is included
            if main_prefix and main_prefix not in all_prefixes:
                all_prefixes.append(main_prefix)

            entity_info = {
                'country': country_name,
                'main_prefix': main_prefix,
                'continent': continent,
                'itu': itu_zone,
                'cq': cq_zone,
                'gps': gps,
            }

            for prefix in all_prefixes:
                # If multiple entities share a prefix (conflict), keep the first one
                if prefix not in db:
                    db[prefix] = entity_info

    return db


def lookup_callsign(callsign: Optional[str]) -> Optional[Dict[str, str]]:
    """
    Look up a callsign in the DXCC database.

    Returns a dict with keys: country, main_prefix, continent, itu, cq, gps
    Returns None if the callsign's prefix is not found in the database.

    Algorithm:
    - Strip portable path prefixes (e.g., DL/ from DL/YO5PJB/P -> YO5PJB)
      Actually, the portable prefix INDICATES the operating DXCC, so DL/YO5PJB
      would be looked up as DL -> Germany
    - For callsigns like YO5PJB/P, strip /P and use YO5PJB
    - Generate candidate prefixes by progressively shortening from the right
    - Return the info for the longest matching prefix
    """
    if not callsign:
        return None

    cs = callsign.upper().strip()
    if not cs:
        return None

    # Collect all prefix candidates to try, grouped by priority
    # Priority order: candidates checked first have higher priority
    candidates: List[str] = []

    # Handle portable callsigns with /
    parts = cs.split('/')

    if len(parts) == 3:
        # Format: PREFIX/BASE/SUFFIX (e.g., DL/YO5PJB/P)
        # The first part is the operating prefix -> highest priority
        candidates.append(parts[0])
        # Then try the base callsign as a whole
        base = parts[1] if parts[1] else cs
        candidates.append(base)
        # Then prefix fragments from the base
        for i in range(len(base) - 1, 0, -1):
            candidates.append(base[:i])
    elif len(parts) == 2:
        # Try the original full string first
        candidates.append(cs)
        # Try each part as a candidate
        for part in parts:
            if part:
                candidates.append(part)
                # Also try progressive shortening of each part
                for i in range(len(part) - 1, 0, -1):
                    candidates.append(part[:i])
    else:
        # Normal callsign (no slashes): try progressive shortening
        for i in range(len(cs), 0, -1):
            candidates.append(cs[:i])

    # Deduplicate while preserving order (first occurrence wins)
    seen: set = set()
    unique_candidates: List[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique_candidates.append(c)

    # Check each candidate in order (longer/more specific first)
    for candidate in unique_candidates:
        if candidate in DXCC_BY_PREFIX:
            return DXCC_BY_PREFIX[candidate]

    return None


def is_yo_callsign(callsign: Optional[str]) -> bool:
    """Check if a callsign belongs to Romania (YO DXCC entity)."""
    if not callsign:
        return False
    info = lookup_callsign(callsign)
    if info is None:
        return False
    return info['main_prefix'] == 'YO'


def get_callsign_continent(callsign: Optional[str]) -> Optional[str]:
    """Get the continent code for a callsign.

    Returns a 2-letter continent code (EU, AS, NA, SA, AF, OC) or None.
    """
    if not callsign:
        return None
    info = lookup_callsign(callsign)
    if info is None:
        return None
    return info['continent']


def are_same_dxcc(callsign1: Optional[str], callsign2: Optional[str]) -> bool:
    """Check if two callsigns belong to the same DXCC entity."""
    if not callsign1 or not callsign2:
        return False
    info1 = lookup_callsign(callsign1)
    info2 = lookup_callsign(callsign2)
    if info1 is None or info2 is None:
        return False
    return info1['main_prefix'] == info2['main_prefix']


# Load the DXCC database at module import time
DXCC_BY_PREFIX = _load_dxcc_database()


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
        regex_pcall = r'^\s*(\w+\/{1})?(\w+[0-9]+)\w+(\/?)\w*\s*$'
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

    Standard Cabrillo V2/V3 QSO format (space/tab separated):
        QSO: <freq> <mode> <date> <time> <call_sent> <rst_sent> <exch_sent> <call_recv> <rst_recv> <exch_recv> [tx_id]
    """

    # Standard Cabrillo QSO regex (11 groups — standard V3 with single-token exchange fields)
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

    # 13-field Cabrillo regex — for logs where the exchange is split into
    # "serial_number + county_code" as two separate tokens (e.g. YO20RRO contest).
    # Groups 7 and 10 capture two tokens each (e.g. "001 BN").
    REGEX_CABRILLO_QSO_13F = (
        r'^QSO:\s+'                           # QSO: marker
        r'(\d+(?:\.\d+)?)\s+'                 # 1  frequency (Hz or MHz)
        r'(\S+)\s+'                           # 2  mode
        r'(\d{4}-\d{2}-\d{2})\s+'             # 3  date YYYY-MM-DD
        r'(\d{4})\s+'                         # 4  time HHMM
        r'(\S+)\s+'                           # 5  station A callsign (our station)
        r'(\S+)\s+'                           # 6  rst sent
        r'(\S+\s+\S+)\s+'                     # 7  exchange sent (nr + county combined: "001 BN")
        r'(\S+)\s+'                           # 8  station B callsign (other station)
        r'(\S+)\s+'                           # 9  rst recv
        r'(\S+\s+\S+)'                        # 10 exchange recv (nr + county combined: "005 IS")
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
        """Parse QSO fields from the matched regex groups.
        
        Uses token count to decide which regex to apply:
          - 12+ data tokens after QSO: → 13-field format (serial + county combined as one exchange)
          - otherwise → standard 11-field format
        """
        # Count data tokens (everything after QSO:)
        tokens = self.qso_line.strip().split()
        data_tokens = tokens[1:]  # skip 'QSO:'
        if len(data_tokens) >= 12:
            # 13-field format: exchange is split into "serial_number + county_code" tokens
            m = re.match(self.REGEX_CABRILLO_QSO_13F, self.qso_line, re.IGNORECASE)
            if m:
                self._assign_fields_13f(m)
                return
        # Standard 11-field format
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

        self.qso_fields['freq'] = freq
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


    def _assign_fields_13f(self, m):
        """
        Cabrillo 13-field field assignment.

        Same as _assign_fields but groups 7 and 10 contain two tokens
        (serial_number + county_code) combined, e.g. "001 BN".

        Regex captures:
            group 1:  frequency
            group 2:  mode
            group 3:  date (YYYY-MM-DD)
            group 4:  time (HHMM)
            group 5:  station A callsign (our station)
            group 6:  rst sent
            group 7:  exchange sent (nr + county combined: "001 BN")
            group 8:  station B callsign (the other station)
            group 9:  rst recv
            group 10: exchange recv (nr + county combined: "005 IS")
            group 11: optional transmitter ID
        """
        freq = m.group(1)       # frequency
        mode = m.group(2)       # mode string
        date_raw = m.group(3)   # YYYY-MM-DD
        hour = m.group(4)       # HHMM
        call_a = m.group(5).upper()  # station A callsign
        rst_a = m.group(6)      # contest rst (ex: 59, 599)
        exch_a = m.group(7)     # contest exchange sent (nr + county combined: "001 BN")
        call_b = m.group(8).upper()  # station B callsign
        rst_b = m.group(9)      # contest rst (ex: 59, 599)
        exch_b = m.group(10)    # contest exchange recv (nr + county combined: "005 IS")
        t = m.group(11) or ''   # transmitter ID (optional)

        self.qso_fields['freq'] = freq
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
        """Validate the QSO line format against the standard Cabrillo regex.
        
        Tries the standard 11-field regex first. If that doesn't match,
        tries the 13-field regex (for logs where the exchange is split into
        "serial_number + county_code" as separate tokens, e.g. YO20RRO contest).
        """
        if not line:
            return 'QSO line is empty'
        if not line.upper().startswith('QSO:'):
            return 'QSO line does not start with QSO:'
        # Try the standard 11-field regex first
        m = re.match(cls.REGEX_CABRILLO_QSO, line, re.IGNORECASE)
        if m:
            return None
        # Try the 13-field format
        m = re.match(cls.REGEX_CABRILLO_QSO_13F, line, re.IGNORECASE)
        if m:
            return None
        return 'Incorrect QSO line format'


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
        # Accept:
        #   - Standard: single alphanumeric token (1-6 chars) e.g. "001", "RRO", "BN"
        #   - Combined: "nr + county" format (7-13 chars with space) e.g. "001 BN", "599 RRO"
        # This covers: numeric serial numbers, county codes, "DRC", combined "number+county", etc.
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

def run_crosscheck(log_class, rules=None, logs_folder=None, checklogs_folder=None):
    """Orchestrate the full cross-check pipeline.

    :param log_class: the Log class (e.g. cabrillo.Log)
    :param rules: Rules instance
    :param logs_folder: path to folder containing competitor logs
    :param checklogs_folder: optional path to folder containing check logs
    :return: dict of operator callsign -> Operator instance
    """
    if not rules:
        print('No rules were provided')
        return {}
    if not logs_folder:
        print('Logs folder was not provided')
        return {}

    # 1. Load log files from both folders
    logs_instances = _load_log_files(log_class, rules, logs_folder, checklogs_folder)
    if logs_instances is None:
        return {}

    # 2. Group by operator callsign
    operator_instances = _group_logs_by_operator(logs_instances)

    # 3. Mark older duplicate logs per band
    _mark_older_duplicates(operator_instances, rules)

    # 4. Run per-band cross-check
    confirmed_pairs = set()
    for band in range(1, rules.contest_bands_nr + 1):
        crosscheck_band(operator_instances, rules, band, confirmed_pairs)

    # 4b. Apply 10-minute rule for multi-operator stations
    _apply_10_minute_rule(operator_instances, rules)

    # 5. Aggregate QSO points per log
    _aggregate_qso_points(operator_instances)

    # 6. Compute multipliers (if enabled)
    if rules.contest_multiplier_enabled:
        _compute_multipliers(operator_instances, rules)

    return operator_instances


def _load_log_files(log_class, rules, logs_folder, checklogs_folder):
    """Load and validate all log files from the given folders.

    Returns a list of Log instances, or None on error.
    """
    if not os.path.isdir(logs_folder):
        print('Cannot open logs folder : {}'.format(logs_folder))
        return None

    logs_instances = []
    for filename in os.listdir(logs_folder):
        logs_instances.append(log_class(os.path.join(logs_folder, filename), rules=rules))

    if checklogs_folder:
        if os.path.isdir(checklogs_folder):
            for filename in os.listdir(checklogs_folder):
                logs_instances.append(log_class(os.path.join(checklogs_folder, filename), rules=rules, checklog=True))
        else:
            print('Cannot open checklogs folder : {}'.format(checklogs_folder))
            return None

    return logs_instances


def _group_logs_by_operator(logs_instances):
    """Group Log instances by operator callsign into Operator objects."""
    operator_instances = {}
    for log in logs_instances:
        if not log.valid_header:
            log.ignore_this_log = True
            continue
        callsign = log.callsign.upper()
        if not operator_instances.get(callsign, None):
            operator_instances[callsign] = Operator(callsign)
        operator_instances[callsign].add_log_instance(log)
    return operator_instances


def _mark_older_duplicates(operator_instances, rules):
    """For multiple logs per operator on the same band, mark older ones as ignored."""
    for band in range(1, rules.contest_bands_nr + 1):
        for _, _ham in operator_instances.items():
            _logs = _ham.logs_by_band_regexp(rules.contest_band(band)['regexp'])
            mark_older_logs(_logs)


def _aggregate_qso_points(operator_instances):
    """Sum up points and confirmed QSO counts for each log."""
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


# ── 10-minute rule for multi-operator stations ─────────────────────────

def _get_band_from_frequency(freq_str, rules):
    """Determine which contest band (band number) a frequency belongs to.

    The frequency string is the first field after QSO: in the Cabrillo QSO line.
    For HF contests, this is typically in KHz (e.g. "14000") or MHz (e.g. "14.000").

    :param freq_str: The raw frequency string from the QSO line.
    :param rules: Rules instance with band definitions.
    :return: band number (1-based) or None if not determinable.
    """
    if not freq_str or not rules:
        return None

    # Parse the frequency value - convert to MHz
    try:
        if '.' in freq_str:
            # Already in MHz format (e.g. "14.000")
            freq_mhz = float(freq_str)
        else:
            # Likely in KHz (e.g. "14000" = 14.000 MHz)
            # or Hz (e.g. "14000000" = 14.000 MHz)
            freq_val = int(freq_str)
            if freq_val >= 1000000:
                # Hz -> MHz
                freq_mhz = freq_val / 1000000.0
            elif freq_val >= 10000:
                # KHz -> MHz
                freq_mhz = freq_val / 1000.0
            else:
                freq_mhz = float(freq_val)
    except (ValueError, TypeError):
        return None

    # Check against each contest band's nominal frequency
    for band_nr in range(1, rules.contest_bands_nr + 1):
        try:
            band_freq = float(rules.contest_band(band_nr)['band'])
        except (ValueError, KeyError, TypeError):
            continue

        # Use a tolerance of ±5% around the band's nominal frequency,
        # which covers typical HF band edges (e.g., 3.5-29.7 MHz)
        tolerance = band_freq * 0.05
        if abs(freq_mhz - band_freq) <= tolerance:
            return band_nr

    return None


def _parse_qso_datetime(qso):
    """Parse a QSO's date and hour fields into a datetime object.

    :param qso: LogQso instance
    :return: datetime object or None on failure
    """
    try:
        return datetime.strptime(
            '20' + qso.qso_fields['date'] + ' ' + qso.qso_fields['hour'],
            '%Y%m%d %H%M')
    except (ValueError, KeyError, TypeError):
        return None


def _classify_qso_multiplier(qso, rules):
    """Determine if a QSO's partner is a multiplier and return its key.

    For the 10-minute rule exception, we only care whether the QSO's
    partner represents a new multiplier. This function wraps the existing
    _compute_multiplier_for_qso logic.

    :param qso: LogQso instance
    :param rules: Rules instance
    :return: multiplier key tuple (type, value) or None if not a multiplier
    """
    if not rules or not qso:
        return None
    exchange_field = rules.contest_multiplier_exchange_field
    special_exchange = rules.contest_multiplier_special_exchange
    return _compute_multiplier_for_qso(qso, rules, exchange_field, special_exchange)


def _apply_10_minute_rule(operator_instances, rules):
    """Apply the 10-minute rule to multi-operator stations.

    The rule (as defined in CQWW / Dracula contest rules):
      - Multi-operator stations must stay on a band for at least 10 full minutes
      - The clock starts at the time of the first QSO made on that band
      - Banda can be changed after 10 full minutes have elapsed
      - Exception: working a new multiplier allows an early band change
      - Violation: QSOs made in violation get 0 points

    :param operator_instances: dict of callsign -> Operator
    :param rules: Rules instance
    """
    if not rules:
        return

    for op_callsign, op_inst in operator_instances.items():
        # Only apply to multi-operator stations (category == 'multi')
        is_multi = any(
            log.category and log.category.upper() == 'MULTI'
            for log in op_inst.logs
        )
        if not is_multi:
            continue

        # Collect all confirmed QSOs across all logs (sorted chronologically)
        all_qsos = []
        for log in op_inst.logs:
            if log.ignore_this_log or not log.valid_header:
                continue
            for qso in log.qsos:
                if not qso.valid or qso.cc_confirmed is not True:
                    continue
                dt = _parse_qso_datetime(qso)
                if dt is None:
                    continue
                all_qsos.append((dt, qso, log))

        if not all_qsos:
            continue

        # Sort chronologically by QSO time
        all_qsos.sort(key=lambda x: x[0])

        # Track band sessions and multipliers worked
        current_band_nr = None
        session_first_time = None
        seen_multipliers = set()

        for dt, qso, log in all_qsos:
            # Extract frequency from raw QSO line (first field after 'QSO:')
            tokens = qso.qso_line.strip().split()
            if len(tokens) < 2:
                continue
            freq_str = tokens[1]

            qso_band_nr = _get_band_from_frequency(freq_str, rules)
            if qso_band_nr is None:
                continue

            # Determine if this QSO is a new multiplier (exception check)
            mult_key = _classify_qso_multiplier(qso, rules)
            is_new_mult = mult_key is not None and mult_key not in seen_multipliers

            if current_band_nr is None:
                # First QSO - start a new session on this band
                current_band_nr = qso_band_nr
                session_first_time = dt
            elif qso_band_nr == current_band_nr:
                # Same band - session continues, no action needed
                pass
            else:
                # Band change detected
                elapsed_minutes = (dt - session_first_time).total_seconds() / 60.0

                if elapsed_minutes < 10 and not is_new_mult:
                    # Violation: band changed before 10 minutes AND this is not
                    # a new multiplier — set QSO points to 0
                    qso.points = 0
                else:
                    # Allowed band change:
                    #   - either 10+ minutes have passed on the current band, OR
                    #   - this QSO is a new multiplier (exception)
                    # Start a new session on the new band
                    current_band_nr = qso_band_nr
                    session_first_time = dt

            # Track this multiplier for future new-multiplier checks
            if mult_key:
                seen_multipliers.add(mult_key)


def _compute_multipliers(operator_instances, rules):
    """Post-process multipliers for each operator's logs.

    Supports both per-band and global multiplier modes,
    as well as DRACULA and standard (RRO-style) multiplier logic.
    """
    exchange_field = rules.contest_multiplier_exchange_field
    special_exchange = rules.contest_multiplier_special_exchange
    per_band_mult = rules.contest_multiplier_per_band

    for op, op_inst in operator_instances.items():
        if per_band_mult:
            for log in op_inst.logs:
                band_unique_mult = set()
                for qso in log.qsos:
                    if not qso.cc_confirmed or not (qso.points and qso.points > 0):
                        continue
                    mult_entry = _compute_multiplier_for_qso(qso, rules, exchange_field, special_exchange)
                    if mult_entry:
                        band_unique_mult.add(mult_entry)
                log.multiplier_count = len(band_unique_mult)
                log.final_score = log.qsos_points * log.multiplier_count if log.qsos_points else 0
        else:
            unique_multipliers = set()
            for log in op_inst.logs:
                for qso in log.qsos:
                    if not qso.cc_confirmed or not (qso.points and qso.points > 0):
                        continue
                    mult_entry = _compute_multiplier_for_qso(qso, rules, exchange_field, special_exchange)
                    if mult_entry:
                        unique_multipliers.add(mult_entry)
            for log in op_inst.logs:
                log.multiplier_count = len(unique_multipliers)
                log.final_score = log.qsos_points * log.multiplier_count if log.qsos_points else 0


def _compute_multiplier_for_qso(qso, rules, exchange_field, special_exchange):
    """Determine the multiplier type and key for a single confirmed QSO.

    Returns a tuple (type, key) suitable for adding to a multiplier set,
    or None if the QSO does not contribute a multiplier.

    For DRACULA:
        - Special station (DRC) -> ('DRC', callsign)
        - YO station -> ('YO_COUNTY', exchange_value)
        - Non-YO station -> ('DXCC', main_prefix)
    For standard (RRO-style):
        - Category A station -> ('CAT_A', callsign)
        - Other -> ('COUNTY', county_code)
    """
    is_dracula = is_dracula_contest(rules)
    partner_call = qso.qso_fields.get('call', '').upper()

    if is_dracula:
        if not partner_call:
            return None
        if is_dracula_special(partner_call, rules):
            return ('DRC', partner_call)
        elif is_yo_callsign(partner_call):
            exchange_val = qso.qso_fields.get(exchange_field, '').strip().upper()
            if exchange_val:
                return ('YO_COUNTY', exchange_val)
            return None
        else:
            dxcc_info = lookup_callsign(partner_call)
            dxcc_key = dxcc_info['main_prefix'] if dxcc_info else partner_call[:2]
            return ('DXCC', dxcc_key)
    else:
        exchange_val = qso.qso_fields.get(exchange_field, '').strip().upper()
        county_val = _extract_county_from_exchange(exchange_val)
        if not county_val:
            return None
        if special_exchange and county_val == special_exchange:
            if partner_call:
                return ('CAT_A', partner_call)
            return None
        return ('COUNTY', county_val)


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
        if is_yo_callsign(callsign2):
            qso1.points = rules.contest_non_yo_to_yo_points
        else:
            if are_same_dxcc(callsign1, callsign2):
                qso1.points = rules.contest_non_yo_same_country_points
            else:
                qso1.points = rules.contest_non_yo_dxcc_points
    return True, []


def _standard_scoring(callsign1, callsign2, rules, qso1, confirmed_pairs,
                      band_nr, qso_points_normal, qso_points_special,
                      special_callsign_list, distance):
    """
    Standard contest scoring logic.

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


def crosscheck_band(operator_instances, rules, band_nr, confirmed_pairs):
    """Cross-check QSOs between operators on a given band."""
    special_callsign_list = rules.contest_special_callsign
    qso_points_normal = rules.contest_qso_points
    qso_points_special = rules.contest_special_qso_points

    for callsign1, ham1 in operator_instances.items():
        _had_qso_with = []
        log1 = _find_active_log(ham1, rules, band_nr)
        if log1 is None:
            continue

        for qso1 in log1.qsos:
            if qso1.valid is False:
                qso1.cc_confirmed = False
                qso1.cc_error = qso1.errors[0][2] if len(qso1.errors) >= 1 else 'Qso is not valid'
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

            log2 = _find_active_log(ham2, rules, band_nr)
            if log2 is None:
                qso1.cc_confirmed = False
                qso1.cc_error = 'No valid log for this band from {}'.format(callsign2)
                continue

            qso2 = _find_matching_qso(qso1, log2, callsign1, inside_period_nr1)
            if qso2 is None:
                qso1.cc_confirmed = False
                qso1.cc_error = 'No qso found on {} log'.format(callsign2)
                continue

            # Determine period number from partner's QSO for dedup
            _, partner_period_nr = qso2.qso_inside_period()

            distance = _compare_qso_pair(log1, qso1, log2, qso2)
            if distance is None:
                continue

            _had_qso_with.append('{}-period{}'.format(callsign2, partner_period_nr))

            # Apply scoring (custom or standard) via dispatcher
            qso1.cc_confirmed, qso1.cc_error = apply_custom_scoring(
                callsign1, callsign2, rules, qso1, confirmed_pairs,
                band_nr, qso_points_normal, qso_points_special,
                special_callsign_list, distance)


def _find_active_log(ham, rules, band_nr):
    """Find the first valid, non-ignored log for an operator on a given band.

    Returns a Log instance, or None if no suitable log is found.

    For Cabrillo HF logs, a single log covers ALL bands (CATEGORY-BAND: ALL).
    If no band-specific log is found, fall back to searching for a log with
    CATEGORY-BAND set to "ALL" (case-insensitive).
    """
    _logs = ham.logs_by_band_regexp(rules.contest_band(band_nr)['regexp'])
    if not _logs:
        # For Cabrillo HF logs: a single log may cover all bands (CATEGORY-BAND: ALL).
        # Fall back to finding a log with band set to "ALL".
        for log in ham.logs:
            if all((log.use_as_checklog is False,
                    log.ignore_this_log is False,
                    log.valid_header is True,
                    log.band and log.band.upper() == 'ALL')):
                return log
        return None
    # If multiple logs match the band regex, return the first valid, non-ignored one.
    # TODO : hope this will not bite us in the future if we have multiple versions of the same log 
    for log in _logs:
        if all((log.use_as_checklog is False,
                log.ignore_this_log is False,
                log.valid_header is True)):
            return log
    return None


def _find_matching_qso(qso1, log2, expected_callsign, inside_period_nr1):
    """Search the partner's log for a QSO matching qso1.

    Returns the matching LogQso instance, or None if no match is found.
    """
    for qso2 in log2.qsos:
        if qso2.valid is False:
            continue
        if qso2.qso_fields['call'].upper() != expected_callsign:
            continue
        _, inside_period_nr2 = qso2.qso_inside_period()
        if inside_period_nr1 != inside_period_nr2:
            continue
        return qso2
    return None


def _compare_qso_pair(log1, qso1, log2, qso2):
    """Compare two QSOs and return distance if they match, None otherwise.

    Sets qso1.cc_confirmed to False and qso1.cc_error on mismatch.
    """
    try:
        distance = compare_qso(log1, qso1, log2, qso2)
    except ValueError as e:
        qso1.cc_confirmed = False
        qso1.cc_error = e
        return None
    return distance


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
    if qso1.qso_fields['nr_sent'] != qso2.qso_fields['nr_recv']:
        raise ValueError('Serial number mismatch (other ham)')
    if qso1.qso_fields['nr_recv'] != qso2.qso_fields['nr_sent']:
        raise ValueError('Serial number mismatch')

    # No Maidenhead locator for Cabrillo — distance is 1 km per requirement
    return 1


def _extract_county_from_exchange(exchange_val):
    """
    Extract the county/exchange code from a potentially combined exchange value.
    
    For 13-field QSOs, the exchange contains "nr + county" (e.g. "001 BN").
    For standard 11-field QSOs, the exchange is just the county code (e.g. "BN").
    
    Returns the county/exchange code part.
    """
    if not exchange_val:
        return ''
    parts = exchange_val.strip().upper().split()
    if len(parts) >= 2:
        # Combined format: "001 BN" -> return "BN"
        return parts[-1]
    # Single token: "BN" or "RRO" -> return as-is
    return parts[0]


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
