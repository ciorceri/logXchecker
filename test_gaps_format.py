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

Characterization tests for known format-parsing gaps/bugs recorded in
specs/09-known-gaps-and-deviations.md (GAP-001, GAP-004, GAP-005, GAP-011,
GAP-015, GAP-016). These tests PIN DOWN today's actual behavior, including
the buggy/undesired parts -- they intentionally do NOT fix any of the
underlying code. If the underlying gap is ever fixed, the corresponding
test here must be updated together with specs/09-known-gaps-and-deviations.md,
per this project's spec-driven-development approach.

This file is self-contained (its own rules-fixture strings) rather than
importing fixtures from test_cabrillo.py/test_edi.py, to avoid any
collision with concurrent edits to those files.
"""

from unittest import TestCase, mock
from unittest.mock import patch

import rules
import rules_hf

from test_rules import VALID_RULES_BASIC

import edi
import formats.cabrillo as cabrillo
from common.operator import Operator as CommonOperator


# ── Shared rules fixtures for Cabrillo scenarios ──────────────────────────

# A minimal single-band (20m) Cabrillo rules fixture, used for the
# checklog-asymmetry and candidate-retry scenarios (GAP-005a, GAP-005c).
GAP005_CABRILLO_RULES: str = \
r"""[contest]
name=Test
begindate=20261031
enddate=20261101
beginhour=1200
endhour=1159
bands=1
periods=1
categories=1
modes=CW,SSB

[log]
format=cabrillo

[band1]
band=14
regexp=14\.?|20m
multiplier=1

[period1]
begindate=20261031
enddate=20261101
beginhour=1200
endhour=1159
bands=band1

[category1]
name=SO-AB
regexp=SINGLE|SO|CHECK
bands=band1
"""

# A two-band (20m/40m, with distinct multipliers) Cabrillo rules fixture,
# used to demonstrate the ALL-band frequency-blind fallback (GAP-016).
GAP016_CABRILLO_RULES: str = \
r"""[contest]
name=Test AllBand
begindate=20261031
enddate=20261101
beginhour=1200
endhour=1159
bands=2
periods=1
categories=1
modes=CW,SSB

[log]
format=cabrillo

[band1]
band=14
regexp=14\.?|20m
multiplier=1

[band2]
band=7
regexp=7\.?|40m
multiplier=3

[period1]
begindate=20261031
enddate=20261101
beginhour=1200
endhour=1159
bands=band1,band2

[category1]
name=SO-AB
regexp=SINGLE|SO
bands=band1,band2
"""

# A DRACULA-shaped, 5-band Cabrillo rules fixture, used to demonstrate that
# CATEGORY-BAND is never validated against rules (GAP-004).
GAP004_CABRILLO_RULES: str = \
r"""[contest]
name=Dracula
begindate=20261031
enddate=20261101
beginhour=1200
endhour=1159
bands=5
periods=1
categories=7
modes=CW,SSB

[log]
format=cabrillo

[band1]
band=3.5
regexp=3\.?|80m
multiplier=1

[band2]
band=7
regexp=7\.?|40m
multiplier=1

[band3]
band=14
regexp=14\.?|20m
multiplier=1

[band4]
band=21
regexp=21\.?|15m
multiplier=1

[band5]
band=28
regexp=28\.?|10m
multiplier=1

[period1]
begindate=20261031
enddate=20261101
beginhour=1200
endhour=1159
bands=band1,band2,band3,band4,band5

[category1]
name=SO-AB-HP SSB
regexp=A1
bands=band1,band2,band3,band4,band5

[category2]
name=SO-AB-HP CW
regexp=A2
bands=band1,band2,band3,band4,band5

[category3]
name=SO-AB-HP MIXT
regexp=A3
bands=band1,band2,band3,band4,band5

[category4]
name=SO-AB-LP SSB
regexp=B1
bands=band1,band2,band3,band4,band5

[category5]
name=SO-AB-LP CW
regexp=B2
bands=band1,band2,band3,band4,band5

[category6]
name=SO-AB-LP MIXT
regexp=B3
bands=band1,band2,band3,band4,band5

[category7]
name=MO-AB-HP MIXT
regexp=C
bands=band1,band2,band3,band4,band5
"""

GAP004_LOG_TEMPLATE: str = \
"""START-OF-LOG: 3.0
CONTEST: DRACULA
CALLSIGN: YO5PJB
CATEGORY-OPERATOR: B3
CATEGORY-BAND: {band}
CATEGORY-MODE: MIXED
CREATED-BY: logXchecker test generator

QSO: 14000 CW 2026-10-31 1200 YO5PJB          599 CJ  YO5BTZ          599 001
END-OF-LOG:
"""


# ── GAP-001 ────────────────────────────────────────────────────────────

class TestGap001RttyModeAlias(TestCase):
    def test_gap_001_rtty_mode_normalizes_to_digi_not_rtty(self) -> None:
        """GAP-001: CABRILLO_MODE_ALIASES defines 'RTTY': 'RTTY' early in the
        dict literal, then 'RTTY': 'DIGI' again later (inside the DIGI-family
        block). Python keeps the LAST duplicate key, so
        normalize_cabrillo_mode('RTTY') currently returns 'DIGI', not 'RTTY'.
        This test pins down that (buggy) current behavior."""
        self.assertEqual(cabrillo.normalize_cabrillo_mode('RTTY'), 'DIGI',
                         "GAP-001: normalize_cabrillo_mode('RTTY') should currently "
                         "return 'DIGI' due to the duplicate dict key overwrite")
        # Sanity check directly on the alias dict itself.
        self.assertEqual(cabrillo.CABRILLO_MODE_ALIASES['RTTY'], 'DIGI')


# ── GAP-004 ────────────────────────────────────────────────────────────

class TestGap004DeadHeaderValidators(TestCase):
    @mock.patch('os.path.isfile')
    def test_gap_004_bad_category_band_bypasses_rules_based_validate_band(
            self, mock_isfile: mock.MagicMock) -> None:
        """GAP-004: Log.validate_band / Log.rules_based_validate_band are defined
        but never called from validate_header(). A CATEGORY-BAND value that
        rules_based_validate_band would reject (it doesn't match any of the
        DRACULA-style rules' band regexps) is still accepted verbatim, with no
        header error recorded.

        (validate_date/rules_based_validate_date/validate_email are also dead
        per GAP-004, but a comparably clean, self-contained repro wasn't
        attempted for those here: Cabrillo has no log-level date field at all
        -- self.date is just copied from rules.contest_begin_date, CAB-003 --
        and EMAIL has no similarly "obviously invalid but still accepted"
        example. validate_band gave the clearest, most concrete repro.)
        """
        mock_isfile.return_value = True
        mo_rules = mock.mock_open(read_data=GAP004_CABRILLO_RULES)
        with patch('builtins.open', mo_rules, create=True):
            _rules = rules_hf.RulesHf('some_rule_file.rules')

        # Sanity check: if rules_based_validate_band() were actually invoked
        # from validate_header(), '2M' would be rejected -- it doesn't match
        # any of this rules file's band regexps (80m/40m/20m/15m/10m).
        self.assertFalse(
            cabrillo.Log.rules_based_validate_band('2M', _rules),
            "Sanity check: '2M' should fail rules_based_validate_band against "
            "these rules (bands are 80m/40m/20m/15m/10m only)")

        bad_band_log = GAP004_LOG_TEMPLATE.format(band='2M')
        mo_log = mock.mock_open(read_data=bad_band_log)
        with patch('builtins.open', mo_log, create=True):
            log = cabrillo.Log('some_log_file.log', rules=_rules)

        self.assertTrue(
            log.valid_header,
            "GAP-004: header is accepted even though CATEGORY-BAND ('2M') would "
            "fail rules_based_validate_band -- the validator is dead code")
        self.assertEqual(log.band, '2M')
        header_error_msgs = [msg for _, msg in log.errors[cabrillo.ERR_HEADER]]
        self.assertFalse(
            any('band' in msg.lower() for msg in header_error_msgs),
            "GAP-004: no header error should mention 'band' since "
            "rules_based_validate_band is never actually called")


# ── GAP-005a: checklog asymmetry ──────────────────────────────────────

class TestGap005aChecklogAsymmetry(TestCase):
    @mock.patch('os.path.isfile')
    def test_gap_005a_edi_checklog_only_partner_can_confirm(
            self, mock_isfile: mock.MagicMock) -> None:
        """GAP-005a: EDI's crosscheck_band calls _find_active_log(ham2, ...,
        exclude_checklog=False) for the PARTNER side, so a checklog-only
        submission from the partner can still confirm the searching
        operator's QSO."""
        mock_isfile.return_value = True
        mo_rules = mock.mock_open(read_data=VALID_RULES_BASIC)
        with patch('builtins.open', mo_rules, create=True):
            _rules = rules.Rules('some_rule_file.rules')

        log1_content: str = \
"""TName=Cupa Nasaud
TDate=20130803;20130806
PCall=YO5AAA
PWWLo=KN16SS
PSect=SOSB
PBand=144 MHz
[QSORecords;1]
130803;1200;YO5BBB;6;59;001;59;001;;KN16SS;1;;;;
"""
        op1 = edi.Operator('YO5AAA')
        mo = mock.mock_open(read_data=log1_content)
        with patch('builtins.open', mo, create=True):
            op1.add_log_by_path('log1.edi', rules=_rules)

        log2_content: str = \
"""TName=Cupa Nasaud
TDate=20130803;20130806
PCall=YO5BBB
PWWLo=KN16SS
PSect=SOSB
PBand=144 MHz
[QSORecords;1]
130803;1200;YO5AAA;6;59;001;59;001;;KN16SS;1;;;;
"""
        op2 = edi.Operator('YO5BBB')  # submits ONLY a checklog on this band
        mo = mock.mock_open(read_data=log2_content)
        with patch('builtins.open', mo, create=True):
            op2.add_log_by_path('log2.edi', rules=_rules, checklog=True)

        op_inst = {'YO5AAA': op1, 'YO5BBB': op2}
        edi.crosscheck_band(op_inst, _rules, 1)

        qso1 = op1.logs[0].qsos[0]
        self.assertTrue(
            qso1.cc_confirmed,
            "GAP-005a: EDI should confirm YO5AAA's QSO using YO5BBB's "
            "checklog-only submission")

    @mock.patch('os.path.isfile')
    def test_gap_005a_cabrillo_checklog_only_partner_cannot_confirm(
            self, mock_isfile: mock.MagicMock) -> None:
        """GAP-005a: Cabrillo's _find_active_log has no exclude_checklog
        parameter at all -- checklogs are excluded unconditionally on BOTH
        sides. The exact same scenario that confirms in EDI (see the sibling
        test above) fails to confirm in Cabrillo."""
        mock_isfile.return_value = True
        mo_rules = mock.mock_open(read_data=GAP005_CABRILLO_RULES)
        with patch('builtins.open', mo_rules, create=True):
            _rules = rules_hf.RulesHf('some_rule_file.rules')

        log1_content: str = \
"""START-OF-LOG: 3.0
CONTEST: Test
CALLSIGN: YO5AAA
CATEGORY-OPERATOR: SINGLE-OP
CATEGORY-BAND: 20M
CATEGORY-MODE: MIXED

QSO: 14000 CW 2026-10-31 1200 YO5AAA          599 001 YO5BBB          599 002
"""
        op1 = cabrillo.Operator('YO5AAA')
        mo = mock.mock_open(read_data=log1_content)
        with patch('builtins.open', mo, create=True):
            op1.add_log_by_path('log1.log', rules=_rules)

        log2_content: str = \
"""START-OF-LOG: 3.0
CONTEST: Test
CALLSIGN: YO5BBB
CATEGORY-OPERATOR: CHECKLOG
CATEGORY-BAND: 20M
CATEGORY-MODE: MIXED

QSO: 14000 CW 2026-10-31 1200 YO5BBB          599 002 YO5AAA          599 001
"""
        op2 = cabrillo.Operator('YO5BBB')  # submits ONLY a checklog on this band
        mo = mock.mock_open(read_data=log2_content)
        with patch('builtins.open', mo, create=True):
            op2.add_log_by_path('log2.log', rules=_rules, checklog=True)

        op_inst = {'YO5AAA': op1, 'YO5BBB': op2}
        confirmed_pairs: set = set()
        cabrillo.crosscheck_band(op_inst, _rules, 1, confirmed_pairs)

        qso1 = op1.logs[0].qsos[0]
        self.assertFalse(
            qso1.cc_confirmed,
            "GAP-005a: Cabrillo should NOT confirm using a checklog-only "
            "partner submission (unlike EDI)")
        self.assertEqual(qso1.cc_error, 'No valid log for this band from YO5BBB')


# ── GAP-005b: serial/exchange comparison type ─────────────────────────

class TestGap005bSerialComparisonType(TestCase):
    def test_gap_005b_edi_int_cast_makes_001_equal_1(self) -> None:
        """GAP-005b: EDI's compare_qso casts nr_sent/nr_recv to int() before
        cross-matching, so '001' and '1' are treated as the SAME serial
        number."""
        log1 = mock.Mock(callsign='YO5AAA', maidenhead_locator='KN16AA')
        log2 = mock.Mock(callsign='YO5BBB', maidenhead_locator='KN16AA')

        # qso1 (from YO5AAA's log): nr_sent='001', nr_recv='005'
        qso1 = edi.LogQso('130803;1200;YO5BBB;6;59;001;59;005;;KN16AA;1;;;;', 1)
        # qso2 (from YO5BBB's log, reciprocal): nr_sent='5', nr_recv='1'
        qso2 = edi.LogQso('130803;1200;YO5AAA;6;59;5;59;1;;KN16AA;1;;;;', 2)

        # Does not raise: int('001') == int('1') and int('005') == int('5').
        distance = edi.compare_qso(log1, qso1, log2, qso2)
        self.assertEqual(distance, 1)

    def test_gap_005b_cabrillo_string_comparison_makes_001_mismatch_1(self) -> None:
        """GAP-005b: Cabrillo's compare_qso compares nr_sent/nr_recv as raw
        strings (no int() cast), so the exact same '001' vs '1' pair that
        EDI treats as equal (see the sibling test above) is a mismatch in
        Cabrillo."""
        log1 = mock.Mock(callsign='YO5AAA')
        log2 = mock.Mock(callsign='YO5BBB')

        qso1 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5AAA          599 001 YO5BBB          599 005', 1)
        qso2 = cabrillo.LogQso(
            'QSO: 14000 CW 2026-10-31 1200 YO5BBB          599 5   YO5AAA          599 1', 2)

        self.assertRaisesRegex(
            ValueError, r'^Serial number mismatch \(other ham\)$',
            cabrillo.compare_qso, log1, qso1, log2, qso2)


# ── GAP-005c: candidate retry strategy ─────────────────────────────────

class TestGap005cCandidateRetry(TestCase):
    @mock.patch('os.path.isfile')
    def test_gap_005c_edi_retries_second_candidate_and_confirms(
            self, mock_isfile: mock.MagicMock) -> None:
        """GAP-005c: EDI's crosscheck_band tries every textually-matching
        candidate QSO in the partner's log (via _find_qso_candidates) through
        full compare_qso, until one passes. The partner logs TWO QSOs from
        the same callsign in the same period: the first has a wrong RST (and
        would fail compare_qso), the second is correct. EDI still confirms
        using the second candidate."""
        mock_isfile.return_value = True
        mo_rules = mock.mock_open(read_data=VALID_RULES_BASIC)
        with patch('builtins.open', mo_rules, create=True):
            _rules = rules.Rules('some_rule_file.rules')

        log1_content: str = \
"""TName=Cupa Nasaud
TDate=20130803;20130806
PCall=YO5AAA
PWWLo=KN16SS
PSect=SOSB
PBand=144 MHz
[QSORecords;1]
130803;1200;YO5BBB;6;59;001;59;002;;KN16SS;1;;;;
"""
        op1 = edi.Operator('YO5AAA')
        mo = mock.mock_open(read_data=log1_content)
        with patch('builtins.open', mo, create=True):
            op1.add_log_by_path('log1.edi', rules=_rules)

        # YO5BBB's log has two candidates for YO5AAA in the same period:
        # the first has the wrong RST (58 instead of 59), the second is correct.
        log2_content: str = \
"""TName=Cupa Nasaud
TDate=20130803;20130806
PCall=YO5BBB
PWWLo=KN16SS
PSect=SOSB
PBand=144 MHz
[QSORecords;2]
130803;1200;YO5AAA;6;58;002;59;001;;KN16SS;1;;;;
130803;1201;YO5AAA;6;59;002;59;001;;KN16SS;1;;;;
"""
        op2 = edi.Operator('YO5BBB')
        mo = mock.mock_open(read_data=log2_content)
        with patch('builtins.open', mo, create=True):
            op2.add_log_by_path('log2.edi', rules=_rules)

        op_inst = {'YO5AAA': op1, 'YO5BBB': op2}
        edi.crosscheck_band(op_inst, _rules, 1)

        qso1 = op1.logs[0].qsos[0]
        self.assertTrue(
            qso1.cc_confirmed,
            "GAP-005c: EDI should confirm by falling through to the second, "
            "correct candidate after the first candidate fails comparison")
        self.assertEqual(qso1.cc_error, [])

    @mock.patch('os.path.isfile')
    def test_gap_005c_cabrillo_stops_at_first_candidate_and_reports_mismatch(
            self, mock_isfile: mock.MagicMock) -> None:
        """GAP-005c: Cabrillo's _find_matching_qso returns only the FIRST
        textually-matching candidate and never retries. With the exact same
        two-candidate partner log as the EDI test above (first candidate has
        wrong RST, second would match), Cabrillo reports the specific
        mismatch from the first candidate instead of finding the second."""
        mock_isfile.return_value = True
        mo_rules = mock.mock_open(read_data=GAP005_CABRILLO_RULES)
        with patch('builtins.open', mo_rules, create=True):
            _rules = rules_hf.RulesHf('some_rule_file.rules')

        log1_content: str = \
"""START-OF-LOG: 3.0
CONTEST: Test
CALLSIGN: YO5AAA
CATEGORY-OPERATOR: SINGLE-OP
CATEGORY-BAND: 20M
CATEGORY-MODE: MIXED

QSO: 14000 CW 2026-10-31 1200 YO5AAA          599 001 YO5BBB          599 002
"""
        op1 = cabrillo.Operator('YO5AAA')
        mo = mock.mock_open(read_data=log1_content)
        with patch('builtins.open', mo, create=True):
            op1.add_log_by_path('log1.log', rules=_rules)

        # YO5BBB's log: first candidate has the wrong RST (598), second
        # candidate (which Cabrillo never reaches) would have matched.
        log2_content: str = \
"""START-OF-LOG: 3.0
CONTEST: Test
CALLSIGN: YO5BBB
CATEGORY-OPERATOR: SINGLE-OP
CATEGORY-BAND: 20M
CATEGORY-MODE: MIXED

QSO: 14000 CW 2026-10-31 1200 YO5BBB          598 002 YO5AAA          599 001
QSO: 14000 CW 2026-10-31 1201 YO5BBB          599 002 YO5AAA          599 001
"""
        op2 = cabrillo.Operator('YO5BBB')
        mo = mock.mock_open(read_data=log2_content)
        with patch('builtins.open', mo, create=True):
            op2.add_log_by_path('log2.log', rules=_rules)

        op_inst = {'YO5AAA': op1, 'YO5BBB': op2}
        confirmed_pairs: set = set()
        cabrillo.crosscheck_band(op_inst, _rules, 1, confirmed_pairs)

        qso1 = op1.logs[0].qsos[0]
        self.assertFalse(
            qso1.cc_confirmed,
            "GAP-005c: Cabrillo should fail on the first (wrong-RST) "
            "candidate instead of retrying the second, correct one")
        self.assertEqual(str(qso1.cc_error), 'Rst mismatch')


# ── GAP-015 ────────────────────────────────────────────────────────────

class TestGap015EdiDiscardsSpecificMismatchReason(TestCase):
    @mock.patch('os.path.isfile')
    def test_gap_015_edi_overwrites_specific_reason_with_generic_message(
            self, mock_isfile: mock.MagicMock) -> None:
        """GAP-015: when EDI's candidate-retry loop finds a candidate whose
        specific compare_qso failure is captured into qso1.cc_error (e.g.
        'Rst mismatch'), but NO candidate ultimately passes, that specific
        reason is unconditionally overwritten with the generic
        'No qso found on {callsign2} log' message. This test constructs a
        partner log with exactly ONE candidate that fails on RST, and shows
        the final cc_error is the generic message, not 'Rst mismatch' --
        even though 'Rst mismatch' was computed internally along the way."""
        mock_isfile.return_value = True
        mo_rules = mock.mock_open(read_data=VALID_RULES_BASIC)
        with patch('builtins.open', mo_rules, create=True):
            _rules = rules.Rules('some_rule_file.rules')

        log1_content: str = \
"""TName=Cupa Nasaud
TDate=20130803;20130806
PCall=YO5AAA
PWWLo=KN16SS
PSect=SOSB
PBand=144 MHz
[QSORecords;1]
130803;1200;YO5BBB;6;59;001;59;002;;KN16SS;1;;;;
"""
        op1 = edi.Operator('YO5AAA')
        mo = mock.mock_open(read_data=log1_content)
        with patch('builtins.open', mo, create=True):
            op1.add_log_by_path('log1.edi', rules=_rules)

        # YO5BBB's log has exactly ONE candidate for YO5AAA, with the wrong
        # RST -- no second candidate exists to fall through to.
        log2_content: str = \
"""TName=Cupa Nasaud
TDate=20130803;20130806
PCall=YO5BBB
PWWLo=KN16SS
PSect=SOSB
PBand=144 MHz
[QSORecords;1]
130803;1200;YO5AAA;6;58;002;59;001;;KN16SS;1;;;;
"""
        op2 = edi.Operator('YO5BBB')
        mo = mock.mock_open(read_data=log2_content)
        with patch('builtins.open', mo, create=True):
            op2.add_log_by_path('log2.edi', rules=_rules)

        op_inst = {'YO5AAA': op1, 'YO5BBB': op2}
        edi.crosscheck_band(op_inst, _rules, 1)

        qso1 = op1.logs[0].qsos[0]
        self.assertFalse(qso1.cc_confirmed)
        self.assertEqual(
            qso1.cc_error, 'No qso found on YO5BBB log',
            "GAP-015: the specific 'Rst mismatch' reason computed while "
            "trying the only candidate should have been overwritten with "
            "the generic 'no qso found' message")


# ── GAP-016 ────────────────────────────────────────────────────────────

class TestGap016AllBandFallbackIgnoresFrequency(TestCase):
    @mock.patch('os.path.isfile')
    def test_gap_016_all_band_log_scored_under_wrong_band_pass(
            self, mock_isfile: mock.MagicMock) -> None:
        """GAP-016: Cabrillo's _find_active_log falls back to an operator's
        CATEGORY-BAND: ALL log on every band-number pass, regardless of the
        QSO's actual frequency. Here YO5AAA's ALL log contains one QSO on
        14000 kHz (band 1's frequency, 20m), but YO5BBB only has a
        band-specific log on 40m (band 2). Because the ALL log is used
        as-is during the band-2 pass too, the QSO gets matched and scored
        with band 2's multiplier (3), not band 1's (1) -- even though the
        QSO was never actually made on 40m."""
        mock_isfile.return_value = True
        mo_rules = mock.mock_open(read_data=GAP016_CABRILLO_RULES)
        with patch('builtins.open', mo_rules, create=True):
            _rules = rules_hf.RulesHf('some_rule_file.rules')

        # Sanity check: 14000 kHz really does belong to band 1 (20m), not band 2.
        self.assertEqual(cabrillo._get_band_from_frequency('14000', _rules), 1)

        log1_content: str = \
"""START-OF-LOG: 3.0
CONTEST: Test AllBand
CALLSIGN: YO5AAA
CATEGORY-OPERATOR: SINGLE-OP
CATEGORY-BAND: ALL
CATEGORY-MODE: MIXED

QSO: 14000 CW 2026-10-31 1200 YO5AAA          599 001 YO5BBB          599 002
"""
        op1 = cabrillo.Operator('YO5AAA')
        mo = mock.mock_open(read_data=log1_content)
        with patch('builtins.open', mo, create=True):
            op1.add_log_by_path('log1.log', rules=_rules)

        log2_content: str = \
"""START-OF-LOG: 3.0
CONTEST: Test AllBand
CALLSIGN: YO5BBB
CATEGORY-OPERATOR: SINGLE-OP
CATEGORY-BAND: 40M
CATEGORY-MODE: MIXED

QSO: 7000 CW 2026-10-31 1200 YO5BBB          599 002 YO5AAA          599 001
"""
        op2 = cabrillo.Operator('YO5BBB')
        mo = mock.mock_open(read_data=log2_content)
        with patch('builtins.open', mo, create=True):
            op2.add_log_by_path('log2.log', rules=_rules)

        op_inst = {'YO5AAA': op1, 'YO5BBB': op2}
        confirmed_pairs: set = set()
        # Run only the band-2 (40m) pass -- YO5AAA has no 20m-specific log,
        # so _find_active_log falls back to the ALL log for this pass too.
        cabrillo.crosscheck_band(op_inst, _rules, 2, confirmed_pairs)

        qso1 = op1.logs[0].qsos[0]
        self.assertTrue(
            qso1.cc_confirmed,
            "GAP-016: the ALL-band log's QSO gets matched during the band-2 "
            "pass even though it was made on a band-1 frequency")
        # qso1.points = distance(1) * band2's multiplier(3) = 3.
        # If frequency filtering existed, this QSO would never be considered
        # during the band-2 pass at all.
        self.assertEqual(qso1.points, 3)


# ── GAP-011 ────────────────────────────────────────────────────────────

class TestGap011CommonOperatorBroken(TestCase):
    def test_gap_011_add_log_by_path_raises_nameerror(self) -> None:
        """GAP-011: common.operator.Operator.add_log_by_path references a
        bare 'Log' name that is never imported into common/operator.py.
        Calling it raises NameError -- documenting that this "shared" base
        class is currently broken for the one method that would actually
        load a log from disk."""
        op = CommonOperator('YO5PJB')
        with self.assertRaises(NameError):
            op.add_log_by_path('some_log_file.log')
