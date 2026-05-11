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

Base class for contest rules.
Shared INI parsing & validation logic.
Concrete sub-classes (RulesVhf, RulesHf) add format-specific mode handling.
"""
import configparser
import os
from datetime import datetime


class Rules(object):
    """
    Base INI-based contest rules reader.

    Shared properties & accessors that work for both VHF/UHF/SHF (EDI) and HF (Cabrillo).
    Sub-classes may override contest_qso_modes to change parsing behaviour.
    """

    path = None
    config = None
    valid = False

    def __init__(self, path):
        if not os.path.isfile(path):
            raise FileNotFoundError("The rules file " + str(path) + " was not found")
        self.path = path
        self.valid = False
        self.config = configparser.ConfigParser()
        self.config.read_string(self.read_config_file_content(self.path))
        self.validate_rules()

    @staticmethod
    def read_config_file_content(path):
        content = None
        with open(path, 'r') as _file:
            content = _file.read()
        return content

    def validate_rules(self):
        # -- validate [contest] section fields --
        try:
            _ = self.contest_bands_nr
            _ = self.contest_periods_nr
            _ = self.contest_categories_nr
            _ = self.contest_qso_modes
        except KeyError:
            raise KeyError("ERROR: Rules has missing fields from [contest] section")

        if self.contest_bands_nr < 1:
            raise ValueError('Rules have invalid \'bands\' value in [contest] section')
        try:
            for band in range(1, self.contest_bands_nr+1):
                _ = self.contest_band(band)
                _ = self.contest_band(band)['band']
                _ = self.contest_band(band)['regexp']
                _ = self.contest_band(band)['multiplier']
        except KeyError:
            raise ValueError('Rules file has invalid settings for band {}'.format(band))

        if self.contest_periods_nr < 1:
            raise ValueError('Rules file has invalid \'periods\' field setting in [contest] section')
        try:
            for period in range(1, self.contest_periods_nr+1):
                _ = self.contest_period(period)
                _ = self.contest_period(period)['begindate']
                _ = self.contest_period(period)['enddate']
                _ = self.contest_period(period)['beginhour']
                _ = self.contest_period(period)['endhour']
                _ = self.contest_period(period)['bands']
        except KeyError:
            raise KeyError('Rules file has invalid settings for period {}'.format(period))

        if self.contest_categories_nr < 1:
            raise ValueError('Rules have invalid \'categories\' value in [contest] section')
        try:
            for category in range(1, self.contest_categories_nr+1):
                _ = self.contest_category(category)
                _ = self.contest_category(category)['name']
                _ = self.contest_category(category)['regexp']
                _ = self.contest_category(category)['bands']
        except KeyError:
            raise KeyError('Rules file has missing settings for category {}'.format(category))

        # validate dates & times
        try:
            msg = 'contest begin date'
            datetime.strptime(self.contest_begin_date, '%Y%m%d')
            msg = 'contest end date'
            datetime.strptime(self.contest_end_date, '%Y%m%d')
            for period in range(1, self.contest_periods_nr+1):
                msg = 'period {} begin date'.format(period)
                datetime.strptime(self.contest_period(period)['begindate'], '%Y%m%d')
                msg = 'period {} end date'.format(period)
                datetime.strptime(self.contest_period(period)['enddate'], '%Y%m%d')
            msg = 'contest begin hour'
            datetime.strptime(self.contest_begin_hour, '%H%M')
            msg = 'contest end hour'
            datetime.strptime(self.contest_end_hour, '%H%M')
            for period in range(1, self.contest_periods_nr+1):
                msg = 'period {} begin hour'.format(period)
                datetime.strptime(self.contest_period(period)['beginhour'], '%H%M')
                msg = 'period {} end hour'.format(period)
                datetime.strptime(self.contest_period(period)['endhour'], '%H%M')
        except ValueError:
            raise ValueError('Rules file has invalid {}'.format(msg))

        # validate band field in [periodX]
        for period in range(1, self.contest_periods_nr+1):
            period_bands = self.contest_period_bands(period)
            for period_band in period_bands:
                if period_band not in self.config.sections():
                    raise ValueError('Rules file has invalid band settings ({}) for period {}'.format(period_band, period))

        # validate band field in [categoryX]
        for category in range(1, self.contest_categories_nr+1):
            category_bands = self.contest_category_bands(category)
            for category_band in category_bands:
                if category_band not in self.config.sections():
                    raise ValueError('Rules file has invalid band settings ({}) for category {}'.format(category_band, category))

    # ── Shared properties ──────────────────────────────────────────────

    @property
    def contest_begin_date(self):
        return self.config['contest']['begindate']

    @property
    def contest_end_date(self):
        return self.config['contest']['enddate']

    @property
    def contest_begin_hour(self):
        return self.config['contest']['beginhour']

    @property
    def contest_end_hour(self):
        return self.config['contest']['endhour']

    @property
    def contest_qso_modes(self):
        """
        Default implementation: parse modes as integers (VHF/EDI mode codes).
        Sub-classes may override to e.g. parse string-based modes (HF/Cabrillo).
        """
        try:
            modes = [int(mode) for mode in self.config['contest']['modes'].split(',')]
            return modes
        except KeyError:
            raise KeyError('Rules are missing field \'modes\' in [contest] section')
        except ValueError:
            raise ValueError('The rules have invalid \'modes\' value in [contest] section')

    @property
    def contest_bands_nr(self):
        try:
            return int(self.config['contest']['bands'])
        except KeyError:
            raise KeyError('Rules has missing field \'bands\' in [contest] section')
        except ValueError:
            raise ValueError('The rules have invalid \'bands\' value in [contest] section')

    def contest_band(self, number):
        return self.config['band'+str(number)]

    @property
    def contest_periods_nr(self):
        try:
            return int(self.config['contest']['periods'])
        except KeyError:
            raise KeyError('Rules has missing field \'periods\' in [contest] section')
        except ValueError:
            raise ValueError('The rules have invalid \'periods\' value in [contest] section')

    def contest_period(self, number):
        return self.config['period'+str(number)]

    def contest_period_bands(self, number):
        return [band for band in self.contest_period(number)['bands'].split(',')]

    @property
    def contest_categories_nr(self):
        try:
            return int(self.config['contest']['categories'])
        except KeyError:
            raise KeyError('Rules has missing field \'categories\' in [contest] section')
        except ValueError:
            raise ValueError('Rules have invalid \'categories\' value in [contest] section')

    def contest_category(self, number):
        return self.config['category'+str(number)]

    def contest_category_bands(self, number):
        return [band for band in self.contest_category(number)['bands'].split(',')]

    @property
    def contest_log_format(self):
        return self.config['log']['format'].upper()

    @property
    def contest_extra_fields(self):
        extra_fields_to_check = ['callregexp']
        extra_list = []
        try:
            assert self.config['extra']
        except (KeyError, AssertionError):
            return []

        for field in extra_fields_to_check:
            try:
                assert self.config['extra'][field]
                extra_list.append(field)
            except (KeyError, AssertionError):
                pass
        extra_list.extend([x for x in self.config['extra'] if self.config['extra'][x].upper() == 'YES'])
        return extra_list

    def contest_extra_field_value(self, field):
        if field in self.contest_extra_fields:
            return self.config['extra'][field]
        return None
