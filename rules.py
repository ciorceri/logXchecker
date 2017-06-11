"""
Copyright 2016-2017 Ciorceri Petru Sorin

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

        [log]
        format=edi

        [mode]
        regexp=1|2|6

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

        [band1]
        band=144
        regexp=144|145|2m

        [band2]
        band=432
        regexp=430|432|70cm

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
        with open(path, 'r') as f:
            content = f.read()
        return content

    def validate_rules(self):
        # validate contest fields
        # in case of error it will print it and exit with exitcode = 1,9,10,11,12
        try:
            self.contest_bands_nr
            self.contest_periods_nr
            self.contest_categories_nr
        except KeyError as e:
            print('ERROR: Rules has missing fields from [contest] section')
            sys.exit(10)

        # validate bands number and fields
        if self.contest_bands_nr < 1:
            print('ERROR: Rules file has invalid \'bands\' field setting in [contest] section')
            sys.exit(10)
        try:
            for band in range(1, self.contest_bands_nr+1):
                self.contest_band(band)
                self.contest_band(band)['band']
                self.contest_band(band)['regexp']
        except KeyError as e:
            print('ERROR: Rules file has invalid settings for band', band)
            sys.exit(11)

        # validate period number and fields
        if self.contest_periods_nr < 1:
            print('ERROR: Rules file has invalid \'periods\' field setting in [contest] section')
            sys.exit(10)
        try:
            for period in range(1, self.contest_periods_nr+1):
                self.contest_period(period)
                self.contest_period(period)['begindate']
                self.contest_period(period)['enddate']
                self.contest_period(period)['beginhour']
                self.contest_period(period)['endhour']
                self.contest_period(period)['bands']
        except KeyError as e:
            print('ERROR: Rules file has invalid settings for period', period)
            sys.exit(12)

        # validate period number and fields
        if self.contest_categories_nr < 1:
            print('ERROR: Rules file has invalid \'categories\' field setting in [contest] section')
            sys.exit(10)
        try:
            for category in range(1, self.contest_categories_nr+1):
                self.contest_category(category)
                self.contest_category(category)['name']
                self.contest_category(category)['regexp']
                self.contest_category(category)['bands']
        except KeyError as e:
            print('ERROR: Rules file has invalid settings for category', category)
            sys.exit(13)

        # validate date and time in [periodX]. period date and time to be in [contest] date/time range
        try:
            msg = 'contest begin date'
            datetime.strptime(self.contest_begin_date, '%Y%m%d')
            msg = 'contest end date'
            datetime.strptime(self.contest_end_date, '%Y%m%d')
            for period in range(1, self.contest_periods_nr+1):
                msg = 'period %d begin date' % period
                datetime.strptime(self.contest_period(period)['begindate'], '%Y%m%d')
                msg = 'period %d end date' % period
                datetime.strptime(self.contest_period(period)['enddate'], '%Y%m%d')
            msg = 'contest begin hour'
            datetime.strptime(self.contest_begin_hour, '%H%M')
            msg = 'contest end hour'
            datetime.strptime(self.contest_end_hour, '%H%M')
            for period in range(1, self.contest_periods_nr+1):
                msg = 'period %d begin hour' % period
                datetime.strptime(self.contest_period(period)['beginhour'], '%H%M')
                msg = 'period %d end hour' % period
                datetime.strptime(self.contest_period(period)['endhour'], '%H%M')
        except ValueError as e:
            print('ERROR: Rules file has invalid', msg)
            sys.exit(12)

        # validate band field in [periodX]
        for period in range(1, self.contest_periods_nr+1):
            period_bands = self.contest_period_bands(period)
            for period_band in period_bands:
                if period_band not in self.config.sections():
                    print('ERROR: Rules file has invalid band settings ({}) for period {}'.format(period_band, period))
                    sys.exit(12)

        # validate band field in [categoryX]
        for category in range(1, self.contest_categories_nr+1):
            category_bands = self.contest_category_bands(category)
            for category_band in category_bands:
                if category_band not in self.config.sections():
                    print('ERROR: Rules file has invalid band settings ({}) for category {}'.format(category_band, period))
                    sys.exit(13)

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
    def contest_bands_nr(self):
        try:
            self.config['contest']['bands']
            nr = int(self.config['contest']['bands'])
            return nr
        except KeyError:
            raise KeyError("Rules has missing field 'bands' in [contest] section")
        except ValueError:
            raise ValueError("The rules have invalid 'bands' value in [contest] section")

    def contest_band(self, number):
        """
        :param number: 
        :return: an instance of the config[bandX] 
        """
        return self.config['band'+str(number)]

    @property
    def contest_periods_nr(self):
        try:
            self.config['contest']['periods']
            nr = int(self.config['contest']['periods'])
            return nr
        except KeyError:
            raise KeyError("Rules has missing field 'periods' in [contest] section")
        except ValueError:
            raise ValueError("The rules have invalid 'periods' value in [contest] section")

    def contest_period(self, number):
        """
        :param number: 
        :return: an instance of config[periodX] 
        """
        return self.config['period'+str(number)]

    def contest_period_bands(self, number):
        """
        :param number: 
        :return: a list with bands names from config[periodX][bands] 
        """
        return [band for band in self.contest_period(number)['bands'].split(',')]

    @property
    def contest_categories_nr(self):
        try:
            self.config['contest']['categories']
            nr = int(self.config['contest']['categories'])
            return nr
        except KeyError:
            raise KeyError("Rules has missing field 'categories' in [contest] section")
        except ValueError:
            raise ValueError("The rules have invalid 'categories' value in [contest] section")

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
