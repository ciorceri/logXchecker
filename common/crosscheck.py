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

Shared cross-check pipeline functions used by all log format modules.
"""
import os


def load_log_files(log_class, rules, logs_folder, checklogs_folder):
    """Load and validate all log files from the given folders.

    Returns a list of Log instances, or None on error.
    """
    if not os.path.isdir(logs_folder):
        print('Cannot open logs folder : {}'.format(logs_folder))
        return None

    logs_instances = []
    for filename in os.listdir(logs_folder):
        logs_instances.append(log_class(os.path.join(logs_folder, filename), rules=rules))

    if checklogs_folder:
        if os.path.isdir(checklogs_folder):
            for filename in os.listdir(checklogs_folder):
                logs_instances.append(log_class(os.path.join(checklogs_folder, filename), rules=rules, checklog=True))
        else:
            print('Cannot open checklogs folder : {}'.format(checklogs_folder))
            return None

    return logs_instances


def group_logs_by_operator(logs_instances, Operator):
    """Group Log instances by operator callsign into Operator objects."""
    operator_instances = {}
    for log in logs_instances:
        if not log.valid_header:
            log.ignore_this_log = True
            continue
        callsign = log.callsign.upper()
        if not operator_instances.get(callsign, None):
            operator_instances[callsign] = Operator(callsign)
        operator_instances[callsign].add_log_instance(log)
    return operator_instances


def mark_older_duplicates(operator_instances, rules):
    """For multiple logs per operator on the same band, mark older ones as ignored."""
    for band in range(1, rules.contest_bands_nr + 1):
        for _, _ham in operator_instances.items():
            _logs = _ham.logs_by_band_regexp(rules.contest_band(band)['regexp'])
            mark_older_logs(_logs)


def aggregate_qso_points(operator_instances):
    """Sum up points and confirmed QSO counts for each log."""
    for op, op_inst in operator_instances.items():
        for log in op_inst.logs:
            points = 0
            confirmed = 0
            for qso in log.qsos:
                if qso.points and qso.points > 0:
                    points += qso.points
                    confirmed += 1
            log.qsos_points = points
            log.qsos_confirmed = confirmed


def mark_older_logs(log_list):
    """Mark older log files (by timestamp) with ignore_this_log."""
    maxDate = 0
    maxDateLogId = None
    for log in log_list:
        date = os.path.getmtime(log.path)
        if date > maxDate:
            maxDate = date
            maxDateLogId = id(log)
    for log in log_list:
        if maxDateLogId != id(log):
            log.ignore_this_log = True
