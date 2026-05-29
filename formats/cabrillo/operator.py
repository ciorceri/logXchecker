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

Cabrillo Operator class.
"""
import re


class Operator(object):
    """Keep operator callsign, info and logs path."""

    def __init__(self, callsign):
        self.callsign = callsign
        self.logs = []

    def add_log_by_path(self, path, rules=None, checklog=False):
        from .log import Log
        self.logs.append(Log(path, rules=rules, checklog=checklog))

    def add_log_instance(self, log):
        self.logs.append(log)

    def logs_by_band_regexp(self, band_regexp):
        logs = []
        for log in self.logs:
            if not log.valid_header:
                continue
            res = re.match(band_regexp, log.band, re.IGNORECASE)
            if res:
                logs.append(log)
        return logs
