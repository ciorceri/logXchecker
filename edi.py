import re
from collections import namedtuple

regexMinimalQsoCheck = ".*?;.*?;.*?;.*?;.*?;.*?;.*?;.*?;.*?;.*?;.*?;.*?;.*?;.*?;"
regexMediumQsoCheck = "^\d{6};\d{4};.*?;\d;\d{2,3};\d{2,4};\d{2,3};\d{2,4};.*?;.*?;.*?;.*?;.*?;.*?;"


class Operator(object):
    """
    This will keep the info & logs for each ham operator (team)
    """
    callsign = None
    info = {}
    logs = []

    def __init__(self, callsign):
        self.callsign = callsign
        self.logs = []

    def add_log(self, path):
        self.logs.append(Log(path))


class Log(object):
    """
    This will keep a single log information (header + list of LogQso instances)
    """
    path = None
    log_content = None  # full content of the log
    callsign = None
    maidenhead_locator = None
    band = None
    section = None
    qsos_tuple = namedtuple('qso_tuple', ['line', 'qso'])
    qsos = []
    errors_tuple = namedtuple('errors_tuple', ['line', 'qso', 'error'])
    errors = []

    def __init__(self, path, checklog=False):
        self.path = path
        self.log_content = self.read_file_content(self.path)
        _temp = self.get_field('PCall')
        if _temp is None:
            raise ValueError('The PCall field is not present')
        if len(_temp) > 1:
            raise ValueError('The PCall field is present multiple times')
        self.callsign = _temp[0]
        self.qsos = []
        qsos = self.get_qsos()

    def read_file_content(self, path):
        try:
            with open(self.path, 'r') as f:
                content = f.readlines()
        except IOError as why:
            raise
        except Exception as why:
            raise
        return content

    def validate_log_content(self):
        pass

    def get_field(self, field):
        """
        Will read the log_content and will return field value
        """

        if self.log_content is None:
            raise FileNotFoundError("Log content is not available")

        value = []
        _field = str(field).upper() + '='
        for line in self.log_content:
            if line.upper().startswith(_field):
                value.append(line.split('=', 1)[1].strip())
        return value or None

    def get_qsos(self):
        """
        Will read the log_content and will return a list of LogQso
        """
        qso_record_start = "[QSORECORDS"
        qso_record_end = "[END;"
        qso_lines = []
        do_read_qso = False

        # read qso lines
        for (index, line) in enumerate(self.log_content):
            if line.upper().startswith(qso_record_start):
                do_read_qso = True
                continue
            if line.upper().startswith(qso_record_end):
                do_read_qso = False
                continue
            if do_read_qso:
                qso_lines.append((index, line.strip()))

        # validate qso lines
        for qso in qso_lines:
            message = self.valid_qso_line(qso[1])
            if message is None:
                self.qsos.append(self.qsos_tuple(line=qso[0], qso=qso[1]))
            else:
                self.errors.append(self.errors_tuple(line=qso[0], qso=qso[1], error=message))

    def valid_qso_line(self, line):
        """
        This will validate the a line of qso from .edi log
        :param line:
        :return: None or error message
        """
        qso_min_line_lenght = 40

        if len(line) < qso_min_line_lenght:
            return 'QSO line is too short'
        res = re.match(regexMinimalQsoCheck, line)
        if not res:
            return 'Minimal QSO checks didn\'t pass'
        res = re.match(regexMediumQsoCheck, line)
        if not res:
            return 'QSO checks didn\'t pass'
        return None

    def dump_summary(self):
        """
        Based on the output format (text, html...) this will output a summary of the log
        """
        pass


class LogQso(object):
    """
    This will keep a single QSO
    """
    qsoFields = {'date': None,
                 'hour': None,
                 'callsign': None,
                 'mode':None,
                 'rst_sent':None,
                 'nr_sent':None,
                 'rst_recv':None,
                 'nr_recv':None,
                 'exchange_recv':None,
                 'wwl_recv':None,
                 'points':None,
                 'new_exchange': None,
                 'new_wwl': None,
                 'new_dxcc': None,
                 'duplicate_qso': None,
                 }

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


class LogException(Exception):
    def __init__(self, message, line):
        self.message = message
        self.line = line
