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

VHF/UHF/SHF contest rules (EDI log format).
Modes are represented as integers:
    0=None  1=SSB  2=CW  3=SSB+CW  4=CW+SSB  5=AM  6=FM  7=RTTY  8=SSTV  9=ATV
"""
from rules import Rules


class RulesVhf(Rules):
    """
    VHF/UHF/SHF contest rules — integer-based mode representation.
    Used together with the EDI log format.
    """

    @property
    def contest_qso_modes(self):
        try:
            modes = [int(mode) for mode in self.config['contest']['modes'].split(',')]
            return modes
        except KeyError:
            raise KeyError('Rules are missing field \'modes\' in [contest] section')
        except ValueError:
            raise ValueError('The rules have invalid \'modes\' value in [contest] section')
