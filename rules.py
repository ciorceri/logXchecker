"""
Copyright 2016 Ciorceri Petru Sorin

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

        [band1]
        band=144
        regexp=(144|145|2m)

        [band2]
        band=432
        regexp=(430|432|70cm)

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
        regexp=(so|single)
        bands=band1

        [category2]
        name=Single Operator 432
        regexp=(so|single)
        bands=band2

        [category3]
        name=Multi Operator
        regexp=(mo|multi)
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

    def read_config_file_content(self, path):
        try:
            with open(self.path, 'r') as f:
                content = f.read()
        except IOError as why:
            raise
        except Exception as why:
            raise
        return content

    def validate_rules(self):
        # validata contest fields
        try:
            self.contest_bands_nr
            self.contest_periods_nr
            self.contest_categories_nr
        except KeyError as e:
            print('ERROR: Rules has missing fields from [contest] section')
            sys.exit(9)

        # validate bands number and fields
        if self.contest_bands_nr < 1:
            print('ERROR: Rules file has invalid settings for [contest] secttion -> band field')
            sys.exit(10)
        try:
            for band in range(1, self.contest_bands_nr+1):
                self.contest_band(band)
                self.contest_band(band)['band']
                self.contest_band(band)['regexp']
        except KeyError as e:
            print('ERROR: Rules file has invalid settings for band', band)
            sys.exit(10)

        # validate period number and fields
        if self.contest_periods_nr < 1:
            print("ERROR: Rules file has invalid settings for [contest] section -> periods field")
            sys.exit(11)
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
            sys.exit(11)

        # validate period number and fields
        if self.contest_categories_nr < 1:
            print("ERROR: Rules file has invalid settings for [contest] section -> categories field")
            sys.exit(12)
        try:
            for category in range(1, self.contest_categories_nr+1):
                self.contest_category(category)
                self.contest_category(category)['name']
                self.contest_category(category)['regexp']
                self.contest_category(category)['bands']
        except KeyError as e:
            print('ERROR: Rules file has invalid settings for category', category)
            sys.exit(12)

        # validate date and time
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
            sys.exit(1)

        # validate category & period bands
        pass

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
            nr = int(self.config['contest']['bands'])
            return nr
        except:
            raise ValueError("The contest bands value is not valid")

    def contest_band(self, number):
        return self.config['band'+str(number)]

    @property
    def contest_periods_nr(self):
        try:
            nr = int(self.config['contest']['periods'])
            return nr
        except:
            raise ValueError("The contest periods value is not valid")

    def contest_period(self, number):
        return self.config['period'+str(number)]

    def contest_period_bands(self, number):
        for band in self.contest_period(number)['bands'].split(','):
            yield band

    @property
    def contest_categories_nr(self):
        try:
            nr = int(self.config['contest']['categories'])
            return nr
        except:
            raise ValueError("The contest categories value is not valid")

    def contest_category(self, number):
        return self.config['category'+str(number)]
