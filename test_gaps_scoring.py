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

Characterization tests for known gaps/bugs recorded in
specs/09-known-gaps-and-deviations.md. These tests PIN DOWN current
behavior (including buggy/undesired behavior) - they are NOT meant to
assert "correct" behavior. If one of these tests starts failing, it
means the underlying gap has been fixed (intentionally or not), and the
corresponding entry in specs/09-known-gaps-and-deviations.md (and the
spec files it references) must be updated alongside the code change.
"""
from types import SimpleNamespace
from typing import List
from unittest import TestCase, mock
from unittest.mock import patch

import logXchecker
import rules
import rules_hf

import formats.cabrillo as cabrillo
from test_cabrillo import DRACULA_RULES, CABRILLO_CROSSCHECK_RULES


class TestGap003CabrilloCallregexpNotEnforced(TestCase):
    """GAP-003: `[extra] callregexp` filtering exists in EDI's QSO validator
    (formats/edi.py) but has no equivalent in Cabrillo's QSO validator
    (formats/cabrillo/qso.py) - a Cabrillo QSO with a callsign that would be
    rejected by `callregexp` still validates successfully today."""

    @mock.patch('os.path.isfile')
    def test_cabrillo_qso_ignores_callregexp(self, mock_isfile: mock.MagicMock) -> None:
        # callregexp only allows YO/YP/YQ/YR prefixed callsigns (national-contest style filter)
        rules_with_callregexp: str = CABRILLO_CROSSCHECK_RULES + """
[extra]
callregexp=yo|yp|yq|yr
"""
        mock_isfile.return_value = True
        mo = mock.mock_open(read_data=rules_with_callregexp)
        with patch('builtins.open', mo, create=True):
            _rules = rules_hf.RulesHf('some_rule_file.rules')

        # sanity: the rules object does carry the callregexp value, and it
        # would reject 'DL1ABC' if anything actually consulted it.
        self.assertEqual(_rules.contest_extra_field_value('callregexp'), 'yo|yp|yq|yr')

        # A QSO whose partner callsign is 'DL1ABC' -- clearly rejected by
        # 'yo|yp|yq|yr' -- but Cabrillo's QSO validator never looks at
        # contest_extra_field_value('callregexp') at all.
        qso_line = 'QSO: 14000 CW 2026-10-31 1200 YO5PJB          599 CJ  DL1ABC          599 001'
        lq = cabrillo.LogQso(qso_line, 1, rules=_rules)

        self.assertEqual(lq.qso_fields['call'], 'DL1ABC')
        self.assertTrue(lq.valid,
                        "GAP-003: Cabrillo QSO validator does not filter by 'callregexp', "
                        "so a non-YO callsign still validates successfully")
        self.assertEqual(lq.errors, [])


class TestGap006FragileScoringPathSelector(TestCase):
    """GAP-006: `_standard_scoring` uses `qso_points_normal != 1` as a proxy
    for 'was [scoring] qso_points actually configured'. An explicit
    `qso_points=1` in [scoring] is indistinguishable from no [scoring]
    section at all, and silently falls into the legacy distance*multiplier
    branch instead of the per-mode/per-pair dedup branch."""

    @mock.patch('os.path.isfile')
    def test_explicit_qso_points_1_falls_into_legacy_branch(self, mock_isfile: mock.MagicMock) -> None:
        rules_explicit_qso_points_1: str = CABRILLO_CROSSCHECK_RULES + """
[scoring]
qso_points=1
"""
        mock_isfile.return_value = True
        mo = mock.mock_open(read_data=rules_explicit_qso_points_1)
        with patch('builtins.open', mo, create=True):
            _rules = rules_hf.RulesHf('some_rule_file.rules')

        # the explicit value really is 1, same as the ScoringMixin default
        self.assertEqual(_rules.contest_qso_points, 1)

        confirmed_pairs: set = set()
        qso1 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5AAA          599 CJ  YO5BBB          599 001', 1)
        qso1.cc_confirmed, qso1.cc_error = cabrillo.apply_custom_scoring(
            'YO5AAA', 'YO5BBB', _rules, qso1, confirmed_pairs, 1,
            _rules.contest_qso_points, _rules.contest_special_qso_points,
            _rules.contest_special_callsign, distance=1)

        # legacy branch: points = distance * band multiplier (band1 multiplier=1)
        self.assertEqual(qso1.points, 1)

        # The tell-tale sign of the legacy branch: the pair-dedup mechanism
        # (confirmed_pairs) is never touched at all when qso_points_normal == 1,
        # even though a real [scoring] section with qso_points=1 was configured.
        self.assertEqual(confirmed_pairs, set(),
                         "GAP-006: an explicit qso_points=1 never populates confirmed_pairs, "
                         "proving it is treated identically to 'no [scoring] section configured'")

        # Scoring the exact same contact a second time (as if from the
        # partner's log) still scores full points rather than being deduped -
        # further proof the qso_points!=1 dedup path was never entered.
        qso2 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5BBB          599 CJ  YO5AAA          599 001', 1)
        qso2.cc_confirmed, qso2.cc_error = cabrillo.apply_custom_scoring(
            'YO5BBB', 'YO5AAA', _rules, qso2, confirmed_pairs, 1,
            _rules.contest_qso_points, _rules.contest_special_qso_points,
            _rules.contest_special_callsign, distance=1)
        self.assertEqual(qso2.points, 1)


class TestGap008SilentFallbackToBaseRulesClass(TestCase):
    """GAP-008: `logXchecker._get_rules_class` silently falls back to the
    base `Rules` class for any `[log] format` value that isn't a key in
    `FORMAT_RULES_MAP` (currently only 'EDI'/'CABRILLO'), instead of raising
    a clear 'unsupported format' error."""

    def test_unmapped_format_returns_base_rules_class_without_raising(self) -> None:
        result = logXchecker._get_rules_class('SOMETHING_UNMAPPED')

        self.assertIs(result, rules.Rules,
                      "GAP-008: an unmapped [log] format silently falls back to the plain "
                      "Rules class instead of raising an 'unsupported format' error")

    def test_unmapped_format_also_covers_lowercase_and_adif(self) -> None:
        # 'adif' isn't in FORMAT_RULES_MAP either (GAP-008's own example) -
        # same silent fallback applies.
        self.assertIs(logXchecker._get_rules_class('ADIF'), rules.Rules)
        self.assertIs(logXchecker._get_rules_class('adif'), rules.Rules)


class TestGap010DraculaCountyMultiplierNowValidated(TestCase):
    """GAP-010 is now FIXED (see specs/10-dracula-transylvania-2026.md
    DRACULA-004 and specs/09-known-gaps-and-deviations.md's updated GAP-010
    entry): DRACULA's county-based multiplier branch in
    `_compute_multiplier_for_qso` now calls `is_yo_county` before returning a
    ('YO_COUNTY', value) tuple, exactly like the sibling YODX branch already
    did. `ScoringMixin.contest_dracula_county_list` remains unread/dead code
    - that part of the original gap was not in scope for this fix."""

    @mock.patch('os.path.isfile')
    def test_garbage_exchange_value_no_longer_counts_as_yo_county_multiplier(
            self, mock_isfile: mock.MagicMock) -> None:
        mock_isfile.return_value = True
        mo = mock.mock_open(read_data=DRACULA_RULES)
        with patch('builtins.open', mo, create=True):
            _rules = rules_hf.RulesHf('some_rule_file.rules')

        self.assertEqual(_rules.contest_custom_scoring, 'DRACULA')

        # 'ZZZZZZ' is not a real Romanian county code (see common/dxcc.py's
        # ALL_YO_COUNTIES table). Previously this was accepted unvalidated
        # (GAP-010); now it is rejected (returns None) just like the YODX
        # branch already did for a non-county exchange value.
        qso = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5AAA          599 CJ  YO5BTZ          599 ZZZZZZ', 1)
        self.assertEqual(qso.qso_fields['call'], 'YO5BTZ')
        self.assertEqual(qso.qso_fields['nr_recv'], 'ZZZZZZ')

        # caller_callsign='DL1AAA' (non-YO) -- a YO caller would get no
        # county multiplier at all per DRACULA-004, regardless of validity.
        mult_key = cabrillo._compute_multiplier_for_qso(
            qso, _rules, _rules.contest_multiplier_exchange_field,
            _rules.contest_multiplier_special_exchange, 'DL1AAA')

        self.assertIsNone(mult_key,
                         "GAP-010 (fixed): DRACULA's YO_COUNTY multiplier branch now validates "
                         "the exchange value against is_yo_county and rejects a garbage value")

        # Sanity/contrast: a real Romanian county code from the same YO
        # partner still counts as a YO_COUNTY multiplier for a non-YO caller.
        qso_valid = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 DL1AAA          599 005 YO5BTZ          599 CJ', 1)
        mult_key_valid = cabrillo._compute_multiplier_for_qso(
            qso_valid, _rules, _rules.contest_multiplier_exchange_field,
            _rules.contest_multiplier_special_exchange, 'DL1AAA')
        self.assertEqual(mult_key_valid, ('YO_COUNTY', 'CJ'))


class TestGap013SymmetricDedupKeyScoresOnlyOneSide(TestCase):
    """GAP-013: `_standard_scoring`'s dedup key
    `(mode, min(call1, call2), max(call1, call2))` is symmetric, so for a
    confirmed QSO pair shared between two operators' logs (as
    `crosscheck_band` would use via a shared `confirmed_pairs` set), only
    whichever operator is scored FIRST claims the points - the other
    operator's matching QSO for the exact same contact scores 0."""

    @mock.patch('os.path.isfile')
    def test_only_first_scored_operator_gets_points(self, mock_isfile: mock.MagicMock) -> None:
        # a rules file with a non-default qso_points (mirrors
        # test_logs/rules_hf_rro_2024.config's qso_points=2)
        rules_qso_points_2: str = CABRILLO_CROSSCHECK_RULES + """
[scoring]
qso_points=2
"""
        mock_isfile.return_value = True
        mo = mock.mock_open(read_data=rules_qso_points_2)
        with patch('builtins.open', mo, create=True):
            _rules = rules_hf.RulesHf('some_rule_file.rules')

        self.assertEqual(_rules.contest_qso_points, 2)

        # confirmed_pairs is shared across both operators, exactly as
        # run_crosscheck()/crosscheck_band() thread a single set through the
        # whole cross-check run (formats/cabrillo/crosscheck.py).
        confirmed_pairs: set = set()

        # Operator A (YO5AAA) scoring its own confirmed QSO with YO5BBB.
        qso_from_a = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5AAA          599 CJ  YO5BBB          599 001', 1)
        qso_from_a.cc_confirmed, qso_from_a.cc_error = cabrillo.apply_custom_scoring(
            'YO5AAA', 'YO5BBB', _rules, qso_from_a, confirmed_pairs, 1,
            _rules.contest_qso_points, _rules.contest_special_qso_points,
            _rules.contest_special_callsign, distance=1)

        # Operator B (YO5BBB) scoring its own log's QSO for the SAME contact
        # (same mode, same two callsigns, just call1/call2 swapped - this is
        # what crosscheck_band does when it later scores operator B's log).
        qso_from_b = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5BBB          599 CJ  YO5AAA          599 001', 1)
        qso_from_b.cc_confirmed, qso_from_b.cc_error = cabrillo.apply_custom_scoring(
            'YO5BBB', 'YO5AAA', _rules, qso_from_b, confirmed_pairs, 1,
            _rules.contest_qso_points, _rules.contest_special_qso_points,
            _rules.contest_special_callsign, distance=1)

        self.assertEqual(qso_from_a.points, 2,
                         "Operator A, scored first, claims the configured qso_points")
        self.assertEqual(qso_from_b.points, 0,
                         "GAP-013: Operator B's matching QSO for the exact same contact scores "
                         "0, not because it's an actual duplicate contact, but because the "
                         "symmetric dedup key (mode, min(call1,call2), max(call1,call2)) was "
                         "already marked seen by operator A's QSO")


class TestGap014TenMinuteRuleKeysOffCategoryDisplayName(TestCase):
    """GAP-014: `_apply_10_minute_rule` checks `log.category.upper() ==
    'MULTI'`, but `log.category` is the rules file's `[categoryN] name`
    value, not the raw CATEGORY-OPERATOR log line. DRACULA's own rules
    fixture names its multi-op category 'MO-AB-HP MIXT' (see
    test_logs/rules_hf_dracula.config / README.md's Dracula example), so the
    10-minute rule silently never fires for DRACULA multi-op stations."""

    def _build_rules(self) -> rules_hf.RulesHf:
        with mock.patch('os.path.isfile', return_value=True):
            mo = mock.mock_open(read_data=DRACULA_RULES)
            with patch('builtins.open', mo, create=True):
                return rules_hf.RulesHf('some_rule_file.rules')

    def test_dracula_multi_op_category_name_does_not_trigger_rule(self) -> None:
        _rules = self._build_rules()

        # DRACULA_RULES' [category7] name is exactly 'MO-AB-HP MIXT', matching
        # README.md's own Dracula example - confirm that assumption first.
        self.assertEqual(_rules.contest_category(7)['name'], 'MO-AB-HP MIXT')

        # Two confirmed QSOs, 5 minutes apart, on two different bands
        # (band3=14MHz, band4=21MHz), against the same non-YO partner so the
        # multiplier key is identical for both (i.e. NOT a "new multiplier",
        # satisfying the 10-minute rule's penalty precondition) - this
        # combination WOULD be zeroed out by the 10-minute rule if it fired.
        qso1 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5PJB          599 CJ  DL1ABC          599 005', 1)
        qso2 = cabrillo.LogQso(
            'QSO: 21000 CW 2026-10-31 1205 YO5PJB          599 CJ  DL1ABC          599 006', 2)
        for q in (qso1, qso2):
            q.cc_confirmed = True
            q.points = 7  # sentinel value distinguishable from a "zeroed by rule" 0

        log = SimpleNamespace(
            category='MO-AB-HP MIXT',  # the real [categoryN] name for DRACULA multi-op
            ignore_this_log=False,
            valid_header=True,
            qsos=[qso1, qso2],
        )
        op_inst = SimpleNamespace(logs=[log])
        operator_instances = {'YO5PJB': op_inst}

        cabrillo._apply_10_minute_rule(operator_instances, _rules)

        self.assertEqual(qso1.points, 7)
        self.assertEqual(qso2.points, 7,
                         "GAP-014: the 10-minute rule never fires for a log whose category name "
                         "is 'MO-AB-HP MIXT' (DRACULA's real multi-op category name) because "
                         "_apply_10_minute_rule only recognizes the literal string 'MULTI'")

    def test_contrast_literal_multi_category_does_trigger_rule(self) -> None:
        """Sanity/contrast check: the exact same QSO timing+multiplier setup
        DOES get penalized when log.category is literally 'MULTI' - proving
        the mechanism works and that GAP-014 is really about the category
        *name* string, not some other confound in this test's QSO data."""
        _rules = self._build_rules()

        qso1 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5PJB          599 CJ  DL1ABC          599 005', 1)
        qso2 = cabrillo.LogQso(
            'QSO: 21000 CW 2026-10-31 1205 YO5PJB          599 CJ  DL1ABC          599 006', 2)
        for q in (qso1, qso2):
            q.cc_confirmed = True
            q.points = 7

        log = SimpleNamespace(
            category='MULTI',
            ignore_this_log=False,
            valid_header=True,
            qsos=[qso1, qso2],
            # DRACULA-004: _apply_10_minute_rule's multiplier classification
            # is now caller-aware and reads log.callsign for that purpose.
            callsign='YO5PJB',
        )
        op_inst = SimpleNamespace(logs=[log])
        operator_instances = {'YO5PJB': op_inst}

        cabrillo._apply_10_minute_rule(operator_instances, _rules)

        self.assertEqual(qso1.points, 7, "first QSO of a session is never penalized")
        self.assertEqual(qso2.points, 0,
                         "with category literally 'MULTI', the second QSO (band switch within "
                         "10 minutes, no new multiplier) IS zeroed by the rule")
