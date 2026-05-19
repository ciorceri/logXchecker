# Active Context

## Current Work Focus
Added DXCC entity information (country, continent, ITU zone, CQ zone) to cross-check output for all output formats.

## Recent Changes
### logXchecker.py
- Added `from formats.cabrillo import lookup_callsign` import for DXCC database lookups
- In the cross-check loop, for each operator callsign, call `lookup_callsign()` and add `country`, `continent`, `itu`, `cq` keys to the operator's output dict

### output/formatters.py
- **print_human_friendly_output()**: Added printing of Country, Continent, ITU zone, CQ zone after each operator's Callsign line in cross-check mode
- **print_csv_output()**: Added `Country, Continent, ITU, CQ` columns to the CSV header and data rows

### test_formatters.py
- Updated CSV test assertions to match the new column layout (Callsign, Country, Continent, ITU, CQ, ValidLog, Band, Category, ConfirmedQso, Points)

### JSON & XML output
- No changes needed — these serialize the output dict directly, so the new fields appear automatically

## Next Steps
- (none currently)

## Active Decisions
- DXCC info is stored at the **operator level** (not per-band) since country/continent/zone are properties of the callsign, not of a specific log or band
