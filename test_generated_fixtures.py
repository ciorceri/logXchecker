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

Integration tests for the synthetic fixture sets under
``test_logs/generated/`` (built by the log-generator agent, see
``.claude/agents/log-generator.md`` and ``test_logs/tools/*_fixture_generator.py``).

Each fixture set ships a ``manifest.json`` recording, per log, whether its
header is intentionally valid/invalid, and per QSO, the intended cross-check
outcome (``confirmed`` / ``not_confirmed:<reason>`` / ``invalid:<reason>`` /
``not_evaluated:<reason>``) plus which partner QSO it pairs with. That
manifest was already hand-verified once (by running the real app and diffing
its output), but that verification was never wired into the automated test
suite. This file turns it into a permanent regression guard by re-running the
real cross-check pipeline (``formats.edi``/``formats.cabrillo``'s
``run_crosscheck``, the exact function ``logXchecker.py``'s ``-cc`` mode
calls) and asserting the real output matches every claim in the manifest.

IMPORTANT: this test intentionally asserts *current real behavior*, which
includes known gaps documented in ``specs/09-known-gaps-and-deviations.md``
(see each manifest entry's ``gap_ref``/``note`` fields, e.g. GAP-005a,
GAP-005b, GAP-016, GAP-018) -- it does not assert "ideal" behavior. If an
assertion here ever fails, treat it as a sign that the fixtures, the app, or
this test has drifted out of sync -- not as something to loosen or skip.
"""
import json
import os

from unittest import TestCase

import rules_hf
import rules_vhf

import edi
import formats.cabrillo as cabrillo


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

NAPOCA_DIR = os.path.join(BASE_DIR, 'test_logs', 'generated', 'napoca-2016')
NAPOCA_RULES_FILE = os.path.join(BASE_DIR, 'test_logs', 'rules_vhf_napoca_2016.config')

DRACULA_DIR = os.path.join(BASE_DIR, 'test_logs', 'generated', 'dracula')
DRACULA_RULES_FILE = os.path.join(BASE_DIR, 'test_logs', 'rules_hf_dracula.config')

# Hard requirement from .claude/agents/log-generator.md: at least half of all
# generated QSOs must be genuinely, correctly confirmable.
MIN_CONFIRMABLE_RATIO = 0.5


def _load_manifest(fixture_dir):
    manifest_path = os.path.join(fixture_dir, 'manifest.json')
    with open(manifest_path, encoding='utf-8') as _file:
        return json.load(_file)


def _basename_from_manifest_path(raw_path):
    """Manifest paths mix '/' and '\\' (written on Windows) -- just take the filename."""
    return os.path.basename(raw_path.replace('\\', '/'))


def _find_qso(log_obj, raw_line):
    """Locate the LogQso instance matching a manifest raw_line (case-insensitive)."""
    target = raw_line.strip().upper()
    for qso in log_obj.qsos:
        if qso.qso_line.strip().upper() == target:
            return qso
    return None


def assert_fixture_set_matches_manifest(test_case, fixture_dir, rules_obj, log_class, run_crosscheck):
    """Shared reconciliation helper -- run the real cross-check pipeline against
    a generated fixture set and assert its output matches every per-log and
    per-QSO expectation recorded in that fixture set's manifest.json.

    Returns (confirmed_qsos, total_qsos, confirmed_ratio) so callers can also
    report/assert on the >=50% confirmable-QSO property.
    """
    manifest = _load_manifest(fixture_dir)
    logs_folder = os.path.join(fixture_dir, 'logs')
    checklogs_folder = os.path.join(fixture_dir, 'checklogs')

    operator_instances = run_crosscheck(
        log_class, rules=rules_obj, logs_folder=logs_folder, checklogs_folder=checklogs_folder
    )
    test_case.assertTrue(
        operator_instances, 'run_crosscheck produced no operators for {}'.format(fixture_dir)
    )

    # Flatten every Log instance that made it into the cross-check output,
    # keyed by filename -- only header-valid logs are ever added here
    # (common/crosscheck.py's group_logs_by_operator drops invalid-header
    # logs before any Operator is created).
    logs_by_basename = {}
    for _callsign, instance in operator_instances.items():
        for log_obj in instance.logs:
            logs_by_basename[os.path.basename(log_obj.path)] = log_obj

    total_qsos = 0
    confirmed_qsos = 0

    for log_entry in manifest['logs']:
        basename = _basename_from_manifest_path(log_entry['path'])
        total_qsos += len(log_entry['qsos'])
        for qso_entry in log_entry['qsos']:
            if qso_entry['expected_outcome'].split(':', 1)[0] == 'confirmed':
                confirmed_qsos += 1

        if not log_entry['valid_header_expected']:
            test_case.assertNotIn(
                basename, logs_by_basename,
                'Header-invalid log {} ({}) unexpectedly present in cross-check '
                'operator output -- expected it to be dropped before grouping.'.format(
                    basename, log_entry.get('note', '')
                )
            )
            continue

        test_case.assertIn(
            basename, logs_by_basename,
            'Header-valid log {} is missing from the cross-check operator output.'.format(basename)
        )
        log_obj = logs_by_basename[basename]
        test_case.assertTrue(
            log_obj.valid_header,
            'Log {} was expected to have a valid header, got valid_header={!r}'.format(
                basename, log_obj.valid_header
            )
        )

        for qso_entry in log_entry['qsos']:
            raw_line = qso_entry['raw_line']
            qso_obj = _find_qso(log_obj, raw_line)
            test_case.assertIsNotNone(
                qso_obj,
                'QSO line {!r} from manifest ({}) was not found among the parsed '
                'QSOs of log {}.'.format(raw_line, qso_entry.get('scenario'), basename)
            )

            outcome, _, expected_msg = qso_entry['expected_outcome'].partition(':')
            context = '{} / {!r} (scenario={})'.format(basename, raw_line, qso_entry.get('scenario'))

            if outcome == 'confirmed':
                test_case.assertIs(
                    qso_obj.cc_confirmed, True,
                    '{}: expected confirmed, got cc_confirmed={!r}, cc_error={!r}'.format(
                        context, qso_obj.cc_confirmed, qso_obj.cc_error
                    )
                )
            elif outcome == 'not_evaluated':
                test_case.assertIsNone(
                    qso_obj.cc_confirmed,
                    '{}: expected not_evaluated (cc_confirmed stays None), got {!r}'.format(
                        context, qso_obj.cc_confirmed
                    )
                )
                test_case.assertFalse(
                    qso_obj.cc_error,
                    '{}: expected no cc_error while never evaluated, got {!r}'.format(
                        context, qso_obj.cc_error
                    )
                )
            else:
                # Both 'not_confirmed:<reason>' (rejected during cross-check
                # comparison) and 'invalid:<reason>' (rejected during QSO-line
                # format validation) surface identically on the QSO object:
                # cc_confirmed is False and cc_error carries the reason verbatim.
                test_case.assertIs(
                    qso_obj.cc_confirmed, False,
                    '{}: expected cc_confirmed=False ({}), got {!r}'.format(
                        context, qso_entry['expected_outcome'], qso_obj.cc_confirmed
                    )
                )
                test_case.assertIn(
                    expected_msg, str(qso_obj.cc_error),
                    '{}: expected error substring {!r} in cc_error, got {!r}'.format(
                        context, expected_msg, qso_obj.cc_error
                    )
                )

    confirmed_ratio = (confirmed_qsos / total_qsos) if total_qsos else 0.0
    test_case.assertGreaterEqual(
        confirmed_ratio, MIN_CONFIRMABLE_RATIO,
        '{}: only {}/{} ({:.1%}) of manifest QSOs are marked confirmed -- '
        'violates the >=50% confirmable-QSO fixture requirement documented in '
        '.claude/agents/log-generator.md.'.format(fixture_dir, confirmed_qsos, total_qsos, confirmed_ratio)
    )

    return confirmed_qsos, total_qsos, confirmed_ratio


class TestGeneratedNapoca2016Fixtures(TestCase):
    """EDI/VHF fixtures (napoca-2016), built from rules_vhf_napoca_2016.config."""

    def test_crosscheck_output_matches_manifest(self):
        rules_obj = rules_vhf.RulesVhf(NAPOCA_RULES_FILE)
        confirmed, total, ratio = assert_fixture_set_matches_manifest(
            self, NAPOCA_DIR, rules_obj, edi.Log, edi.run_crosscheck
        )
        self.assertEqual(total, 60)
        self.assertEqual(confirmed, 35)
        self.assertAlmostEqual(ratio, 35 / 60)


class TestGeneratedDraculaFixtures(TestCase):
    """Cabrillo/HF fixtures (DRACULA contest), built from rules_hf_dracula.config."""

    def test_crosscheck_output_matches_manifest(self):
        rules_obj = rules_hf.RulesHf(DRACULA_RULES_FILE)
        confirmed, total, ratio = assert_fixture_set_matches_manifest(
            self, DRACULA_DIR, rules_obj, cabrillo.Log, cabrillo.run_crosscheck
        )
        self.assertEqual(total, 53)
        self.assertEqual(confirmed, 32)
        self.assertAlmostEqual(ratio, 32 / 53)
