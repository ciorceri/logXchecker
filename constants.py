"""
Copyright 2016-2022 Ciorceri Petru Sorin (yo5pjb)

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Shared constants used across logXchecker and format modules.
Importing this module has no side effects and does not require any
optional format module to be installed.
"""
INFO_MLC = 'multi_logs_folder'
INFO_CC = 'cross_check_folder'
INFO_LOG = 'log'
INFO_LOGS = 'logs'
INFO_BANDS = 'band'
INFO_OPERATORS = 'operators'
ERR_IO = 'io'
ERR_HEADER = 'header'
ERR_QSO = 'qso'

# Map user-facing format names to Python module names
FORMAT_MODULE_MAP = {
    'EDI': 'edi',
    'ADIF': 'adif',
    'CABRILLO': 'cabrillo',
}
