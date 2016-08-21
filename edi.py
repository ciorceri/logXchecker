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
        :return:
        """

        if self.log_content is None:
            raise FileNotFoundError("Log content is not available")

        value = []
        fieldU = str(field).upper()+'='
        for line in self.log_content:
            if line.upper().startswith(fieldU):
                value.append(line.split('=', 1)[1].strip())
        return value or None

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
