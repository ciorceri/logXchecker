import re

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
    qsos = []

    def __init__(self, path, checklog=False):
        self.path = path
        self.log_content = self.read_file_content(self.path)

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
        fieldU = str(field).upper() + '='
        for line in self.log_content:
            if line.upper().startswith(fieldU):
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
        for line in self.log_content:
            if line.upper().startswith(qso_record_start):
                do_read_qso = True
            if line.upper().startswith(qso_record_end):
                do_read_qso = False
            if do_read_qso:
                qso_lines.append(line)

                # validate qso lines

    def valid_qso_line(self, line):
        """
        This will validate the a line of qso from .edi log
        :param line:
        :return: True or False
        """
        qso_min_line_lenght = 40

        if len(line) < qso_min_line_lenght:
            raise LogException('QSO line is too short', line)
        res = re.match(regexMinimalQsoCheck, line)
        if not res:
            raise LogException('Minimal QSO check didn\'t pass', line)
        res = re.match(regexMediumQsoCheck, line)
        if not res:
            raise LogException('Medium QSO check didn\'t pass', line)
        return True

    def dump_summary(self):
        """
        Based on the output format (text, html...) this will output a summary of the log
        """
        pass


class LogQso(object):
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


class LogException(Exception):
    def __init__(self, message, line):
        self.message = message
        self.line = line
