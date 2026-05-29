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

Cabrillo format constants and helpers.
"""

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

# Standard Cabrillo QSO regex (11 groups)
REGEX_CABRILLO_QSO = (
    r'^QSO:\s+'
    r'(\d+(?:\.\d+)?)\s+'
    r'(\S+)\s+'
    r'(\d{4}-\d{2}-\d{2})\s+'
    r'(\d{4})\s+'
    r'(\S+)\s+'
    r'(\S+)\s+'
    r'(\S+)\s+'
    r'(\S+)\s+'
    r'(\S+)\s+'
    r'(\S+)'
    r'(?:\s+(.*))?$'
)

# 13-field Cabrillo regex (serial + county exchange)
REGEX_CABRILLO_QSO_13F = (
    r'^QSO:\s+'
    r'(\d+(?:\.\d+)?)\s+'
    r'(\S+)\s+'
    r'(\d{4}-\d{2}-\d{2})\s+'
    r'(\d{4})\s+'
    r'(\S+)\s+'
    r'(\S+)\s+'
    r'(\S+\s+\S+)\s+'
    r'(\S+)\s+'
    r'(\S+)\s+'
    r'(\S+\s+\S+)'
    r'(?:\s+(.*))?$'
)


def normalize_cabrillo_mode(mode):
    """Normalise a Cabrillo mode string to one of the standard modes
    (CW, SSB, FM, AM, DIGI, RTTY, SSTV, ATV)."""
    m = mode.strip().upper()
    return CABRILLO_MODE_ALIASES.get(m, m)


def qth_distance(qth1, qth2):
    return 1
