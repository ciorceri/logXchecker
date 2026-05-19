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

Output formatters for logXchecker results.
"""

from typing import Any, Dict, List, Optional, Union

from constants import (
    INFO_LOG, INFO_MLC, INFO_LOGS, INFO_CC, INFO_OPERATORS, INFO_BANDS,
    ERR_IO, ERR_HEADER, ERR_QSO,
)

# Type alias for the nested error tuples used in the output dict
ErrorEntry = tuple[Optional[int], str, Optional[str]]


def print_log_human_friendly(output: Dict[str, Any]) -> None:
    """Will print human friendly info for a log"""
    has_errors: bool = False
    print('Checking log : {}'.format(output[INFO_LOG]))
    if output[ERR_IO]:
        print('Input/Output : {}'.format(output[ERR_IO]))
        has_errors = True
    if output[ERR_HEADER]:
        print('Header errors :')
        for err in output[ERR_HEADER]:
            print('Line {} : {}'.format(err[0], err[1]))
        has_errors = True
    if output[ERR_QSO]:
        print('QSO errors :')
        for err in output[ERR_QSO]:
            print('Line {} : {} <- {}'.format(err[0], err[1], err[2]))
        has_errors = True

    if has_errors is False:
        print('No error found')


def print_human_friendly_output(output: Dict[str, Any], verbose: bool = False) -> None:
    """Will print a human-friendly output for easy read"""
    # single log
    if output.get(INFO_LOG, False):
        print_log_human_friendly(output)
    # multi logs
    if output.get(INFO_MLC, False):
        print('Checking logs from folder : {}'.format(output[INFO_MLC]))
        print('#########################')
        for log in output[INFO_LOGS]:
            print_log_human_friendly(log)
            print('--------')
    # cross check
    if output.get(INFO_CC, False):
        print('Cross check logs from folder : {}'.format(output[INFO_CC]))
        print('#########################')
        for _call, _values in output[INFO_OPERATORS].items():
            print('Callsign : {}'.format(_call))
            country = _values.get('country', None)
            continent = _values.get('continent', None)
            itu = _values.get('itu', None)
            cq = _values.get('cq', None)
            print('  Country : {} | Continent : {} | ITU : {} | CQ : {}'.format(country, continent, itu, cq))
            for _band, _details in _values['band'].items():
                if _details.get('checklog', False) is True:
                    print('  [checklog] band={} , valid={}'.format(_band, _details['valid']))
                else:
                    multipliers: Optional[int] = _details.get('multipliers')
                    final_score: Optional[int] = _details.get('final_score')
                    if multipliers is not None and final_score is not None:
                        print('  band={} , valid={} , category={} , points={} , qsos_confirmed={} , multipliers={} , final_score={}'.format(
                            _band, _details['valid'], _details['category'],
                            _details['points'], _details['qsos_confirmed'],
                            multipliers, final_score
                        ))
                    else:
                        print('  band={} , valid={} , category={} , points={} , qsos_confirmed={}'.format(
                            _band, _details['valid'], _details['category'],
                            _details['points'], _details['qsos_confirmed']
                        ))
                if not verbose:
                    continue
                for err in _details['qso_errors']:
                    print('  - ERROR {}'.format(err))
                for val in _details['qso_valid']:
                    print('  - VALID {}'.format(val))
            print('--------')


def print_csv_output(output: Dict[str, Any]) -> None:
    """Will print a CSV-formatted output"""
    # cross check
    if output.get(INFO_CC, False):
        print('Callsign, Country, Continent, ITU, CQ, ValidLog, Band, Category, ConfirmedQso, Points')
        for _call, _values in output[INFO_OPERATORS].items():
            country = _values.get('country', '')
            continent = _values.get('continent', '')
            itu = _values.get('itu', '')
            cq = _values.get('cq', '')
            for _band, _details in _values['band'].items():
                if not _details.get('checklog', False) is True:
                    print('{}, {}, {}, {}, {}, {}, {}, {}, {}, {}'.format(
                        _call, country, continent, itu, cq,
                        _details['valid'], _band,
                        _details['category'], _details['qsos_confirmed'], _details['points']
                    ))
    else:
        # TODO: implement CSV output for single-log and multi-log modes
        raise NotImplementedError('CSV output is only implemented for cross-check mode')
