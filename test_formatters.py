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

Unit tests for output/formatters.py
"""

import io
from typing import Any, Dict, List
from unittest import TestCase
from unittest.mock import patch

from constants import (
    INFO_LOG, INFO_MLC, INFO_LOGS, INFO_CC, INFO_OPERATORS, INFO_BANDS,
    ERR_IO, ERR_HEADER, ERR_QSO,
)
from output.formatters import (
    print_log_human_friendly,
    print_human_friendly_output,
    print_csv_output,
)


class TestPrintLogHumanFriendly(TestCase):
    """Tests for print_log_human_friendly(output)."""

    def test_no_errors(self) -> None:
        """Empty errors dict prints 'Checking log' + 'No error found'."""
        output: Dict[str, Any] = {
            INFO_LOG: 'test.log',
            ERR_IO: '',
            ERR_HEADER: [],
            ERR_QSO: [],
        }
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            print_log_human_friendly(output)
        result: str = mock_stdout.getvalue()
        self.assertIn('Checking log : test.log', result)
        self.assertIn('No error found', result)

    def test_io_error(self) -> None:
        """An I/O error message is printed."""
        output = {
            INFO_LOG: 'test.log',
            ERR_IO: 'Permission denied',
            ERR_HEADER: [],
            ERR_QSO: [],
        }
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            print_log_human_friendly(output)
        result = mock_stdout.getvalue()
        self.assertIn('Input/Output : Permission denied', result)
        self.assertNotIn('No error found', result)

    def test_header_errors(self) -> None:
        """Multiple header errors are each printed."""
        output = {
            INFO_LOG: 'test.log',
            ERR_IO: '',
            ERR_HEADER: [
                (1, 'Missing callsign'),
                (3, 'Invalid band'),
            ],
            ERR_QSO: [],
        }
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            print_log_human_friendly(output)
        result = mock_stdout.getvalue()
        self.assertIn('Header errors :', result)
        self.assertIn('Line 1 : Missing callsign', result)
        self.assertIn('Line 3 : Invalid band', result)
        self.assertNotIn('No error found', result)

    def test_qso_errors(self) -> None:
        """Multiple QSO errors are each printed with the qso line and detail."""
        output = {
            INFO_LOG: 'test.log',
            ERR_IO: '',
            ERR_HEADER: [],
            ERR_QSO: [
                (5, '210000;...', 'Callsign invalid'),
                (8, '220000;...', 'Invalid mode'),
            ],
        }
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            print_log_human_friendly(output)
        result = mock_stdout.getvalue()
        self.assertIn('QSO errors :', result)
        self.assertIn('Line 5 : 210000;... <- Callsign invalid', result)
        self.assertIn('Line 8 : 220000;... <- Invalid mode', result)
        self.assertNotIn('No error found', result)

    def test_all_errors(self) -> None:
        """All error types are printed together."""
        output = {
            INFO_LOG: 'test.log',
            ERR_IO: 'Cannot open file',
            ERR_HEADER: [(1, 'Missing callsign')],
            ERR_QSO: [(5, '210000;...', 'Callsign invalid')],
        }
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            print_log_human_friendly(output)
        result = mock_stdout.getvalue()
        self.assertIn('Input/Output : Cannot open file', result)
        self.assertIn('Header errors :', result)
        self.assertIn('Line 1 : Missing callsign', result)
        self.assertIn('QSO errors :', result)
        self.assertIn('Line 5 : 210000;... <- Callsign invalid', result)
        self.assertNotIn('No error found', result)

    def test_empty_header_errors_list(self) -> None:
        """ERR_HEADER set to empty list does not print header section."""
        output = {
            INFO_LOG: 'test.log',
            ERR_IO: '',
            ERR_HEADER: [],
            ERR_QSO: [],
        }
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            print_log_human_friendly(output)
        result = mock_stdout.getvalue()
        self.assertNotIn('Header errors :', result)

    def test_empty_qso_errors_list(self) -> None:
        """ERR_QSO set to empty list does not print QSO section."""
        output = {
            INFO_LOG: 'test.log',
            ERR_IO: '',
            ERR_HEADER: [],
            ERR_QSO: [],
        }
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            print_log_human_friendly(output)
        result = mock_stdout.getvalue()
        self.assertNotIn('QSO errors :', result)


class TestPrintHumanFriendlyOutput(TestCase):
    """Tests for print_human_friendly_output(output, verbose=False)."""

    def test_single_log_mode(self) -> None:
        """When INFO_LOG is present, delegates to print_log_human_friendly."""
        output = {
            INFO_LOG: 'single.log',
            ERR_IO: 'File not found',
            ERR_HEADER: [],
            ERR_QSO: [],
        }
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            print_human_friendly_output(output)
        result = mock_stdout.getvalue()
        self.assertIn('Checking log : single.log', result)
        self.assertIn('Input/Output : File not found', result)

    def test_multi_log_mode(self) -> None:
        """When INFO_MLC is present with logs, prints folder header and each log."""
        output = {
            INFO_MLC: '/logs/folder',
            INFO_LOGS: [
                {INFO_LOG: 'log1.log', ERR_IO: 'error1', ERR_HEADER: [], ERR_QSO: []},
                {INFO_LOG: 'log2.log', ERR_IO: '', ERR_HEADER: [(1, 'bad header')], ERR_QSO: []},
            ],
        }
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            print_human_friendly_output(output)
        result = mock_stdout.getvalue()
        self.assertIn('Checking logs from folder : /logs/folder', result)
        self.assertIn('#########################', result)
        self.assertIn('Checking log : log1.log', result)
        self.assertIn('error1', result)
        self.assertIn('Checking log : log2.log', result)
        self.assertIn('bad header', result)
        self.assertIn('--------', result)

    def test_multi_log_empty_list(self) -> None:
        """When INFO_MLC set but logs list is empty, only folder header shown."""
        output = {
            INFO_MLC: '/logs/folder',
            INFO_LOGS: [],
        }
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            print_human_friendly_output(output)
        result = mock_stdout.getvalue()
        self.assertIn('Checking logs from folder : /logs/folder', result)
        self.assertIn('#########################', result)
        self.assertNotIn('Checking log :', result)

    def test_cross_check_mode(self) -> None:
        """Cross-check output prints operators and band details."""
        output = {
            INFO_CC: '/cc/folder',
            INFO_OPERATORS: {
                'YO5PJB': {
                    'band': {
                        '2m': {
                            'checklog': False,
                            'valid': True,
                            'category': 'SINGLE-OP',
                            'points': 150,
                            'qsos_confirmed': 10,
                        },
                    },
                },
            },
        }
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            print_human_friendly_output(output)
        result = mock_stdout.getvalue()
        self.assertIn('Cross check logs from folder : /cc/folder', result)
        self.assertIn('#########################', result)
        self.assertIn('Callsign : YO5PJB', result)
        self.assertIn('band=2m , valid=True , category=SINGLE-OP , points=150 , qsos_confirmed=10', result)

    def test_cross_check_verbose_with_qso_errors(self) -> None:
        """When verbose=True and qso_errors exist, they are printed."""
        output = {
            INFO_CC: '/cc/folder',
            INFO_OPERATORS: {
                'YO5PJB': {
                    'band': {
                        '2m': {
                            'checklog': False,
                            'valid': True,
                            'category': 'SINGLE-OP',
                            'points': 50,
                            'qsos_confirmed': 3,
                            'qso_errors': ['Line 1 : bad call'],
                            'qso_valid': ['Line 2 : good qso'],
                        },
                    },
                },
            },
        }
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            print_human_friendly_output(output, verbose=True)
        result = mock_stdout.getvalue()
        self.assertIn('  - ERROR Line 1 : bad call', result)
        self.assertIn('  - VALID Line 2 : good qso', result)

    def test_cross_check_checklog(self) -> None:
        """Checklog entries show '[checklog]' instead of points details."""
        output = {
            INFO_CC: '/cc/folder',
            INFO_OPERATORS: {
                'YO5PJB': {
                    'band': {
                        '2m': {
                            'checklog': True,
                            'valid': True,
                        },
                    },
                },
            },
        }
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            print_human_friendly_output(output)
        result = mock_stdout.getvalue()
        self.assertIn('[checklog] band=2m , valid=True', result)
        self.assertNotIn('category', result)

    def test_empty_output(self) -> None:
        """Empty output dict prints nothing."""
        output: Dict[str, Any] = {}
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            print_human_friendly_output(output)
        result = mock_stdout.getvalue()
        self.assertEqual('', result)


class TestPrintCsvOutput(TestCase):
    """Tests for print_csv_output(output)."""

    def test_cross_check_single_operator(self) -> None:
        """Single operator produces header + one data row."""
        output = {
            INFO_CC: '/cc/folder',
            INFO_OPERATORS: {
                'YO5PJB': {
                    'band': {
                        '2m': {
                            'checklog': False,
                            'valid': True,
                            'category': 'SINGLE-OP',
                            'points': 100,
                            'qsos_confirmed': 5,
                        },
                    },
                },
            },
        }
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            print_csv_output(output)
        result = mock_stdout.getvalue()
        lines: List[str] = result.strip().split('\n')
        self.assertEqual(lines[0], 'Callsign, ValidLog, Band, Category, ConfirmedQso, Points')
        self.assertIn('YO5PJB, True, 2m, SINGLE-OP, 5, 100', lines[1])

    def test_cross_check_multiple_operators_and_bands(self) -> None:
        """Multiple operators and bands produce multiple data rows."""
        output = {
            INFO_CC: '/cc/folder',
            INFO_OPERATORS: {
                'YO5PJB': {
                    'band': {
                        '2m': {
                            'checklog': False,
                            'valid': True,
                            'category': 'SINGLE-OP',
                            'points': 100,
                            'qsos_confirmed': 5,
                        },
                        '70cm': {
                            'checklog': False,
                            'valid': False,
                            'category': 'SINGLE-OP',
                            'points': 0,
                            'qsos_confirmed': 0,
                        },
                    },
                },
                'YO5ABC': {
                    'band': {
                        '2m': {
                            'checklog': False,
                            'valid': True,
                            'category': 'MULTI-OP',
                            'points': 200,
                            'qsos_confirmed': 10,
                        },
                    },
                },
            },
        }
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            print_csv_output(output)
        result = mock_stdout.getvalue()
        lines = result.strip().split('\n')
        self.assertEqual(lines[0], 'Callsign, ValidLog, Band, Category, ConfirmedQso, Points')
        self.assertIn('YO5PJB, True, 2m, SINGLE-OP, 5, 100', lines[1])
        self.assertIn('YO5PJB, False, 70cm, SINGLE-OP, 0, 0', lines[2])
        self.assertIn('YO5ABC, True, 2m, MULTI-OP, 10, 200', lines[3])

    def test_cross_check_checklog_excluded(self) -> None:
        """Operators with checklog=True are excluded from CSV."""
        output = {
            INFO_CC: '/cc/folder',
            INFO_OPERATORS: {
                'YO5PJB': {
                    'band': {
                        '2m': {
                            'checklog': True,
                            'valid': True,
                            'category': 'CHECKLOG',
                            'points': 0,
                            'qsos_confirmed': 0,
                        },
                    },
                },
            },
        }
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            print_csv_output(output)
        result = mock_stdout.getvalue()
        lines = result.strip().split('\n')
        self.assertEqual(len(lines), 1, 'Only the header should be printed')
        self.assertEqual(lines[0], 'Callsign, ValidLog, Band, Category, ConfirmedQso, Points')

    def test_cross_check_empty_operators(self) -> None:
        """INFO_CC set but no operators prints header only."""
        output = {
            INFO_CC: '/cc/folder',
            INFO_OPERATORS: {},
        }
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            print_csv_output(output)
        result = mock_stdout.getvalue()
        lines = result.strip().split('\n')
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], 'Callsign, ValidLog, Band, Category, ConfirmedQso, Points')

    def test_non_crosscheck_raises_not_implemented(self) -> None:
        """Without INFO_CC, print_csv_output raises NotImplementedError."""
        output = {
            INFO_LOG: 'test.log',
            ERR_IO: 'error',
        }
        with self.assertRaises(NotImplementedError):
            print_csv_output(output)
