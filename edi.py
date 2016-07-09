class Operator(object):
    """
    This will keep the info & logs for each ham operator (team)
    """
    callsign = None
    info = {}
    logs = []

    def __init__(self):
        pass


class Log(object):
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
