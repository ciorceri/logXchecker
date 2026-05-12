# Product Context

## Why This Project Exists
logXchecker was created to solve the problem of manually checking ham radio contest logs for accuracy and completeness. Contest organizers need to:
- Validate that submitted logs follow the required format
- Cross-check logs between operators to verify QSO confirmations
- Generate contest results with scoring based on contest-specific rules

## Problems It Solves
1. **Format Validation**: Ensures logs follow the correct syntax (EDI, Cabrillo V2, Cabrillo V3)
2. **Rules Compliance**: Validates QSOs against contest rules (dates, times, bands, modes, periods)
3. **Cross-Confirmation**: Finds mutual QSOs between operators to produce verified contact lists
4. **Scoring**: Calculates contest points based on rules (regular QSO points, special station bonus, per-band/per-mode deduplication)
5. **Output Flexibility**: Generates results in formats usable by contest managers (human-friendly, JSON, XML, CSV)

## How It Should Work
1. User provides either a single log file, a folder of logs, or a folder for cross-check (optionally with checklogs)
2. Rules file (INI format) defines contest parameters: dates, bands, periods, categories, scoring
3. The application validates headers and QSOs, flagging errors
4. For cross-check mode, it finds matching QSO pairs between operators
5. Results are presented in the requested output format

## User Experience Goals
- **Simple CLI**: Clear command-line interface with mutually exclusive operation modes
- **Flexible Rules**: INI-based rules that can be adapted to any contest format
- **Informative Output**: Verbose mode available for debugging unmatched QSOs
- **Language**: UI messages in English, contest rules support Romanian contests
