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

formats.cabrillo — Cabrillo V2/V3 log parser package.

Re-exports everything from submodules for backward compatibility
with code that imports from ``formats.cabrillo``.
"""
# flake8: noqa

# Re-export DXCC helpers and DRACULA helpers from common package
from common.dxcc import (
    _load_dxcc_database,
    DXCC_BY_PREFIX,
    lookup_callsign,
    is_yo_callsign,
    get_callsign_continent,
    are_same_dxcc,
    YO_COUNTIES,
    ALL_YO_COUNTIES,
    is_dracula_contest,
    is_dracula_special,
    is_yo_county,
    is_yodx_contest,
)

# Constants and helpers
from .constants import (
    HEADER_FIELDS_CABRILLO,
    CABRILLO_MODE_ALIASES,
    REGEX_CABRILLO_QSO,
    REGEX_CABRILLO_QSO_13F,
    normalize_cabrillo_mode,
    qth_distance,
)

# Classes
from .operator import Operator
from .log import Log
from .qso import LogQso

# Cross-check
from .crosscheck import run_crosscheck, crosscheck_band, compare_qso

# Shared cross-check utilities (backward compat)
from common.crosscheck import mark_older_logs

# Scoring
from .scoring import (
    apply_custom_scoring,
    _dracula_scoring,
    _yodx_scoring,
    _standard_scoring,
    _compute_multipliers,
    _compute_multiplier_for_qso,
    _extract_county_from_exchange,
    _apply_10_minute_rule,
    _get_band_from_frequency,
    _parse_qso_datetime,
    _classify_qso_multiplier,
)

# Serialisation helpers (backward compat)
from common.serialization import dict_to_json, dict_to_xml

# Constants
from constants import ERR_IO, ERR_HEADER, ERR_QSO
