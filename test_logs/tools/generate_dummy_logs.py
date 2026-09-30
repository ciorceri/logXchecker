"""
Deterministic synthetic contest log fixture generator for logXchecker's
cross-check pipeline.

Usage:
    python test_logs/tools/generate_dummy_logs.py \
        --rules test_logs/rules_vhf_napoca_2016.config \
        --seed 7 --operators 20 \
        --outdir test_logs/generated/napoca-2016

Loads the rules file through the project's own Rules/RulesVhf/RulesHf
classes (never re-parses the INI by hand), detects the log format from
rules.contest_log_format, and dispatches to the matching format-specific
generator module:
  - 'EDI'      -> edi_fixture_generator.py   (owned here)
  - 'CABRILLO' -> a sibling module, if present (owned by whichever agent
                  is building the Cabrillo fixture generator -- this
                  dispatcher does not implement Cabrillo generation itself
                  to avoid collisions with concurrent work on that side).

Re-run this script (extending the per-format generator module) whenever a
new contest/edge-case needs to be added -- don't try to make it universally
generic on the first pass.
"""
import argparse
import json
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_DIR, '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import rules as rules_mod  # noqa: E402  (project root import, base Rules class)


def _load_rules_and_detect_format(rules_path: str):
    """Load the rules file through the project's own Rules classes.

    NOTE: we can't instantiate the base `Rules` class first to "peek" at
    rules.contest_log_format the way logXchecker.py's _get_rules_class does
    for an *already-format-selected* class -- `Rules.__init__` unconditionally
    runs `validate_rules()` (rules.py:49), which calls the base class's
    `contest_qso_modes` (int-parsing, rules.py:159-170). For a Cabrillo rules
    file (string modes like 'CW,SSB') that raises ValueError before we ever
    get to read `[log] format`. So the peek itself has to be format-agnostic:
    a plain ConfigParser read of just the `[log] format` key, with the real
    parsing/validation left entirely to the correct RulesVhf/RulesHf
    subclass below (never hand-parsed beyond this one lookup).
    """
    import configparser
    _peek = configparser.ConfigParser()
    _peek.read(rules_path)
    log_format = _peek['log']['format'].upper()
    if log_format == 'EDI':
        import rules_vhf
        return rules_vhf.RulesVhf(rules_path), log_format
    elif log_format == 'CABRILLO':
        import rules_hf
        return rules_hf.RulesHf(rules_path), log_format
    else:
        raise ValueError('Unsupported [log] format in rules file: {}'.format(log_format))


def _strip_non_serializable(manifest: dict) -> dict:
    out = dict(manifest)
    out.pop('fixture', None)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--rules', required=True, help='Path to a rules_*.config INI file')
    parser.add_argument('--seed', type=int, default=7, help='Deterministic RNG seed')
    parser.add_argument('--operators', type=int, default=20,
                        help='Minimum number of distinct operator callsigns (floor, not target)')
    parser.add_argument('--outdir', required=True,
                        help='Output directory (will contain logs/, checklogs/, manifest.json)')
    args = parser.parse_args()

    rules_path = os.path.abspath(args.rules)
    rules_obj, log_format = _load_rules_and_detect_format(rules_path)

    if log_format == 'EDI':
        import edi_fixture_generator as gen
        manifest = gen.build_fixture(rules_obj, seed=args.seed, operators_min=args.operators)
        gen.write_fixture(manifest, args.outdir)
    elif log_format == 'CABRILLO':
        try:
            import cabrillo_fixture_generator as gen
        except ImportError:
            print("No Cabrillo fixture generator module found yet "
                  "(expected test_logs/tools/cabrillo_fixture_generator.py). "
                  "This EDI-focused generator run does not implement Cabrillo generation "
                  "to avoid colliding with concurrent work on that side.")
            sys.exit(1)
        manifest = gen.build_fixture(rules_obj, seed=args.seed, operators_min=args.operators)
        gen.write_fixture(manifest, args.outdir)
    else:
        print('Unsupported format: {}'.format(log_format))
        sys.exit(1)

    os.makedirs(args.outdir, exist_ok=True)
    manifest_path = os.path.join(args.outdir, 'manifest.json')
    serializable = _strip_non_serializable(manifest)
    serializable['generator'] = {
        'rules_file': rules_path,
        'log_format': log_format,
        'seed': args.seed,
        'operators_requested': args.operators,
    }
    with open(manifest_path, 'w') as f:
        json.dump(serializable, f, indent=2, sort_keys=False)

    print('Wrote {} logs, {} total QSOs ({} confirmed, {:.1f}%) to {}'.format(
        serializable['summary']['total_logs'],
        serializable['summary']['total_qsos'],
        serializable['summary']['confirmed_qsos'],
        serializable['summary']['confirmed_ratio'] * 100,
        args.outdir,
    ))
    print('Manifest: {}'.format(manifest_path))


if __name__ == '__main__':
    main()
