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
import re
from datetime import datetime

from common.dxcc import (
    lookup_callsign,
    is_yo_callsign,
    are_same_dxcc,
    get_callsign_continent,
    is_dracula_contest,
    is_dracula_special,
    is_yodx_contest,
    is_transylvania_county,
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


def _classify_qso_multiplier(qso, rules, caller_callsign=None):
    if not rules or not qso:
        return None
    exchange_field = rules.contest_multiplier_exchange_field
    special_exchange = rules.contest_multiplier_special_exchange
    return _compute_multiplier_for_qso(qso, rules, exchange_field, special_exchange, caller_callsign)


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

            mult_key = _classify_qso_multiplier(qso, rules, log.callsign)
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
                    mult_entry = _compute_multiplier_for_qso(qso, rules, exchange_field, special_exchange, log.callsign)
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
                    mult_entry = _compute_multiplier_for_qso(qso, rules, exchange_field, special_exchange, log.callsign)
                    if mult_entry:
                        unique_multipliers.add(mult_entry)
            for log in op_inst.logs:
                log.multiplier_count = len(unique_multipliers)
                log.final_score = log.qsos_points * log.multiplier_count if log.qsos_points else 0


def _is_yo_county_val(val):
    """Check if a value is a Romanian county abbreviation."""
    from common.dxcc import is_yo_county as _is_yo_county
    return _is_yo_county(val)


def _compute_multiplier_for_qso(qso, rules, exchange_field, special_exchange, caller_callsign=None):
    is_yodx = is_yodx_contest(rules)
    is_dracula = is_dracula_contest(rules)
    partner_call = qso.qso_fields.get('call', '').upper()

    if is_yodx:
        # YO DX HF Contest multiplier:
        # - When working a YO station → use received county code as multiplier
        # - When working a non-YO station → use DXCC entity as multiplier
        if not partner_call:
            return None
        if is_yo_callsign(partner_call):
            exchange_val = qso.qso_fields.get(exchange_field, '').strip().upper()
            if exchange_val and _is_yo_county_val(exchange_val):
                return ('YO_COUNTY', exchange_val)
            return None
        else:
            dxcc_info = lookup_callsign(partner_call)
            dxcc_key = dxcc_info['main_prefix'] if dxcc_info else partner_call[:2]
            return ('DXCC', dxcc_key)
    elif is_dracula:
        if not partner_call:
            return None
        if is_dracula_special(partner_call, rules):
            return ('DRC', partner_call)
        elif is_yo_callsign(partner_call):
            # DRACULA-004: per the official rules, a YO caller's multipliers
            # are DXCC entities + DRC only -- no county multiplier -- so a
            # YO-caller-to-YO-partner (non-special) contact contributes no
            # multiplier at all. Only a non-YO (foreign) caller gets a
            # YO_COUNTY multiplier for working a YO partner.
            if is_yo_callsign(caller_callsign):
                return None
            exchange_val = qso.qso_fields.get(exchange_field, '').strip().upper()
            # GAP-010 fix: validate against the real YO county table instead
            # of accepting any non-empty exchange value as a county
            # multiplier. This validation applies regardless of the
            # Transylvania scoring tier (DRACULA-003) -- is_yo_county checks
            # the full YO_COUNTIES set; is_transylvania_county is a separate,
            # narrower check used only for scoring-tier selection, not here.
            if exchange_val and _is_yo_county_val(exchange_val):
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
    elif custom_type == 'YODX':
        return _yodx_scoring(callsign1, callsign2, rules, qso1)
    elif custom_type is None:
        return _standard_scoring(callsign1, callsign2, rules, qso1, confirmed_pairs,
                                 band_nr, qso_points_normal, qso_points_special,
                                 special_callsign_list, distance)
    else:
        raise NotImplementedError('Custom scoring type "{}" is not implemented'.format(custom_type))


def _dracula_scoring(callsign1, callsign2, rules, qso1):
    """DRACULA-Transilvania scoring (specs/10-dracula-transylvania-2026.md
    DRACULA-002/003). callsign1 is the caller being scored, callsign2 is the
    confirmed partner. A Transylvania-region tier (8 pts, both directions)
    sits between the special-station tier (10) and the generic YO/foreign
    tier (5/2/1) -- detected via the same multiplier exchange field
    (rules.contest_multiplier_exchange_field, default nr_recv) that
    _compute_multiplier_for_qso already reads, not a separately configured
    field.
    """
    exchange_field = rules.contest_multiplier_exchange_field
    partner_exchange = qso1.qso_fields.get(exchange_field, '').strip().upper()

    if is_dracula_special(callsign2, rules):
        qso1.points = rules.contest_non_yo_to_special_points
    elif is_yo_callsign(callsign1):
        if is_yo_callsign(callsign2):
            if is_transylvania_county(partner_exchange):
                qso1.points = rules.contest_yo_to_transylvania_points
            else:
                qso1.points = rules.contest_yo_to_yo_points
        else:
            qso1.points = rules.contest_yo_to_nonyo_points
    else:
        if is_yo_callsign(callsign2):
            if is_transylvania_county(partner_exchange):
                qso1.points = rules.contest_non_yo_to_transylvania_points
            else:
                qso1.points = rules.contest_non_yo_to_yo_points
        else:
            if are_same_dxcc(callsign1, callsign2):
                qso1.points = rules.contest_non_yo_same_country_points
            else:
                qso1.points = rules.contest_non_yo_dxcc_points
    return True, []


def _yodx_scoring(callsign1, callsign2, rules, qso1):
    """YO DX HF Contest scoring with continent-based differentiation.

    Scoring logic (callsign1 is the 'caller' being scored):
      - YO works YO     → 0 pts
      - YO works non-YO:
          * same continent (EU) → yo_to_nonyo_same_continent_points
          * different continent  → yo_to_nonyo_points
      - non-YO works YO:
          * same continent       → non_yo_to_yo_same_continent_points
          * different continent  → non_yo_to_yo_points
      - non-YO works non-YO:
          * same DXCC            → non_yo_same_country_points
          * different DXCC       → non_yo_dxcc_points
    """
    if is_yo_callsign(callsign1):
        # YO station calls
        if is_yo_callsign(callsign2):
            qso1.points = 0
        else:
            continent2 = get_callsign_continent(callsign2)
            if continent2 == 'EU':
                qso1.points = rules.contest_yo_to_nonyo_same_continent_points
            else:
                qso1.points = rules.contest_yo_to_nonyo_points
    else:
        # Non-YO station calls
        if is_yo_callsign(callsign2):
            # QSO with YO station: always 8 points regardless of continent
            qso1.points = rules.contest_non_yo_to_yo_points
        else:
            if are_same_dxcc(callsign1, callsign2):
                qso1.points = rules.contest_non_yo_same_country_points
            else:
                continent1 = get_callsign_continent(callsign1)
                continent2 = get_callsign_continent(callsign2)
                if continent1 and continent2 and continent1 == continent2:
                    qso1.points = rules.contest_non_yo_same_continent_points
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


def _derive_band_nr_for_witness_qso(qso, log, rules):
    """Derive a band_nr for a QSO being (re-)scored outside the normal
    per-band crosscheck loop.

    There is no existing precedent for deriving band_nr from a bare
    Log/QSO pair outside that loop (DRACULA-005's witness-confirmation pass
    runs once, contest-wide, after all bands have already been
    cross-checked) -- this implementation's choice, documented here per the
    spec's request:
      1. Try the same frequency-parsing heuristic the 10-minute rule already
         uses (_get_band_from_frequency) against the QSO's own frequency
         token -- the most accurate source when available.
      2. Fall back to matching the owning log's own CATEGORY-BAND value
         against each configured [bandN] regexp -- handles e.g. an
         'ALL'-band log whose own QSO frequency might not cleanly match a
         single configured band center.
      3. Finally default to band 1, so a band_nr is always available for
         apply_custom_scoring's legacy standard-scoring branch. In practice
         this default is very unlikely to matter: band_nr is not read at all
         by the DRACULA/YODX custom-scoring functions this feature is
         primarily intended for, only by the legacy distance*multiplier
         fallback within _standard_scoring when no [scoring] qso_points is
         configured.
    """
    tokens = qso.qso_line.strip().split()
    if len(tokens) >= 2:
        band_nr = _get_band_from_frequency(tokens[1], rules)
        if band_nr is not None:
            return band_nr

    if log.band:
        for band_nr in range(1, rules.contest_bands_nr + 1):
            try:
                if re.match(rules.contest_band(band_nr)['regexp'], log.band, re.IGNORECASE):
                    return band_nr
            except (KeyError, TypeError, re.error):
                continue

    return 1


def _apply_witness_confirmation(operator_instances, rules):
    """DRACULA-005 (specs/10-dracula-transylvania-2026.md): confirm and score
    QSOs against a partner callsign that never submitted its own log, once
    at least `rules.contest_witness_confirmation_min_logs` *distinct*
    operators (contest-wide, not per-band; checklogs included) independently
    logged a contact with that same phantom callsign.

    Generic, opt-in (default threshold 0 = disabled) -- not hardcoded to
    DRACULA. Must run after the normal per-band crosscheck loop and the
    10-minute rule, but before aggregate_qso_points/_compute_multipliers,
    since it can newly confirm and score QSOs that must then be included in
    both.
    """
    if not rules or rules.contest_witness_confirmation_min_logs <= 0:
        return
    threshold = rules.contest_witness_confirmation_min_logs

    # Pass 1: collect QSOs actually pending witness confirmation -- valid,
    # non-ignored, and whose cross-check failure is specifically "partner has
    # zero submitted logs at all". Re-derived directly (rather than
    # string-matching cc_error == 'No log from {callsign2}') per the spec's
    # own note that this is more resilient to message-wording changes.
    pending = []  # list of (qso, log, caller_callsign, phantom_callsign)
    phantoms_of_interest = set()
    for caller_callsign, op_inst in operator_instances.items():
        for log in op_inst.logs:
            if log.ignore_this_log or not log.valid_header:
                continue
            for qso in log.qsos:
                if not qso.valid or qso.cc_confirmed is not False:
                    continue
                phantom = qso.qso_fields.get('call', '').upper()
                if not phantom or phantom in operator_instances:
                    continue
                pending.append((qso, log, caller_callsign, phantom))
                phantoms_of_interest.add(phantom)

    if not phantoms_of_interest:
        return

    # Pass 2: contest-wide witness tally per phantom callsign. Every valid
    # QSO in any non-ignored, header-valid log (checklogs included) whose
    # partner is that phantom callsign counts its OWN log's operator as one
    # witness -- independent of that QSO's cc_confirmed status. This
    # independence from cc_confirmed is what makes "checklogs count as
    # witnesses" actually work: a checklog's own QSOs never run through the
    # normal per-band crosscheck at all (_find_active_log excludes checklogs
    # unconditionally on both sides, see XC-004/GAP-005), so cc_confirmed is
    # never set to False for them -- scanning for the phantom callsign
    # directly, rather than filtering on cc_confirmed, is required to count
    # them. Distinct *operators* are tallied (a set), not distinct log
    # files, so one operator claiming the same phantom across several of
    # their own band logs counts once.
    witnesses = {phantom: set() for phantom in phantoms_of_interest}
    for caller_callsign, op_inst in operator_instances.items():
        for log in op_inst.logs:
            if log.ignore_this_log or not log.valid_header:
                continue
            for qso in log.qsos:
                if not qso.valid:
                    continue
                phantom = qso.qso_fields.get('call', '').upper()
                if phantom in witnesses:
                    witnesses[phantom].add(caller_callsign)

    special_callsign_list = rules.contest_special_callsign
    qso_points_normal = rules.contest_qso_points
    qso_points_special = rules.contest_special_qso_points
    # Scoped to this witness-confirmation pass only -- separate from the
    # per-band confirmed_pairs set, since these QSOs were never part of any
    # band's normal confirmation pass.
    confirmed_pairs_witness = set()

    for qso, log, caller_callsign, phantom in pending:
        if len(witnesses[phantom]) < threshold:
            # Threshold not met: leave exactly as-is (cc_confirmed=False,
            # original cc_error) -- this pass must not change anything about
            # these QSOs.
            continue

        # Threshold met: trust the witnessing caller's own submitted
        # RST/exchange for their own scoring -- there is no partner log to
        # cross-verify against, and inter-witness exchange consensus is
        # explicitly not required. distance=1 matches Cabrillo's existing
        # qth_distance stub (CAB-010) -- no locator data exists for a
        # phantom partner anyway.
        band_nr = _derive_band_nr_for_witness_qso(qso, log, rules)
        qso.cc_confirmed, qso.cc_error = apply_custom_scoring(
            caller_callsign, phantom, rules, qso, confirmed_pairs_witness,
            band_nr, qso_points_normal, qso_points_special,
            special_callsign_list, distance=1)
