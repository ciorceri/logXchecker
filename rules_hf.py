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

HF contest rules (Cabrillo log format).
Modes are represented as uppercase strings: CW, SSB, DIGI, FM, AM, RTTY, etc.
"""
from rules import Rules


class RulesHf(Rules):
    """
    HF contest rules — string-based mode representation.
    Used together with the Cabrillo log format.
    """

    @property
    def contest_qso_modes(self):
        try:
            modes = [mode.strip().upper() for mode in self.config['contest']['modes'].split(',')]
            return modes
        except KeyError:
            raise KeyError('Rules are missing field \'modes\' in [contest] section')
        except ValueError:
            raise ValueError('The rules have invalid \'modes\' value in [contest] section')
