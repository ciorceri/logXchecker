import argparse
import importlib
import os
import sys
import configparser
from datetime import datetime

import edi
import version


class ArgumentParser():
    """
    Parses the parameters from command line
    """

    def check_format_value(self, arg):
        """
        :param arg: specifies log file format (edi, adif, cbr)
        :return: arg
        :raise: ArgumentTypeError
        """
        valid_formats = ('EDI', 'ADIF', 'CABRILLO')
        if arg.upper() in valid_formats:
            return arg.upper()
        raise argparse.ArgumentTypeError('Format "%s" is an invalid value' % arg)

    def check_output_value(self, arg):
        """
        :param arg: specifies the output format (text, html, json, yml)
        :return: arg
        :raise: ArgumentTypeError
        """
        valid_output = ('TXT', 'TEXT', 'HTML', 'JSON', 'YML')
        if arg.upper() in valid_output:
            return arg
        raise argparse.ArgumentTypeError('Output "%s" is an invalid value' % arg)

    def __init__(self):
        self.parser = argparse.ArgumentParser(description='log cross checker')
        self.parser.add_argument('-f', '--format', type=self.check_format_value, required=True,
                                 help="Log format: edi, adif, cabrillo")
        self.parser.add_argument('-r', '--rules', type=str, required=False, help='INI file with contest rules')
        self.parser.add_argument('-o', '--output', type=self.check_output_value, required=False,
                                 help='Output format: text, html, json, yml')
        group = self.parser.add_mutually_exclusive_group()
        group.add_argument('-slc', '--singlelogcheck', type=str, default=False, help='single log check')
        group.add_argument('-mlc', '--multilogcheck', type=str, default=False, help='multiple log check')

    def parse(self, args):
        return self.parser.parse_args(args)


class Contest(object):
    """
    This is the main contest class which will held an instance of 'Rules' class.
    It will create a list of instances of 'Operator' class
    and each 'Operator' instance will have a list of 'Log' class
    and each 'Log' instance will keep a lot of instances of 'LogQso'
    """


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
        self.config.read_string(self.read_file_content(self.path))
        self.validate_rules()

    def read_file_content(self, path):
        try:
            with open(self.path, 'r') as f:
                content = f.read()
        except IOError as why:
            raise
        except Exception as why:
            raise
        return content

    def validate_rules(self):
        # validate bands number and fields
        try:
            for band in range(1, self.contest_bands_nr+1):
                self.contest_band(band)
                self.contest_band(band)['band']
                self.contest_band(band)['regexp']
        except KeyError as e:
            print('ERROR: Rules file has invalid settings for band', band)
            sys.exit(1)

        # validate period number and fields
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
            sys.exit(1)

        # validate period number and fields
        try:
            for category in range(1, self.contest_categories_nr+1):
                self.contest_category(category)
                self.contest_category(category)['name']
                self.contest_category(category)['regexp']
                self.contest_category(category)['bands']
        except KeyError as e:
            print('ERROR: Rules file has invalid settings for category', category)
            sys.exit(1)

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
        return int(self.config['contest']['bands'])

    def contest_band(self, number):
        return self.config['band'+str(number)]

    @property
    def contest_periods_nr(self):
        return int(self.config['contest']['periods'])

    def contest_period(self, number):
        return self.config['period'+str(number)]

    def contest_period_bands(self, number):
        for band in self.contest_period(number)['bands'].split(','):
            yield band

    @property
    def contest_categories_nr(self):
        return int(self.config['contest']['categories'])

    def contest_category(self, number):
        return self.config['category'+str(number)]


class Operator(edi.Operator):
    """
    This will keep the info & logs for each ham operator (team)
    """
    callsign = None
    info = {}
    logs = []

    def __init__(self):
        pass


class Log(edi.Log):
    """
    This will keep a single log information (header + list of LogQso instances)
    """
    path = None

    def __init__(self):
        pass

    def validate_log_name(self):
        pass

    def validate_log_content(self):
        pass

    def get_summary(self):
        """
        Based on the output format (text, html...) this will output a summary of the log
        """
        pass


class LogQso(edi.LogQso):
    """
    This will keep a single QSO
    """
    qsoFields = {}

    def __init__(self):
        pass

    def qso_parser(self):
        """
        This should parse a qso based on log format
        """
        pass

    def validate_qso(self):
        """
        This will validate a parsed qso based on generic rules (simple validation) or based on rules
        """
        pass


# This function is not used at this moment since I have support only for 'edi format'
def load_log_format_module(module_name):
    """
    :param module_name: path to module who knows to parse & read a specified file format (edi, adif, cbr)
    :return:
    """
    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        print("ERROR:", e)
        sys.exit(1)
    return module

    # class Module(module):
    #     def __init__(self):
    #         pass
    #
    #     def validate_rules(self):
    #         pass


def main():
    print(version.__project__,  version.__version__)
    args = ArgumentParser().parse(sys.argv[1:])
    if args.format:
        # lfmodule = load_log_format_module(args.format)
        lfmodule = edi

    # if 'validate one log'
    if args.slc:
        print('Validate log: ', args.slc)
        if not os.path.isfile(args.slc):
            raise FileNotFoundError(args.slc)

    elif args.mlc:
        print('Validate folder: ', args.mlc)
        if not os.path.isdir(args.mlc):
            raise FileNotFoundError(args.mlc)

if __name__ == '__main__':
    main()
