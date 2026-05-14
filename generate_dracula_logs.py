#!/usr/bin/env python3
"""
Generate DRACULA Contest Cabrillo Test Logs.

Generates realistic Cabrillo V3 log files for the DRACULA contest
(Oct 31 - Nov 1, 2026) with a configurable set of stations and
partial connectivity matrix.

Usage:
    python generate_dracula_logs.py
    python generate_dracula_logs.py --seed 123 --density 0.5 --dry-run
    python generate_dracula_logs.py --output-dir test_logs/cabrillo/logs_dracula --seed 42
    python generate_dracula_logs.py --bands 40M 20M 80M --density 0.35
"""

import argparse
import os
import random
import sys
from datetime import datetime, timedelta

# ── Default station definitions ─────────────────────────────────────────

# Contest parameters
DEFAULT_CONTEST_NAME = "DRACULA"
DEFAULT_BEGIN_DATE = "20261031"
DEFAULT_END_DATE = "20261101"
DEFAULT_BEGIN_HOUR = "1200"
DEFAULT_END_HOUR = "1159"

# DRACULA special stations (picked from the 9 defined in the config)
DRACULA_SPECIALS = [
    {"callsign": "YP2DRACULA", "yo_district": "YO2", "category": "A1"},
    {"callsign": "YR5DRACULA", "yo_district": "YO5", "category": "A2"},
    {"callsign": "YQ6DRACULA", "yo_district": "YO6", "category": "A3"},
]

# YO stations (one per district with county code)
YO_STATIONS = [
    {"callsign": "YO2ARM",  "yo_district": "YO2", "county": "AR", "category": "B1"},
    {"callsign": "YO3APJ",  "yo_district": "YO3", "county": "BU", "category": "B1"},
    {"callsign": "YO4SLL",  "yo_district": "YO4", "county": "CT", "category": "B2"},
    {"callsign": "YO5FGH",  "yo_district": "YO5", "county": "CJ", "category": "B3"},
    {"callsign": "YO7ABC",  "yo_district": "YO7", "county": "AG", "category": "C"},
    {"callsign": "YO8XYZ",  "yo_district": "YO8", "county": "IS", "category": "C"},
]

# Non-YO stations — includes same-country pairs for 1-point testing
NON_YO_STATIONS = [
    # Same-country pairs (same DXCC prefix - should score 1pt)
    {"callsign": "HA5ABC", "dxcc": "HA", "country": "Hungary",      "category": "A2"},
    {"callsign": "HA5DEF", "dxcc": "HA", "country": "Hungary",      "category": "B1"},
    {"callsign": "OK1ABC", "dxcc": "OK", "country": "Czech Rep.",   "category": "A3"},
    {"callsign": "OK1DEF", "dxcc": "OK", "country": "Czech Rep.",   "category": "B2"},
    {"callsign": "DL1ABC", "dxcc": "DL", "country": "Germany",      "category": "B1"},
    {"callsign": "DL1DEF", "dxcc": "DL", "country": "Germany",      "category": "B3"},
    {"callsign": "I4ABC",  "dxcc": "I",  "country": "Italy",        "category": "B2"},
    {"callsign": "I4DEF",  "dxcc": "I",  "country": "Italy",        "category": "C"},
    {"callsign": "G4ABC",  "dxcc": "G",  "country": "England",      "category": "B3"},
    {"callsign": "G4DEF",  "dxcc": "G",  "country": "England",      "category": "C"},
    {"callsign": "S5ABC",  "dxcc": "S5", "country": "Slovenia",     "category": "B2"},
    {"callsign": "S5DEF",  "dxcc": "S5", "country": "Slovenia",     "category": "C"},
    {"callsign": "OZ1ABC", "dxcc": "OZ", "country": "Denmark",      "category": "A2"},
    {"callsign": "OZ1DEF", "dxcc": "OZ", "country": "Denmark",      "category": "B3"},
    # Single stations (different DXCC from each other - should score 2pt)
    {"callsign": "SP2XXX", "dxcc": "SP", "country": "Poland",       "category": "B1"},
    {"callsign": "F5XXX",  "dxcc": "F",  "country": "France",       "category": "C"},
    {"callsign": "ON4XXX", "dxcc": "ON", "country": "Belgium",      "category": "A3"},
    {"callsign": "PA3XXX", "dxcc": "PA", "country": "Netherlands",  "category": "B2"},
    {"callsign": "OE3XXX", "dxcc": "OE", "country": "Austria",      "category": "B3"},
    {"callsign": "HB9XXX", "dxcc": "HB", "country": "Switzerland",  "category": "C"},
]

# External stations (not in our set, for realism)
EXTERNAL_CALLSIGNS = [
    "YU1ABC", "YU5DEF", "E72ZZZ", "R3AAA", "RA3BBB",
    "UA3CCC", "RK3DDD", "UR5FFF", "US0GGG", "UT5HHH",
    "LZ1ABC", "LZ5DEF", "LZ9GHI", "9A1AAA", "9A5BBB",
    "9A9CCC", "LY2AAA", "LY5BBB", "ES1ABC", "ES5DEF",
    "TF3AAA", "TF5BBB", "JW5ABC", "JW9DEF", "OH2ABC",
    "OH5DEF", "SM5ABC", "SM5DEF", "LA5ABC", "LA5DEF",
    "OZ5ABC", "OZ5DEF", "DL5ZZZ", "DF5AAA", "DJ5BBB",
    "F6ABC", "F8DEF", "CT1ABC", "CT3DEF", "EA5ABC",
    "EA5DEF", "EA7GHI", "IK5ABC", "IK5DEF", "IZ5GHI",
    "S51ABC", "S53DEF", "HG5ABC", "HG5DEF", "HA8GHI",
    "OK2ABC", "OK5DEF", "OM5ABC", "OM5DEF", "OM7GHI",
    "SP5ABC", "SQ5DEF", "SP9GHI", "YO5PJB", "YO9XC",
    "UR0ABC", "UT5DEF", "UU0GHI", "EM5ABC", "EN5DEF",
    "ER5ABC", "ER5DEF", "EV5GHI", "EW5ABC", "EX5DEF",
    "R5AAA", "R9BBB", "RA3CCC", "RK5DDD", "RN5EEE",
    "RU5FFF", "RV3GGG", "UA5HHH", "UN5AAA", "UN9BBB",
    "UN7CCC", "UP5DDD", "4X0ABC", "4X5DEF", "4Z5GHI",
    "HZ5ABC", "HZ5DEF", "A65AAA", "A65BBB", "A65CCC",
    "VU2ABC", "VU2DEF", "VU3GHI", "HS0ABC", "HS5DEF",
    "E20ABC", "E25DEF", "BV5ABC", "BV5DEF", "BV9GHI",
    "JA1ABC", "JA5DEF", "JR5GHI", "JH5IJK", "JE5LMN",
    "ZL2ABC", "ZL5DEF", "ZL7GHI", "VK2ABC", "VK5DEF",
    "VE3ABC", "VE3DEF", "VE5GHI", "W1ABC", "W2DEF",
    "W3GHI", "W4IJK", "W5LMN", "W6OPQ", "W7RST",
    "N1ABC", "N2DEF", "K1AAA", "K5BBB", "AA5CCC",
    "KP2ABC", "KP5DEF", "WP4AAA", "NP4BBB",
]

# Band definitions
BANDS = [
    {"band_name": "7",  "cabrillo_band": "40M",  "cw_freqs": [7005, 7010, 7015, 7020, 7025, 7030, 7035, 7040],
     "ssb_freqs": [7100, 7110, 7120, 7130, 7140, 7150, 7160, 7170, 7180, 7190, 7200]},
    {"band_name": "14", "cabrillo_band": "20M",  "cw_freqs": [14005, 14010, 14015, 14020, 14025, 14030, 14035, 14040, 14045],
     "ssb_freqs": [14150, 14160, 14170, 14180, 14190, 14200, 14210, 14220, 14230, 14240, 14250, 14260, 14270, 14280, 14290, 14300, 14310, 14320, 14330, 14340, 14350]},
]


# ── Helper functions ───────────────────────────────────────────────────

def _make_qso_line(freq, mode, date_str, time_str, call_sent, rst_sent,
                   exch_sent, call_recv, rst_recv, exch_recv):
    """Create a Cabrillo V3 QSO line."""
    return "QSO: {freq} {mode} {date} {time} {call_sent:<16s}{rst_sent:<4s}{exch_sent:<4s}{call_recv:<16s}{rst_recv:<4s}{exch_recv}".format(
        freq=freq, mode=mode, date=date_str, time=time_str,
        call_sent=call_sent, rst_sent=rst_sent, exch_sent=exch_sent,
        call_recv=call_recv, rst_recv=rst_recv, exch_recv=exch_recv
    )


def _generate_date_time(begin_date, end_date, begin_hour, end_hour, rand):
    """
    Generate a random (date_yyyy_mm_dd, time_hhmm) tuple within the contest period.
    """
    bd = datetime.strptime(begin_date + begin_hour, "%Y%m%d%H%M")
    ed = datetime.strptime(end_date + end_hour, "%Y%m%d%H%M")
    if ed <= bd:
        ed = ed + timedelta(days=1)
    delta = ed - bd
    offset_seconds = rand.randint(0, max(0, int(delta.total_seconds()) - 60))
    qso_dt = bd + timedelta(seconds=offset_seconds)
    return qso_dt.strftime("%Y-%m-%d"), qso_dt.strftime("%H%M")


def _generate_qso_rst(mode, rand):
    """Return appropriate RST for mode."""
    if mode == "CW":
        return "599"
    else:
        return "59"


def _get_exchange_for_station(station):
    """Return the exchange value based on station type (static per station, not per-QSO)."""
    if station.get("type") == "DRACULA":
        return "DRC"
    elif station.get("type") == "YO":
        return station.get("county", "BCN")
    elif station.get("type") == "NON_YO":
        return station.get("exchange", "001")
    return "000"


def _get_cabrillo_mode_category(station, contest_modes):
    """
    Determine which Cabrillo mode category the station belongs to
    based on the contest category (A1=A2=SSB? No, A1=SSB, A2=CW, A3=MIXT, etc.)
    Returns list of modes the station operates on.
    """
    cat_upper = station["category"].upper()
    if cat_upper in ("A1", "B1"):
        return ["PH"]
    elif cat_upper in ("A2", "B2"):
        return ["CW"]
    elif cat_upper in ("A3", "B3", "C"):
        return contest_modes  # both modes
    return contest_modes  # default: both


# ── Main generation function ───────────────────────────────────────────

def generate_logs(
    seed=42,
    output_dir="test_logs/cabrillo/logs_dracula",
    density=0.40,
    external_qso_min=5,
    external_qso_max=12,
    contest_name=DEFAULT_CONTEST_NAME,
    begin_date=DEFAULT_BEGIN_DATE,
    end_date=DEFAULT_END_DATE,
    begin_hour=DEFAULT_BEGIN_HOUR,
    end_hour=DEFAULT_END_HOUR,
    bands=None,
    dry_run=False,
):
    """
    Generate DRACULA contest Cabrillo log files.

    Args:
        seed: Random seed for reproducibility
        output_dir: Directory to write log files
        density: Connectivity density between stations (0.0-1.0)
        external_qso_min: Minimum external QSOs per station
        external_qso_max: Maximum external QSOs per station
        contest_name: Contest name
        begin_date: Contest begin date (YYYYMMDD)
        end_date: Contest end date (YYYYMMDD)
        begin_hour: Contest begin hour (HHMM)
        end_hour: Contest end hour (HHMM)
        bands: List of band configs (defaults to BANDS)
        dry_run: If True, only print summary without writing files
    """
    if bands is None:
        bands = BANDS

    rand = random.Random(seed)

    # ------------------------------------------------------------------
    # 1. Build the station list
    # ------------------------------------------------------------------
    all_stations = []

    # DRACULA specials (index 0-2)
    for i, sp in enumerate(DRACULA_SPECIALS):
        all_stations.append({
            **sp,
            "type": "DRACULA",
            "exchange": "DRC",
            "idx": i,
        })

    # YO stations (index 3-8)
    offset = len(all_stations)
    for i, yo in enumerate(YO_STATIONS):
        all_stations.append({
            **yo,
            "type": "YO",
            "exchange": yo["county"],
            "idx": offset + i,
        })

    # Non-YO stations (index 9+)
    offset = len(all_stations)
    for i, ny in enumerate(NON_YO_STATIONS):
        all_stations.append({
            **ny,
            "type": "NON_YO",
            "exchange": f"{i+1:03d}",
            "idx": offset + i,
        })

    contest_modes = ["CW", "PH"]

    # ------------------------------------------------------------------
    # 2. Assign band/mode capabilities for each station
    # ------------------------------------------------------------------
    station_band_mode = {}  # station_idx -> {band_idx: [modes]}

    for s in all_stations:
        sidx = s["idx"]
        station_band_mode[sidx] = {}
        station_modes = _get_cabrillo_mode_category(s, contest_modes)

        for b_idx in range(len(bands)):
            pass_band_roll = rand.random()

            if s["type"] == "DRACULA":
                # DRACULA stations always work all bands with all their modes
                station_band_mode[sidx][b_idx] = station_modes
                continue

            # Non-DRACULA: 85% chance to be on this band
            if pass_band_roll < 0.85:
                modes_on_band = []
                for m in station_modes:
                    if rand.random() < 0.85:
                        modes_on_band.append(m)
                if modes_on_band:
                    station_band_mode[sidx][b_idx] = modes_on_band

        # Ensure every station has at least one band
        if not station_band_mode[sidx]:
            # Force station onto first band with all its modes
            station_band_mode[sidx][0] = station_modes
            # Possibly also second band
            if len(bands) > 1 and rand.random() < 0.5:
                station_band_mode[sidx][1] = station_modes

    # ------------------------------------------------------------------
    # 3. Build connectivity matrix (partial)
    # ------------------------------------------------------------------
    connectivity = {}
    station_count = len(all_stations)

    for i in range(station_count):
        for j in range(i + 1, station_count):
            s1 = all_stations[i]
            s2 = all_stations[j]

            # YO-YO pairs: only 5% connect (for 0-pt testing)
            if s1["type"] == "YO" and s2["type"] == "YO":
                connectivity[(i, j)] = rand.random() < 0.05
            else:
                # Normal: density determines connection
                connectivity[(i, j)] = rand.random() < density

    # ------------------------------------------------------------------
    # 4. Generate internal QSO data for each station
    # ------------------------------------------------------------------
    station_qsos = {s["idx"]: [] for s in all_stations}
    total_internal_qsos = 0
    total_external_qsos = 0

    for i in range(station_count):
        s1 = all_stations[i]
        for j in range(i + 1, station_count):
            if not connectivity.get((i, j), False):
                continue
            s2 = all_stations[j]

            # Find common bands and modes
            common = set(station_band_mode.get(i, {}).keys()) & set(station_band_mode.get(j, {}).keys())
            if not common:
                continue

            for b_idx in common:
                modes_i = set(station_band_mode[i].get(b_idx, []))
                modes_j = set(station_band_mode[j].get(b_idx, []))
                common_modes = modes_i & modes_j
                for mode in common_modes:
                    freq_band = bands[b_idx]
                    if mode == "CW":
                        freq = rand.choice(freq_band["cw_freqs"])
                    else:
                        freq = rand.choice(freq_band["ssb_freqs"])

                    date_str, time_str = _generate_date_time(
                        begin_date, end_date, begin_hour, end_hour, rand
                    )

                    rst1 = _generate_qso_rst(mode, rand)
                    rst2 = _generate_qso_rst(mode, rand)
                    exch1 = _get_exchange_for_station(s1)
                    exch2 = _get_exchange_for_station(s2)

                    # QSO from s1 perspective (worked s2)
                    station_qsos[i].append({
                        "freq": f'{freq:>5}', "mode": mode,
                        "date": date_str, "time": time_str,
                        "partner": s2["callsign"],
                        "rst_sent": rst1, "exch_sent": exch1,
                        "rst_recv": rst2, "exch_recv": exch2,
                        "partner_idx": j,
                    })

                    # QSO from s2 perspective (worked s1) - slightly different time
                    qso_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H%M")
                    offset_seconds = rand.randint(-120, 120)
                    qso2_dt = qso_dt + timedelta(seconds=offset_seconds)
                    qso2_date = qso2_dt.strftime("%Y-%m-%d")
                    qso2_time = qso2_dt.strftime("%H%M")

                    station_qsos[j].append({
                        "freq": f'{freq:>5}', "mode": mode,
                        "date": qso2_date, "time": qso2_time,
                        "partner": s1["callsign"],
                        "rst_sent": rst2, "exch_sent": exch2,
                        "rst_recv": rst1, "exch_recv": exch1,
                        "partner_idx": i,
                    })

                    total_internal_qsos += 2

    # ------------------------------------------------------------------
    # 5. Add external QSOs (with stations outside our set)
    # ------------------------------------------------------------------
    for s in all_stations:
        s_idx = s["idx"]
        ext_count = rand.randint(external_qso_min, external_qso_max)
        ext_calls = rand.sample(EXTERNAL_CALLSIGNS, min(ext_count, len(EXTERNAL_CALLSIGNS)))

        for ext_call in ext_calls:
            b_idx = rand.choice(list(station_band_mode.get(s_idx, {0: ["CW"]}).keys()))
            freq_band = bands[b_idx]
            modes_avail = station_band_mode[s_idx].get(b_idx, ["CW"])
            mode = rand.choice(modes_avail)

            if mode == "CW":
                freq = rand.choice(freq_band["cw_freqs"])
            else:
                freq = rand.choice(freq_band["ssb_freqs"])

            date_str, time_str = _generate_date_time(
                begin_date, end_date, begin_hour, end_hour, rand
            )

            station_qsos[s_idx].append({
                "freq": f'{freq:>5}', "mode": mode,
                "date": date_str, "time": time_str,
                "partner": ext_call,
                "rst_sent": _generate_qso_rst(mode, rand),
                "exch_sent": _get_exchange_for_station(s),
                "rst_recv": _generate_qso_rst(mode, rand),
                "exch_recv": f"{rand.randint(1, 999):03d}",
                "partner_idx": None,
            })
            total_external_qsos += 1

    # ------------------------------------------------------------------
    # 6. Sort QSOs by date/time for each station, then assign serials
    # ------------------------------------------------------------------
    for s_idx in station_qsos:
        station_qsos[s_idx].sort(key=lambda q: (q["date"], q["time"]))

    # Assign per-QSO incrementing serial numbers for non-YO stations
    # This must happen AFTER sorting so serials match chronological order
    station_serial = {s["idx"]: 1 for s in all_stations}
    for s in all_stations:
        s_idx = s["idx"]
        if s["type"] == "NON_YO":
            for q in station_qsos[s_idx]:
                q["exch_sent"] = f"{station_serial[s_idx]:03d}"
                station_serial[s_idx] += 1

    # ------------------------------------------------------------------
    # 7. Print summary
    # ------------------------------------------------------------------
    print("=" * 70)
    print("DRACULA Contest Log Generator")
    print("=" * 70)
    print(f"  Seed:               {seed}")
    print(f"  Density:            {density}")
    print(f"  Output dir:         {output_dir}")
    print(f"  Contest:            {contest_name} ({begin_date} {begin_hour} - {end_date} {end_hour})")
    print(f"  Bands:              {', '.join(b['cabrillo_band'] for b in bands)}")
    print(f"  Total stations:     {station_count}")
    print(f"    DRACULA specials: {len(DRACULA_SPECIALS)}")
    print(f"    YO stations:      {len(YO_STATIONS)}")
    print(f"    Non-YO stations:  {len(NON_YO_STATIONS)}")
    print(f"  Internal QSOs:      {total_internal_qsos}")
    print(f"  External QSOs:      {total_external_qsos}")
    print(f"  Total QSOs:         {total_internal_qsos + total_external_qsos}")
    print("-" * 70)

    # Station details table
    print(f"\n{'Idx':<4s} {'Callsign':<16s} {'Type':<8s} {'Category':<6s} {'Exch':<6s} {'Bands/Modes':<20s}")
    print("-" * 70)
    for s in all_stations:
        bm_info = []
        for b_idx in sorted(station_band_mode.get(s["idx"], {}).keys()):
            mstr = "/".join(station_band_mode[s["idx"]][b_idx])
            bm_info.append(f"{bands[b_idx]['cabrillo_band']}({mstr})")
        bm_str = ", ".join(bm_info) if bm_info else "NONE"
        print(f"{s['idx']:<4d} {s['callsign']:<16s} {s['type']:<8s} {s['category']:<6s} {s['exchange']:<6s} {bm_str:<20s}")

    print(f"\nInternal QSOs:  {total_internal_qsos}")
    print(f"External QSOs:  {total_external_qsos}")
    print(f"Total QSOs:     {total_internal_qsos + total_external_qsos}")
    print()

    if dry_run:
        print("[DRY RUN] No files written.")
        return all_stations, station_qsos, station_band_mode, bands

    # ------------------------------------------------------------------
    # 8. Write log files
    # ------------------------------------------------------------------
    os.makedirs(output_dir, exist_ok=True)

    for s in all_stations:
        s_idx = s["idx"]
        callsign = s["callsign"]
        qsos = station_qsos[s_idx]

        filepath = os.path.join(output_dir, f"{callsign}.log")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"START-OF-LOG: 3.0\n")
            f.write(f"CONTEST: {contest_name}\n")
            f.write(f"CALLSIGN: {callsign}\n")
            f.write(f"CATEGORY-OPERATOR: {s['category']}\n")

            active_bands = station_band_mode.get(s_idx, {})
            if not active_bands:
                active_bands = {0: ["CW"]}
            band_names = []
            for b_idx in sorted(active_bands.keys()):
                band_names.append(bands[b_idx]["cabrillo_band"])
            if len(band_names) == len(bands):
                f.write(f"CATEGORY-BAND: ALL\n")
            else:
                f.write(f"CATEGORY-BAND: {' '.join(band_names)}\n")

            cat_upper = s["category"].upper()
            if cat_upper in ("A1", "B1"):
                f.write(f"CATEGORY-MODE: SSB\n")
            elif cat_upper in ("A2", "B2"):
                f.write(f"CATEGORY-MODE: CW\n")
            else:
                f.write(f"CATEGORY-MODE: MIXED\n")
            f.write(f"CREATED-BY: logXchecker test generator\n")
            f.write(f"\n")

            for q in qsos:
                f.write(_make_qso_line(
                    freq=q["freq"], mode=q["mode"],
                    date_str=q["date"], time_str=q["time"],
                    call_sent=callsign,
                    rst_sent=q["rst_sent"], exch_sent=q["exch_sent"],
                    call_recv=q["partner"],
                    rst_recv=q["rst_recv"], exch_recv=q["exch_recv"],
                ) + "\n")

            f.write(f"END-OF-LOG:\n")

        print(f"  Wrote {filepath}  ({len(qsos)} QSOs)")

    print(f"\nDone. {len(all_stations)} log files written to {os.path.abspath(output_dir)}")

    return all_stations, station_qsos, station_band_mode, bands


# ── CLI entry point ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate DRACULA contest Cabrillo V3 test logs"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility (default: 42)"
    )
    parser.add_argument(
        "--output-dir", type=str, default="test_logs/cabrillo/logs_dracula",
        help="Output directory for log files"
    )
    parser.add_argument(
        "--density", type=float, default=0.40,
        help="Connectivity density 0.0-1.0 (default: 0.40)"
    )
    parser.add_argument(
        "--external-min", type=int, default=5,
        help="Minimum external QSOs per station (default: 5)"
    )
    parser.add_argument(
        "--external-max", type=int, default=12,
        help="Maximum external QSOs per station (default: 12)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print summary without writing files"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = main()
    generate_logs(
        seed=args.seed,
        output_dir=args.output_dir,
        density=args.density,
        external_qso_min=args.external_min,
        external_qso_max=args.external_max,
        dry_run=args.dry_run,
    )
