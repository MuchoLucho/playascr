#!/usr/bin/env python3
# Copyright 2026 PlayasCR Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Verify integrity, coordinate bounds, locale enum parity, and file-size budgets
for extracted PlayasCR datasets.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SECTORS_DIR = DATA_DIR / "sectors"
LOCALES_DIR = ROOT / "locales"

EXPECTED_SECTORS = [f"{i}P" for i in range(1, 24)] + [f"{i}C" for i in range(1, 8)]

CR_LAT_MIN, CR_LAT_MAX = 8.0, 11.3
CR_LNG_MIN, CR_LNG_MAX = -86.0, -82.5


def assert_cond(cond: bool, msg: str, errors: list[str]) -> None:
    if not cond:
        errors.append(msg)


def main() -> int:
    errors: list[str] = []

    index_path = DATA_DIR / "beaches-index.json"
    overview_path = DATA_DIR / "sectors-overview.json"
    assert_cond(index_path.exists(), "Missing data/beaches-index.json", errors)
    assert_cond(overview_path.exists(), "Missing data/sectors-overview.json", errors)
    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        return 1

    beaches = json.loads(index_path.read_text(encoding="utf-8"))
    overview = json.loads(overview_path.read_text(encoding="utf-8"))
    es = json.loads((LOCALES_DIR / "es.json").read_text(encoding="utf-8"))
    en = json.loads((LOCALES_DIR / "en.json").read_text(encoding="utf-8"))

    # File-size budgets for fast GitHub Pages static lazy loading
    idx_kb = index_path.stat().st_size / 1024.0
    assert_cond(idx_kb < 500.0, f"beaches-index.json too large: {idx_kb:.1f} KB >= 500 KB", errors)

    # Sector overview checks
    sec_list = overview.get("sectors", [])
    sec_ids = [s["id"] for s in sec_list]
    assert_cond(len(sec_ids) == 30, f"Expected 30 sectors, found {len(sec_ids)}", errors)
    assert_cond(set(sec_ids) == set(EXPECTED_SECTORS), f"Sector mismatch: {set(EXPECTED_SECTORS) ^ set(sec_ids)}", errors)

    for sid in EXPECTED_SECTORS:
        sfile = SECTORS_DIR / f"sector-{sid}.geojson"
        assert_cond(sfile.exists(), f"Missing sector GeoJSON: {sfile.name}", errors)
        if sfile.exists():
            skb = sfile.stat().st_size / 1024.0
            assert_cond(skb < 150.0, f"{sfile.name} too large: {skb:.1f} KB >= 150 KB", errors)
            gj = json.loads(sfile.read_text(encoding="utf-8"))
            assert_cond(gj.get("type") == "FeatureCollection", f"{sfile.name} invalid FeatureCollection", errors)
            assert_cond(len(gj.get("features", [])) > 0, f"{sfile.name} has 0 features", errors)

    # Beach count and uniqueness
    assert_cond(len(beaches) >= 650, f"Too few beaches extracted: {len(beaches)} < 650", errors)
    seen_ids: set[str] = set()

    enum_checks = [
        ("region", "regions"),
        ("rip", "rip"),
        ("swim", "swim"),
        ("family", "family"),
        ("surf", "surf"),
        ("accessType", "accessType"),
        ("accessMode", "accessMode"),
        ("accessState", "accessState"),
        ("sand", "sand"),
        ("geo", "geo"),
        ("infra", "infra"),
    ]

    for b in beaches:
        bid = b.get("id", "")
        assert_cond(bool(bid) and bid not in seen_ids, f"Duplicate or empty beach id: {bid}", errors)
        seen_ids.add(bid)

        lat = b.get("lat")
        lng = b.get("lng")
        assert_cond(
            isinstance(lat, (int, float)) and CR_LAT_MIN <= lat <= CR_LAT_MAX,
            f"{bid}: lat out of CR bounds ({lat})",
            errors,
        )
        assert_cond(
            isinstance(lng, (int, float)) and CR_LNG_MIN <= lng <= CR_LNG_MAX,
            f"{bid}: lng out of CR bounds ({lng})",
            errors,
        )
        assert_cond(b.get("sector") in EXPECTED_SECTORS, f"{bid}: invalid sector {b.get('sector')}", errors)

        for field, locale_group in enum_checks:
            val = b.get(field)
            assert_cond(val in es.get(locale_group, {}), f"{bid}: '{field}={val}' missing in es.{locale_group}", errors)
            assert_cond(val in en.get(locale_group, {}), f"{bid}: '{field}={val}' missing in en.{locale_group}", errors)

        for h in b.get("hazards", []):
            assert_cond(h in es.get("hazards", {}), f"{bid}: hazard '{h}' missing in es.hazards", errors)
            assert_cond(h in en.get("hazards", {}), f"{bid}: hazard '{h}' missing in en.hazards", errors)

        for u in b.get("uses", []):
            assert_cond(u in es.get("uses", {}), f"{bid}: use '{u}' missing in es.uses", errors)
            assert_cond(u in en.get("uses", {}), f"{bid}: use '{u}' missing in en.uses", errors)

    if errors:
        print(f"VERIFICATION FAILED ({len(errors)} errors):")
        for e in errors[:25]:
            print(f"  - {e}")
        return 1

    print(
        f"VERIFICATION PASSED: {len(beaches)} beaches across {len(sec_ids)} sectors, "
        f"beaches-index.json={idx_kb:.1f} KB, all bounds and i18n enums valid."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
