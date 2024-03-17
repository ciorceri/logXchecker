"""
Copyright 2016-2024 Ciorceri Petru Sorin (yo5pjb)

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

import cabrillo

class Operator(object):
    """
    Keep operator callsign, info and logs path
    """
    callsign = None
    logs = []           # list with Log() instances

    def __init__(self, callsign):
        self.callsign = callsign
        self.logs = []

    def add_log_by_path(self, path, rules=None, checklog=False):
        self.logs.append(Log(path, rules=rules, checklog=checklog))

    def add_log_instance(self, log):
        self.logs.append(log)



class Log(object):
    use_as_checklog = False
    ignore_this_log = None  # if flag is set this log will not be used in cross-check

    qsos = list()   # list with LogQso instances
    qsos_points = None
    qsos_confirmed = None

    def __init__(self, path, rules=None, checklog=False):
        self.path = path
        self.rules = rules
        self.use_as_checklog = checklog
        self.ignore_this_log = False

        # do header validation

        # get qso's

class LogQso(object):
    def __init__(self, qso_line=None, qso_line_number=None, rules=None):
        self.qso_line = qso_line
        self.line_nr = qso_line_number
        self.rules = rules
        self.valid = True

        # generic QSO validation

        # contest specific QSO validation  

def crosscheck_logs_filter(log_class, rules=None, logs_folder=None, checklogs_folder=None):
    pass

def crosscheck_logs(operator_instances, rules, band_nr):
    pass

def compare_qso(log1, qso1, log2, qso2):
    pass