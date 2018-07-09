"""
Copyright 2016-2018 Ciorceri Petru Sorin (yo5pjb)

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import configparser
import os
import sys
from datetime import datetime


class Rules(object):
    """
    Rule file format : https://en.wikipedia.org/wiki/INI_file

    Will read and parse the contest rule files.
    This class will contain various properties to get contest dates, bands, categories
    Rule example: contest date, contest bands, contest categories.
        [contest]
        name=Cupa Nasaud
        begindate=20160805
        enddate=20160806
        beginhour=1200
        endhour=1200
        bands=2
        periods=2
        categories=3
        modes=1,2,6
        # 0 non of below non of below
        # 1 SSB SSB
        # 2 CW CW
        # 3 SSB CW
        # 4 CW SSB
        # 5 AM AM
        # 6 FM FM
        # 7 RTTY RTTY
        # 8 SSTV SSTV
        # 9 ATV ATV

        [log]
        format=edi

        [band1]
        band=144
        regexp=144|145|2m
        multiplier=1

        [band2]
        band=432
        regexp=430|432|70cm
        multiplier=2

        [period1]
        begindate=20160805
        enddate=20160805
        beginhour=1200
        endhour=2359
        bands=band1,band2

        [period2]
        begindate=20160806
        enddate=201608086
        beginhour=0000
        endhour=1200
        bands=band1,band2

        [category1]
        name=Single Operator 144
        regexp=so|single
        bands=band1

        [category2]
        name=Single Operator 432
        regexp=so|single
        bands=band2

        [category3]
        name=Multi Operator
        regexp=mo|multi
        bands=band1,band2

        [extra]
        name=yes
        email=yes
        address=no

        # And then we have some details about mixing categories & bands. This will need some thinking
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
        # validate contest fields
        # in case of error it will print it and exit with exitcode = 10,11,12,13
        try:
            _ = self.contest_bands_nr
            _ = self.contest_periods_nr
            _ = self.contest_categories_nr
            _ = self.contest_qso_modes
        except KeyError as why:
            raise KeyError("ERROR: Rules has missing fields from [contest] section")

        # validate bands number and fields
        if self.contest_bands_nr < 1:
            raise ValueError('Rules have invalid \'bands\' value in [contest] section')
        try:
            for band in range(1, self.contest_bands_nr+1):
                _ = self.contest_band(band)
                _ = self.contest_band(band)['band']
                _ = self.contest_band(band)['regexp']
                _ = self.contest_band(band)['multiplier']
        except KeyError as why:
            raise ValueError('Rules file has invalid settings for band {}'.format(band))

        # validate period number and fields
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
        except KeyError as why:
            raise KeyError('Rules file has invalid settings for period {}'.format(period))

        # validate category number and fields
        if self.contest_categories_nr < 1:
            raise ValueError('Rules have invalid \'categories\' value in [contest] section')
        try:
            for category in range(1, self.contest_categories_nr+1):
                _ = self.contest_category(category)
                _ = self.contest_category(category)['name']
                _ = self.contest_category(category)['regexp']
                _ = self.contest_category(category)['bands']
        except KeyError as why:
            raise KeyError('Rules file has missing settings for category {}'.format(category))

        # validate date and time in [periodX]. period date and time to be in [contest] date/time range
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
        except ValueError as why:
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
                    raise ValueError('Rules file has invalid band settings ({}) for category {}'.format(category_band, period))

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
        try:
            modes = [int(mode) for mode in self.config['contest']['modes'].split(',')]
            return modes
        except KeyError:
            raise KeyError('Rules are missing field \'modes\' in [contest] section')
        except ValueError:
            raise ValueError('The rules have invalid \'modes\' value in [contest] section')

    @property
    def contest_bands_nr(self):
        """
        :return: number of contest bands
        """
        try:
            _ = self.config['contest']['bands']
            _nr = int(self.config['contest']['bands'])
            return _nr
        except KeyError:
            raise KeyError('Rules has missing field \'bands\' in [contest] section')
        except ValueError:
            raise ValueError('The rules have invalid \'bands\' value in [contest] section')

    def contest_band(self, number):
        """
        :param number: the band number to query
        :return: an instance of the config[bandX]
        """
        return self.config['band'+str(number)]

    @property
    def contest_periods_nr(self):
        """
        :return: number of periods
        """
        try:
            _ = self.config['contest']['periods']
            _nr = int(self.config['contest']['periods'])
            return _nr
        except KeyError:
            raise KeyError('Rules has missing field \'periods\' in [contest] section')
        except ValueError:
            raise ValueError('The rules have invalid \'periods\' value in [contest] section')

    def contest_period(self, number):
        """
        :param number: the period number to query
        :return: an instance of config[periodX]
        """
        return self.config['period'+str(number)]

    def contest_period_bands(self, number):
        """
        This will return a list of bands used in a period
        :param number: the period number to query
        :return: a list with bands names from config[periodX][bands]
        """
        return [band for band in self.contest_period(number)['bands'].split(',')]

    @property
    def contest_categories_nr(self):
        try:
            _ = self.config['contest']['categories']
            _nr = int(self.config['contest']['categories'])
            return _nr
        except KeyError:
            raise KeyError('Rules has missing field \'categories\' in [contest] section')
        except ValueError:
            raise ValueError('Rules have invalid \'categories\' value in [contest] section')

    def contest_category(self, number):
        """
        :param number:
        :return: an instance of config[categoryX]
        """
        return self.config['category'+str(number)]

    def contest_category_bands(self, number):
        """
        :param number:
        :return: a list with bands names from config[categoryX][bands]
        """
        return [band for band in self.contest_category(number)['bands'].split(',')]

    @property
    def contest_log_format(self):
        return self.config['log']['format'].upper()

    @property
    def contest_extra_fields(self):
        try:
            assert self.config['extra']
        except KeyError:
            return []
        return [x for x in self.config['extra'] if self.config['extra'][x].upper() == 'YES']
