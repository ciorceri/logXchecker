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

Cabrillo scoring: custom/standard scoring, multipliers, 10-minute rule.
"""
from datetime import datetime

from common.dxcc import (
    lookup_callsign,
    is_yo_callsign,
    are_same_dxcc,
    is_dracula_contest,
    is_dracula_special,
)


def _get_band_from_frequency(freq_str, rules):
    if not freq_str or not rules:
        return None

    try:
        if '.' in freq_str:
            freq_mhz = float(freq_str)
        else:
            freq_val = int(freq_str)
            if freq_val >= 1000000:
                freq_mhz = freq_val / 1000000.0
            elif freq_val >= 10000:
                freq_mhz = freq_val / 1000.0
            else:
                freq_mhz = float(freq_val)
    except (ValueError, TypeError):
        return None

    for band_nr in range(1, rules.contest_bands_nr + 1):
        try:
            band_freq = float(rules.contest_band(band_nr)['band'])
        except (ValueError, KeyError, TypeError):
            continue

        tolerance = band_freq * 0.05
        if abs(freq_mhz - band_freq) <= tolerance:
            return band_nr

    return None


def _parse_qso_datetime(qso):
    try:
        return datetime.strptime(
            '20' + qso.qso_fields['date'] + ' ' + qso.qso_fields['hour'],
            '%Y%m%d %H%M')
    except (ValueError, KeyError, TypeError):
        return None


def _classify_qso_multiplier(qso, rules):
    if not rules or not qso:
        return None
    exchange_field = rules.contest_multiplier_exchange_field
    special_exchange = rules.contest_multiplier_special_exchange
    return _compute_multiplier_for_qso(qso, rules, exchange_field, special_exchange)


def _apply_10_minute_rule(operator_instances, rules):
    if not rules:
        return

    for op_callsign, op_inst in operator_instances.items():
        is_multi = any(
            log.category and log.category.upper() == 'MULTI'
            for log in op_inst.logs
        )
        if not is_multi:
            continue

        all_qsos = []
        for log in op_inst.logs:
            if log.ignore_this_log or not log.valid_header:
                continue
            for qso in log.qsos:
                if not qso.valid or qso.cc_confirmed is not True:
                    continue
                dt = _parse_qso_datetime(qso)
                if dt is None:
                    continue
                all_qsos.append((dt, qso, log))

        if not all_qsos:
            continue

        all_qsos.sort(key=lambda x: x[0])

        current_band_nr = None
        session_first_time = None
        seen_multipliers = set()

        for dt, qso, log in all_qsos:
            tokens = qso.qso_line.strip().split()
            if len(tokens) < 2:
                continue
            freq_str = tokens[1]

            qso_band_nr = _get_band_from_frequency(freq_str, rules)
            if qso_band_nr is None:
                continue

            mult_key = _classify_qso_multiplier(qso, rules)
            is_new_mult = mult_key is not None and mult_key not in seen_multipliers

            if current_band_nr is None:
                current_band_nr = qso_band_nr
                session_first_time = dt
            elif qso_band_nr == current_band_nr:
                pass
            else:
                elapsed_minutes = (dt - session_first_time).total_seconds() / 60.0

                if elapsed_minutes < 10 and not is_new_mult:
                    qso.points = 0
                else:
                    current_band_nr = qso_band_nr
                    session_first_time = dt

            if mult_key:
                seen_multipliers.add(mult_key)


def _compute_multipliers(operator_instances, rules):
    exchange_field = rules.contest_multiplier_exchange_field
    special_exchange = rules.contest_multiplier_special_exchange
    per_band_mult = rules.contest_multiplier_per_band

    for op, op_inst in operator_instances.items():
        if per_band_mult:
            for log in op_inst.logs:
                band_unique_mult = set()
                for qso in log.qsos:
                    if not qso.cc_confirmed or not (qso.points and qso.points > 0):
                        continue
                    mult_entry = _compute_multiplier_for_qso(qso, rules, exchange_field, special_exchange)
                    if mult_entry:
                        band_unique_mult.add(mult_entry)
                log.multiplier_count = len(band_unique_mult)
                log.final_score = log.qsos_points * log.multiplier_count if log.qsos_points else 0
        else:
            unique_multipliers = set()
            for log in op_inst.logs:
                for qso in log.qsos:
                    if not qso.cc_confirmed or not (qso.points and qso.points > 0):
                        continue
                    mult_entry = _compute_multiplier_for_qso(qso, rules, exchange_field, special_exchange)
                    if mult_entry:
                        unique_multipliers.add(mult_entry)
            for log in op_inst.logs:
                log.multiplier_count = len(unique_multipliers)
                log.final_score = log.qsos_points * log.multiplier_count if log.qsos_points else 0


def _compute_multiplier_for_qso(qso, rules, exchange_field, special_exchange):
    is_dracula = is_dracula_contest(rules)
    partner_call = qso.qso_fields.get('call', '').upper()

    if is_dracula:
        if not partner_call:
            return None
        if is_dracula_special(partner_call, rules):
            return ('DRC', partner_call)
        elif is_yo_callsign(partner_call):
            exchange_val = qso.qso_fields.get(exchange_field, '').strip().upper()
            if exchange_val:
                return ('YO_COUNTY', exchange_val)
            return None
        else:
            dxcc_info = lookup_callsign(partner_call)
            dxcc_key = dxcc_info['main_prefix'] if dxcc_info else partner_call[:2]
            return ('DXCC', dxcc_key)
    else:
        exchange_val = qso.qso_fields.get(exchange_field, '').strip().upper()
        county_val = _extract_county_from_exchange(exchange_val)
        if not county_val:
            return None
        if special_exchange and county_val == special_exchange:
            if partner_call:
                return ('CAT_A', partner_call)
            return None
        return ('COUNTY', county_val)


def _extract_county_from_exchange(exchange_val):
    if not exchange_val:
        return ''
    parts = exchange_val.strip().upper().split()
    if len(parts) >= 2:
        return parts[-1]
    return parts[0]


def apply_custom_scoring(callsign1, callsign2, rules, qso1, confirmed_pairs,
                         band_nr, qso_points_normal, qso_points_special,
                         special_callsign_list, distance):
    custom_type = rules.contest_custom_scoring if rules else None
    if custom_type == 'DRACULA':
        return _dracula_scoring(callsign1, callsign2, rules, qso1)
    elif custom_type is None:
        return _standard_scoring(callsign1, callsign2, rules, qso1, confirmed_pairs,
                                 band_nr, qso_points_normal, qso_points_special,
                                 special_callsign_list, distance)
    else:
        raise NotImplementedError('Custom scoring type "{}" is not implemented'.format(custom_type))


def _dracula_scoring(callsign1, callsign2, rules, qso1):
    if is_dracula_special(callsign2, rules):
        qso1.points = rules.contest_non_yo_to_special_points
    elif is_yo_callsign(callsign1):
        if is_yo_callsign(callsign2):
            qso1.points = 0
        else:
            qso1.points = rules.contest_yo_to_nonyo_points
    else:
        if is_yo_callsign(callsign2):
            qso1.points = rules.contest_non_yo_to_yo_points
        else:
            if are_same_dxcc(callsign1, callsign2):
                qso1.points = rules.contest_non_yo_same_country_points
            else:
                qso1.points = rules.contest_non_yo_dxcc_points
    return True, []


def _standard_scoring(callsign1, callsign2, rules, qso1, confirmed_pairs,
                      band_nr, qso_points_normal, qso_points_special,
                      special_callsign_list, distance):
    if callsign2.upper() in special_callsign_list:
        qso1.points = qso_points_special
    elif qso_points_normal != 1:
        pair_key = (qso1.qso_fields['mode'], min(callsign1, callsign2), max(callsign1, callsign2))
        if pair_key not in confirmed_pairs:
            confirmed_pairs.add(pair_key)
            qso1.points = qso_points_normal
        else:
            qso1.points = 0
    else:
        qso1.points = distance * int(rules.contest_band(band_nr)['multiplier'])
    return True, []
