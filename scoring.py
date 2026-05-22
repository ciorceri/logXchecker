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

Scoring configuration mixin for contest rules.
"""
from typing import Dict, List, Optional


class ScoringMixin:
    """Mixin providing scoring-related properties from the INI [scoring] section."""

    @property
    def contest_qso_points(self) -> int:
        try:
            return int(self.config['scoring']['qso_points'])
        except (KeyError, ValueError):
            return 1

    @property
    def contest_special_qso_points(self) -> int:
        try:
            return int(self.config['scoring']['special_qso_points'])
        except (KeyError, ValueError):
            return 0

    @property
    def contest_special_callsign(self) -> List[str]:
        try:
            sp_callsigns = str(self.config['scoring']['special_callsign']).upper()
            return [s.strip() for s in sp_callsigns.split(',')]
        except (KeyError, ValueError):
            return []

    @property
    def contest_custom_scoring(self) -> Optional[str]:
        try:
            return self.config['contest']['custom_scoring'].strip().upper()
        except (KeyError, ValueError):
            return None

    @property
    def contest_multiplier_enabled(self) -> bool:
        try:
            return self.config['scoring'].getboolean('multiplier_enabled')
        except (KeyError, ValueError):
            return False

    @property
    def contest_multiplier_per_band(self) -> bool:
        try:
            return self.config['scoring'].getboolean('multiplier_per_band')
        except (KeyError, ValueError):
            return False

    @property
    def contest_multiplier_exchange_field(self) -> str:
        try:
            return self.config['scoring']['multiplier_exchange_field']
        except KeyError:
            return 'nr_recv'

    @property
    def contest_multiplier_special_exchange(self) -> Optional[str]:
        try:
            return self.config['scoring']['multiplier_special_exchange'].upper()
        except KeyError:
            return None

    @property
    def contest_non_yo_to_special_points(self) -> int:
        try:
            return int(self.config['scoring']['non_yo_to_special_points'])
        except (KeyError, ValueError):
            return 10

    @property
    def contest_non_yo_to_yo_points(self) -> int:
        try:
            return int(self.config['scoring']['non_yo_to_yo_points'])
        except (KeyError, ValueError):
            return 5

    @property
    def contest_non_yo_dxcc_points(self) -> int:
        try:
            return int(self.config['scoring']['non_yo_dxcc_points'])
        except (KeyError, ValueError):
            return 2

    @property
    def contest_non_yo_same_country_points(self) -> int:
        try:
            return int(self.config['scoring']['non_yo_same_country_points'])
        except (KeyError, ValueError):
            return 1

    @property
    def contest_yo_to_special_points(self) -> int:
        try:
            return int(self.config['scoring']['yo_to_special_points'])
        except (KeyError, ValueError):
            return 10

    @property
    def contest_yo_to_nonyo_points(self) -> int:
        try:
            return int(self.config['scoring']['yo_to_nonyo_points'])
        except (KeyError, ValueError):
            return 5

    @property
    def contest_dracula_county_list(self) -> Dict[str, List[str]]:
        try:
            raw = self.config['scoring'].get('dracula_county_list', '')
            if not raw:
                return {}
            result: Dict[str, List[str]] = {}
            for line in raw.replace('\r', '').split('\n'):
                line = line.strip()
                if ':' not in line:
                    continue
                district, counties = line.split(':', 1)
                result[district.strip().upper()] = [c.strip() for c in counties.split(',')]
            return result
        except Exception:
            return {}
