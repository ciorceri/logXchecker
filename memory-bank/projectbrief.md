# logXchecker - Project Brief

## Core Mission
A ham radio contest log cross-checker and validator that supports multiple log formats.

## Key Requirements
1. **Log Validation**: Validate individual logs (EDI, Cabrillo, ADIF formats) with both generic syntax checks and rules-based validation
2. **Cross-Check**: Compare logs from multiple operators to find mutual QSO confirmations
3. **Multi-Format Output**: Generate results in human-friendly, JSON, XML, and CSV formats
4. **Contest Rules System**: Flexible INI-based rules engine supporting different contest types

## Supported Log Formats
- **EDI** (VHF/UHF/SHF contests) - fully supported
- **Cabrillo** (HF contests) - V2.0 and V3.0 formats supported
- **ADIF** - future support planned

## Target Users
- Ham radio contest participants
- Contest log checkers/managers
- National contest organizers (e.g., Romanian YO contests)

## Project Scope
- Python 3.10+ desktop application (no web UI)
- Primarily CLI-driven, with optional output serialization
- Modular design allowing new log formats and rules engines
