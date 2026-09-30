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

DXCC database (callsign -> country/continent/ITU/CQ zone) and helpers.

The database is loaded from ``country.dat`` at module import time.
"""
import os
from typing import Dict, List, Optional

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


def is_dracula_contest(rules):
    """Check if the contest has DRACULA custom scoring."""
    return rules is not None and rules.contest_custom_scoring == 'DRACULA'


def is_yodx_contest(rules):
    """Check if the contest has YO DX HF custom scoring."""
    return rules is not None and rules.contest_custom_scoring == 'YODX'


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


# Transylvania-region county whitelist (DRACULA-001, specs/10-dracula-transylvania-2026.md).
# This is a flat subset cutting ACROSS YO_COUNTIES district boundaries, not a
# district-level split: YO2 splits into Transylvania 'HD' vs. rest 'AR, CS, TM';
# YO5 splits into Transylvania 'AB, BN, CJ, SJ' vs. rest 'BH, SM, MM'; YO6 is
# entirely Transylvania; YO3, YO4, YO7, YO8, YO9 have no Transylvania counties
# at all. Deliberately not derived from YO_COUNTIES district membership.
TRANSYLVANIA_COUNTIES = {'HD', 'AB', 'BN', 'CJ', 'SJ', 'BV', 'CV', 'HR', 'MS', 'SB'}


def is_transylvania_county(exchange):
    """Check if an exchange value is a Transylvania-region county abbreviation."""
    if not exchange:
        return False
    return exchange.upper().strip() in TRANSYLVANIA_COUNTIES


# Load the DXCC database at module import time
DXCC_BY_PREFIX = _load_dxcc_database()
