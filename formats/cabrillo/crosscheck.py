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

Cabrillo cross-check: orchestration, band cross-check, QSO comparison.
"""
import re
from datetime import datetime, timedelta

from common.crosscheck import load_log_files, group_logs_by_operator, mark_older_duplicates, aggregate_qso_points

from .operator import Operator
from .scoring import apply_custom_scoring, _apply_10_minute_rule, _compute_multipliers


def run_crosscheck(log_class, rules=None, logs_folder=None, checklogs_folder=None):
    if not rules:
        print('No rules were provided')
        return {}
    if not logs_folder:
        print('Logs folder was not provided')
        return {}

    logs_instances = load_log_files(log_class, rules, logs_folder, checklogs_folder)
    if logs_instances is None:
        return {}

    operator_instances = group_logs_by_operator(logs_instances, Operator)
    mark_older_duplicates(operator_instances, rules)

    confirmed_pairs = set()
    for band in range(1, rules.contest_bands_nr + 1):
        crosscheck_band(operator_instances, rules, band, confirmed_pairs)

    _apply_10_minute_rule(operator_instances, rules)
    aggregate_qso_points(operator_instances)

    if rules.contest_multiplier_enabled:
        _compute_multipliers(operator_instances, rules)

    return operator_instances


def crosscheck_band(operator_instances, rules, band_nr, confirmed_pairs):
    special_callsign_list = rules.contest_special_callsign
    qso_points_normal = rules.contest_qso_points
    qso_points_special = rules.contest_special_qso_points

    for callsign1, ham1 in operator_instances.items():
        _had_qso_with = []
        log1 = _find_active_log(ham1, rules, band_nr)
        if log1 is None:
            continue

        for qso1 in log1.qsos:
            if qso1.valid is False:
                qso1.cc_confirmed = False
                qso1.cc_error = qso1.errors[0][2] if len(qso1.errors) >= 1 else 'Qso is not valid'
                continue

            if qso1.cc_confirmed is True:
                continue

            callsign2 = qso1.qso_fields['call'].upper()

            _, inside_period_nr1 = qso1.qso_inside_period()
            if '{}-period{}'.format(callsign2, inside_period_nr1) in _had_qso_with:
                qso1.cc_confirmed = False
                qso1.cc_error = 'Qso already confirmed'
                continue

            ham2 = operator_instances.get(callsign2, None)
            if not ham2:
                qso1.cc_confirmed = False
                qso1.cc_error = 'No log from {}'.format(callsign2)
                continue

            log2 = _find_active_log(ham2, rules, band_nr)
            if log2 is None:
                qso1.cc_confirmed = False
                qso1.cc_error = 'No valid log for this band from {}'.format(callsign2)
                continue

            qso2 = _find_matching_qso(qso1, log2, callsign1, inside_period_nr1)
            if qso2 is None:
                qso1.cc_confirmed = False
                qso1.cc_error = 'No qso found on {} log'.format(callsign2)
                continue

            _, partner_period_nr = qso2.qso_inside_period()

            distance = _compare_qso_pair(log1, qso1, log2, qso2)
            if distance is None:
                continue

            _had_qso_with.append('{}-period{}'.format(callsign2, partner_period_nr))

            qso1.cc_confirmed, qso1.cc_error = apply_custom_scoring(
                callsign1, callsign2, rules, qso1, confirmed_pairs,
                band_nr, qso_points_normal, qso_points_special,
                special_callsign_list, distance)


def _find_active_log(ham, rules, band_nr):
    _logs = ham.logs_by_band_regexp(rules.contest_band(band_nr)['regexp'])
    if not _logs:
        for log in ham.logs:
            if all((log.use_as_checklog is False,
                    log.ignore_this_log is False,
                    log.valid_header is True,
                    log.band and log.band.upper() == 'ALL')):
                return log
        return None
    for log in _logs:
        if all((log.use_as_checklog is False,
                log.ignore_this_log is False,
                log.valid_header is True)):
            return log
    return None


def _find_matching_qso(qso1, log2, expected_callsign, inside_period_nr1):
    for qso2 in log2.qsos:
        if qso2.valid is False:
            continue
        if qso2.qso_fields['call'].upper() != expected_callsign:
            continue
        _, inside_period_nr2 = qso2.qso_inside_period()
        if inside_period_nr1 != inside_period_nr2:
            continue
        return qso2
    return None


def _compare_qso_pair(log1, qso1, log2, qso2):
    try:
        distance = compare_qso(log1, qso1, log2, qso2)
    except ValueError as e:
        qso1.cc_confirmed = False
        qso1.cc_error = e
        return None
    return distance


def compare_qso(log1, qso1, log2, qso2):
    if qso1.valid is False:
        raise ValueError(qso1.errors[0][2])

    if qso2.valid is False:
        raise ValueError('Other ham qso is invalid')

    if log1.callsign != qso2.qso_fields['call'] or log2.callsign != qso1.qso_fields['call']:
        raise ValueError('Callsign mismatch')

    REGEX_DATE = r'(?P<year>\d{2})(?P<month>\d{2})(?P<day>\d{2})'
    REGEX_HOUR = r'(?P<hour>\d{2})(?P<minute>\d{2})'

    date_res1 = re.match(REGEX_DATE, qso1.qso_fields['date'])
    if not date_res1:
        raise ValueError('Date format is invalid : {}'.format(qso1.qso_fields['date']))
    hour_res1 = re.match(REGEX_HOUR, qso1.qso_fields['hour'])
    if not hour_res1:
        raise ValueError('Hour format is invalid : {}'.format(qso1.qso_fields['hour']))
    absolute_time1 = datetime(
        int(date_res1.group('year')), int(date_res1.group('month')),
        int(date_res1.group('day')),
        int(hour_res1.group('hour')), int(hour_res1.group('minute')))

    date_res2 = re.match(REGEX_DATE, qso2.qso_fields['date'])
    if not date_res2:
        raise ValueError('Date format is invalid : {}'.format(qso2.qso_fields['date']))
    hour_res2 = re.match(REGEX_HOUR, qso2.qso_fields['hour'])
    if not hour_res2:
        raise ValueError('Hour format is invalid : {}'.format(qso2.qso_fields['hour']))
    absolute_time2 = datetime(
        int(date_res2.group('year')), int(date_res2.group('month')),
        int(date_res2.group('day')),
        int(hour_res2.group('hour')), int(hour_res2.group('minute')))

    if abs(absolute_time1 - absolute_time2) > timedelta(minutes=5):
        raise ValueError('Different date/time between qso\'s')

    if qso1.qso_fields['mode'] != qso2.qso_fields['mode']:
        raise ValueError('Mode mismatch')
    if qso1.qso_fields['rst_sent'] != qso2.qso_fields['rst_recv']:
        raise ValueError('Rst mismatch (other ham)')
    if qso1.qso_fields['rst_recv'] != qso2.qso_fields['rst_sent']:
        raise ValueError('Rst mismatch')

    if qso1.qso_fields['nr_sent'] != qso2.qso_fields['nr_recv']:
        raise ValueError('Serial number mismatch (other ham)')
    if qso1.qso_fields['nr_recv'] != qso2.qso_fields['nr_sent']:
        raise ValueError('Serial number mismatch')

    return 1
