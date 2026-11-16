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
Extract and georeference all Costa Rica beaches from:
  ATLAS DE PLAYAS COSTA RICA web 2024.pdf

Outputs:
  - data/beaches-index.json      (Tier 1 compact index for instant boot, clustering & filtering)
  - data/sectors-overview.json   (30 sector metadata, bounds, and aggregated stats)
  - data/sectors/sector-*.geojson (Tier 2 lazy-loaded GeoJSON polygons & synthesized notes)
"""

from __future__ import annotations

import json
import math
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np
import pymupdf

ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = ROOT / "ATLAS DE PLAYAS COSTA RICA web 2024.pdf"
DATA_DIR = ROOT / "data"
SECTORS_DIR = DATA_DIR / "sectors"

# ---------------------------------------------------------------------------
# 1. CRTM05 (EPSG:5367) -> WGS84 Inverse Transverse Mercator Projection
# ---------------------------------------------------------------------------
WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563
WGS84_E2 = 2 * WGS84_F - WGS84_F * WGS84_F
CRTM05_K0 = 0.9999
CRTM05_LON0 = math.radians(-84.0)
CRTM05_FE = 500000.0
CRTM05_FN = 0.0


def crtm05_to_wgs84(easting: float, northing: float) -> tuple[float, float]:
    """Convert CRTM05 (Easting, Northing) in meters to WGS84 (lat, lng) in degrees."""
    e2 = WGS84_E2
    ep2 = e2 / (1.0 - e2)
    e1 = (1.0 - math.sqrt(1.0 - e2)) / (1.0 + math.sqrt(1.0 - e2))

    x = easting - CRTM05_FE
    y = northing - CRTM05_FN
    M = y / CRTM05_K0
    mu = M / (WGS84_A * (1.0 - e2 / 4.0 - 3.0 * e2**2 / 64.0 - 5.0 * e2**3 / 256.0))

    phi1 = (
        mu
        + (3.0 * e1 / 2.0 - 27.0 * e1**3 / 32.0) * math.sin(2.0 * mu)
        + (21.0 * e1**2 / 16.0 - 55.0 * e1**4 / 32.0) * math.sin(4.0 * mu)
        + (151.0 * e1**3 / 96.0) * math.sin(6.0 * mu)
        + (1097.0 * e1**4 / 512.0) * math.sin(8.0 * mu)
    )

    sin_p = math.sin(phi1)
    cos_p = math.cos(phi1)
    tan_p = math.tan(phi1)

    N1 = WGS84_A / math.sqrt(1.0 - e2 * sin_p**2)
    T1 = tan_p**2
    C1 = ep2 * cos_p**2
    R1 = WGS84_A * (1.0 - e2) / ((1.0 - e2 * sin_p**2) ** 1.5)
    D = x / (N1 * CRTM05_K0)

    lat = phi1 - (N1 * tan_p / R1) * (
        D**2 / 2.0
        - (5.0 + 3.0 * T1 + 10.0 * C1 - 4.0 * C1**2 - 9.0 * ep2) * D**4 / 24.0
        + (61.0 + 90.0 * T1 + 298.0 * C1 + 45.0 * T1**2 - 252.0 * ep2 - 3.0 * C1**2) * D**6 / 720.0
    )
    lon = CRTM05_LON0 + (
        D
        - (1.0 + 2.0 * T1 + C1) * D**3 / 6.0
        + (5.0 - 2.0 * C1 + 28.0 * T1 - 3.0 * C1**2 + 8.0 * ep2 + 24.0 * T1**2) * D**5 / 120.0
    ) / cos_p

    return (round(math.degrees(lat), 5), round(math.degrees(lon), 5))


# ---------------------------------------------------------------------------
# 2. Sector Metadata (30 Sectors across 5 Coastal Regions)
# ---------------------------------------------------------------------------
SECTORS_META: list[dict[str, Any]] = [
    {"id": "1P", "region": "guanacaste_nicoya", "name": "Bahía Salinas – Bahía Cuajiniquil", "intro_pages": [19, 20]},
    {"id": "2P", "region": "guanacaste_nicoya", "name": "Península de Santa Elena", "intro_pages": [25]},
    {"id": "3P", "region": "guanacaste_nicoya", "name": "Golfo del Papagayo – Bahía Culebra", "intro_pages": [30, 31, 32]},
    {"id": "4P", "region": "guanacaste_nicoya", "name": "Bahía Potrero – Playa Tamarindo", "intro_pages": [37, 38, 39]},
    {"id": "5P", "region": "guanacaste_nicoya", "name": "Playa Avellanas – Playa San Juanillo", "intro_pages": [44, 45, 46, 47]},
    {"id": "6P", "region": "guanacaste_nicoya", "name": "Playa Ostional – Playa Carrillo", "intro_pages": [52, 53]},
    {"id": "7P", "region": "guanacaste_nicoya", "name": "Playa Camaronal – Playa Ario", "intro_pages": [58, 59]},
    {"id": "8P", "region": "guanacaste_nicoya", "name": "Playa Santa Teresa – Playa Tambor", "intro_pages": [64, 65, 66]},
    {"id": "9P", "region": "golfo_nicoya", "name": "Isla Tortuga", "intro_pages": [72, 73, 74]},
    {"id": "10P", "region": "golfo_nicoya", "name": "Golfo de Nicoya", "intro_pages": [79]},
    {"id": "11P", "region": "pacifico_central", "name": "Puntarenas", "intro_pages": [85, 86, 87, 88]},
    {"id": "12P", "region": "pacifico_central", "name": "Playa Tárcoles", "intro_pages": [93, 94]},
    {"id": "13P", "region": "pacifico_central", "name": "Playa Jacó", "intro_pages": [99, 100, 101]},
    {"id": "14P", "region": "pacifico_central", "name": "Palo Seco", "intro_pages": [106, 107]},
    {"id": "15P", "region": "pacifico_central", "name": "Playa Manuel Antonio", "intro_pages": [112, 113, 114]},
    {"id": "16P", "region": "pacifico_central", "name": "Playa Dominical", "intro_pages": [119, 120, 121]},
    {"id": "17P", "region": "pacifico_central", "name": "Parque Nacional Marino Ballena", "intro_pages": [126, 127]},
    {"id": "18P", "region": "pacifico_sur", "name": "Bahía Drake", "intro_pages": [133, 134]},
    {"id": "19P", "region": "pacifico_sur", "name": "Corcovado", "intro_pages": [139]},
    {"id": "20P", "region": "pacifico_sur", "name": "Cabo Matapalo", "intro_pages": [144, 145, 146]},
    {"id": "21P", "region": "pacifico_sur", "name": "Golfo Dulce", "intro_pages": [151, 152]},
    {"id": "22P", "region": "pacifico_sur", "name": "Golfito – Punta Banco Oeste", "intro_pages": [157]},
    {"id": "23P", "region": "pacifico_sur", "name": "Pavones – Punta Banco", "intro_pages": [162, 163, 164]},
    {"id": "1C", "region": "caribe", "name": "Manzanillo – Cahuita Sur", "intro_pages": [170, 171, 172, 173]},
    {"id": "2C", "region": "caribe", "name": "Cahuita", "intro_pages": [178, 179, 180]},
    {"id": "3C", "region": "caribe", "name": "Playa Bananito – Playa Moín", "intro_pages": [185, 186, 187]},
    {"id": "4C", "region": "caribe", "name": "Matina – Madre de Dios", "intro_pages": [192, 193]},
    {"id": "5C", "region": "caribe", "name": "Boca del Río Parismina – Jaloba", "intro_pages": [198, 199]},
    {"id": "6C", "region": "caribe", "name": "Tortuguero", "intro_pages": [204]},
    {"id": "7C", "region": "caribe", "name": "Boca del Río Colorado", "intro_pages": [209, 210]},
]
SECTOR_META_MAP = {s["id"]: s for s in SECTORS_META}

# ---------------------------------------------------------------------------
# 3. Color & Symbol Lookup Palettes from the Atlas Legends
# ---------------------------------------------------------------------------
# Color de la Arena -> Geomorphology vector fill colors (top bright fill)
GEO_FILL_COLORS: dict[tuple[float, float, float], str] = {
    (0.298, 0.902, 0.0): "recta_abierta",
    (1.0, 0.333, 0.0): "herradura_grande",
    (1.0, 1.0, 0.0): "herradura_pequena",
    (0.663, 0.0, 0.902): "rocosa",
    (0.451, 0.698, 1.0): "fluvial",
    (1.0, 0.827, 0.498): "manglar",
    # Secondary/darker shade variants occasionally emitted as standalone fill
    (0.22, 0.659, 0.0): "recta_abierta",
    (0.659, 0.22, 0.0): "herradura_grande",
    (0.902, 0.902, 0.0): "herradura_pequena",
    (0.518, 0.0, 0.659): "rocosa",
    (0.0, 0.439, 1.0): "fluvial",
    (0.659, 0.439, 0.0): "manglar",
}

# Sand color ESRIDefaultMarker hex codes -> semantic key
SAND_HEX_MAP: dict[str, str] = {
    "#d7d79e": "parda_clara",
    "#cdaa66": "parda",
    "#a87000": "parda_oscura",
    "#e64c00": "parda_rojiza",
    "#ff5500": "parda_rojiza",
    "#ffffff": "blanca",
    "#828282": "sin_datos",
    "#000000": "negra",
}

# Rendered RGB signatures (0-255): interior fills + border outlines for thin strips
RIP_RGB_PALETTE: dict[str, tuple[tuple[int, int, int], ...]] = {
    "muy_alto": ((255, 115, 223), (115, 0, 75)),
    "alto": ((255, 127, 127), (230, 0, 0)),
    "medio": ((255, 235, 174), (230, 230, 0)),
    "bajo": ((84, 255, 0), (111, 168, 0), (56, 168, 0)),
    "no_visitado": ((130, 130, 130), (78, 78, 78)),
}

ACCESS_TYPE_RGB_PALETTE: dict[str, tuple[tuple[int, int, int], ...]] = {
    "publico": ((75, 230, 0), (56, 168, 0)),
    "restringido": ((230, 230, 0), (168, 168, 0)),
}

INFRA_RGB_PALETTE: dict[str, tuple[tuple[int, int, int], ...]] = {
    "deshabitada": ((0, 168, 132), (0, 132, 168)),
    "resort_hotel": ((255, 126, 126), (230, 0, 0)),
    "viviendas": ((121, 142, 245), (111, 68, 136)),
    "varios_servicios": ((75, 230, 0), (75, 115, 0)),
    "sin_datos": ((156, 156, 156), (109, 109, 109)),
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def slugify(s: str) -> str:
    s = norm(s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "playa"


def rgb_dist(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    return math.sqrt((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2 + (c1[2] - c2[2]) ** 2)


# ---------------------------------------------------------------------------
# 4. Discover all Map Pages in the PDF
# ---------------------------------------------------------------------------
def discover_map_pages(doc: pymupdf.Document) -> dict[str, dict[str, int]]:
    pages: dict[str, dict[str, int]] = {}
    for i, page in enumerate(doc):
        txt = page.get_text("text")
        m = re.search(
            r"Mapa\s+(\d+)\s*([PC])\s+(?:de\s+)?(Peligros|Accesos|Color de la Arena|Usos)",
            txt,
            re.I,
        )
        if not m:
            continue
        sec = f"{m.group(1)}{m.group(2).upper()}"
        mtype = m.group(3).lower()
        # Handle PDF publisher typo: pages 200-203 are sector 5C chapter maps mislabeled "Mapa 6C"
        if sec == "6C" and (i + 1) <= 203:
            sec = "5C"
        # Handle PDF publisher typo: page 136 in 18P is mislabeled Usos (duplicate of 138)
        if sec == "18P" and mtype == "usos" and (i + 1) == 136:
            pages.setdefault(sec, {})["accesos_missing"] = i + 1
            continue
        pages.setdefault(sec, {})[mtype] = i + 1
    return pages


# ---------------------------------------------------------------------------
# 5. Parse the Master Glossary Table (Pages 217-236)
# ---------------------------------------------------------------------------
def parse_glossary(doc: pymupdf.Document) -> dict[str, list[dict[str, str]]]:
    by_sector: dict[str, list[dict[str, str]]] = {}
    for pidx in range(216, 236):
        page = doc[pidx]
        ys = set()
        for d in page.get_drawings():
            r = d["rect"]
            if 140 <= r.x0 <= 155 and 360 <= r.x1 <= 375 and abs(r.y1 - r.y0) < 2 and r.y0 >= 280:
                ys.add(round(r.y0, 2))
        ys_sorted = sorted(ys)
        words = page.get_text("words")

        for i in range(len(ys_sorted) - 1):
            y_top, y_bot = ys_sorted[i], ys_sorted[i + 1]
            if y_bot - y_top < 12:
                continue
            row_words = [w for w in words if y_top <= (w[1] + w[3]) / 2 <= y_bot]
            if not row_words:
                continue

            def col_text(x0: float, x1: float) -> str:
                ws = [w for w in row_words if x0 <= (w[0] + w[2]) / 2 <= x1]
                ws.sort(key=lambda w: (round(w[1] / 6), w[0]))
                return " ".join(w[4] for w in ws).strip()

            name = col_text(140, 367)
            sector = col_text(367, 507).replace(" ", "").upper()
            if not name or name == "NOMBRE EN EL ATLAS" or not re.match(r"^\d{1,2}[PC]$", sector):
                continue

            entry = {
                "name": name,
                "sector": sector,
                "ign_toponym": col_text(507, 696),
                "is_ign_beach": col_text(696, 806),
                "origin": col_text(806, 1051),
                "alt_names": col_text(1051, 1178),
                "notes": col_text(1178, 1680),
            }
            by_sector.setdefault(sector, []).append(entry)
    return by_sector


# ---------------------------------------------------------------------------
# 6. Georeference Calibration for Any Map Page
# ---------------------------------------------------------------------------
def calibrate_page_transform(page: pymupdf.Page) -> dict[str, Any]:
    """
    Fits linear affine transform from PDF (x, y) -> CRTM05 (E, N)
    using the CRTM05 grey grid lines and 6/7-digit coordinate labels.
    """
    drawings = page.get_drawings()
    ocean_rects = [
        d["rect"]
        for d in drawings
        if d.get("fill")
        and abs(d["fill"][0] - 0.745) < 0.02
        and abs(d["fill"][1] - 0.91) < 0.02
        and d["rect"].width > 400
    ]
    if ocean_rects:
        vp = max(ocean_rects, key=lambda r: r.width * r.height)
    else:
        vp = pymupdf.Rect(100, 100, 1220, 1700)

    # Vertical grid lines inside vp
    v_lines = sorted(
        {
            round(d["rect"].x0, 2)
            for d in drawings
            if d.get("color")
            and all(abs(c - 0.431) < 0.03 for c in d["color"])
            and d["rect"].width < 1.5
            and d["rect"].height > vp.height * 0.5
            and vp.x0 - 5 <= d["rect"].x0 <= vp.x1 + 5
        }
    )
    h_lines = sorted(
        {
            round(d["rect"].y0, 2)
            for d in drawings
            if d.get("color")
            and all(abs(c - 0.431) < 0.03 for c in d["color"])
            and d["rect"].height < 1.5
            and d["rect"].width > vp.width * 0.5
            and vp.y0 - 5 <= d["rect"].y0 <= vp.y1 + 5
        }
    )

    words = page.get_text("words")
    e_labels = [
        ((w[0] + w[2]) / 2.0, int(w[4]))
        for w in words
        if re.match(r"^[2-6]\d{5}$", w[4]) and int(w[4]) % 1000 == 0
    ]
    n_labels = [
        ((w[1] + w[3]) / 2.0, int(w[4]))
        for w in words
        if re.match(r"^(?:9\d{5}|1[0-2]\d{5})$", w[4]) and int(w[4]) % 1000 == 0
    ]

    # Match each grid line to nearest label
    e_pairs = []
    for vx in v_lines:
        near = [(abs(lx - vx), val) for lx, val in e_labels if abs(lx - vx) < 35]
        if near:
            near.sort()
            e_pairs.append((vx, near[0][1]))

    n_pairs = []
    for hy in h_lines:
        near = [(abs(ly - hy), val) for ly, val in n_labels if abs(ly - hy) < 35]
        if near:
            near.sort()
            n_pairs.append((hy, near[0][1]))

    # Deduplicate same value keeping median coordinate
    def fit_1d(pairs: list[tuple[float, int]], default_scale: float) -> tuple[float, float]:
        dedup: dict[int, list[float]] = {}
        for pos, val in pairs:
            dedup.setdefault(val, []).append(pos)
        pts = [(float(np.median(ps)), val) for val, ps in sorted(dedup.items())]
        if len(pts) >= 2:
            xs = np.array([p[0] for p in pts])
            ys = np.array([p[1] for p in pts])
            slope, intercept = np.polyfit(xs, ys, 1)
            return float(slope), float(intercept)
        elif len(pts) == 1:
            p0, v0 = pts[0]
            return default_scale, float(v0 - default_scale * p0)
        raise ValueError("Insufficient grid ticks to calibrate map page")

    # Standard 1:50,000 scale in this atlas: ~17.64 m/pt (x increases E, y increases S so Northing slope is negative)
    ax, bx = fit_1d(e_pairs, 17.64)
    ay, by = fit_1d(n_pairs, -17.64)

    return {
        "vp": vp,
        "ax": ax,
        "bx": bx,
        "ay": ay,
        "by": by,
    }


def pdf_to_wgs84(x: float, y: float, tf: dict[str, Any]) -> tuple[float, float]:
    easting = tf["ax"] * x + tf["bx"]
    northing = tf["ay"] * y + tf["by"]
    return crtm05_to_wgs84(easting, northing)


# ---------------------------------------------------------------------------
# 7. Vector Polygon Extraction & Simplification
# ---------------------------------------------------------------------------
def simplify_ring(pts: list[tuple[float, float]], eps: float = 0.00004) -> list[tuple[float, float]]:
    """Douglas-Peucker simplification in degrees (~4.4m tolerance) to keep GeoJSON compact."""
    if len(pts) <= 4:
        return pts

    def perp_dist(p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        if a == b:
            return math.hypot(p[0] - a[0], p[1] - a[1])
        return abs((b[0] - a[0]) * (a[1] - p[1]) - (a[0] - p[0]) * (b[1] - a[1])) / math.hypot(
            b[0] - a[0], b[1] - a[1]
        )

    def dp(seq: list[tuple[float, float]]) -> list[tuple[float, float]]:
        if len(seq) <= 2:
            return seq
        dmax = 0.0
        idx = 0
        for i in range(1, len(seq) - 1):
            d = perp_dist(seq[i], seq[0], seq[-1])
            if d > dmax:
                idx = i
                dmax = d
        if dmax > eps:
            r1 = dp(seq[: idx + 1])
            r2 = dp(seq[idx:])
            return r1[:-1] + r2
        return [seq[0], seq[-1]]

    closed = pts[0] == pts[-1]
    res = dp(pts[:-1] if closed else pts)
    if len(res) < 3:
        res = pts[:3]
    if closed and res[0] != res[-1]:
        res.append(res[0])
    return res


def extract_beach_polygons(page: pymupdf.Page, vp: pymupdf.Rect) -> list[dict[str, Any]]:
    """
    Extract all beach polygons from a Color de la Arena page.
    ArcGIS writes two stacked paths per beach: a darker outline/fill and the bright fill.
    We keep the bright fills (or deduplicate identical bounding boxes) and convert vertices.
    """
    raw = []
    for d in page.get_drawings():
        if d.get("fill") is None:
            continue
        r = d["rect"]
        if not vp.contains(r) or r.width > vp.width * 0.85 or (r.width < 1.5 and r.height < 1.5):
            continue
        col = tuple(round(c, 3) for c in d["fill"])
        if col not in GEO_FILL_COLORS:
            continue
        geo_type = GEO_FILL_COLORS[col]

        # Extract path points
        pts: list[tuple[float, float]] = []
        for item in d["items"]:
            op = item[0]
            if op == "l":
                if not pts:
                    pts.append((item[1].x, item[1].y))
                pts.append((item[2].x, item[2].y))
            elif op == "c":
                if not pts:
                    pts.append((item[1].x, item[1].y))
                pts.append((item[4].x, item[4].y))
            elif op == "re":
                rr = item[1]
                pts = [(rr.x0, rr.y0), (rr.x1, rr.y0), (rr.x1, rr.y1), (rr.x0, rr.y1), (rr.x0, rr.y0)]

        if len(pts) < 3:
            continue
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        raw.append(
            {
                "geo": geo_type,
                "rect": r,
                "pts": pts,
                "cx": cx,
                "cy": cy,
                "area": r.width * r.height,
                "is_primary": col in {
                    (0.298, 0.902, 0.0),
                    (1.0, 0.333, 0.0),
                    (1.0, 1.0, 0.0),
                    (0.663, 0.0, 0.902),
                    (0.451, 0.698, 1.0),
                    (1.0, 0.827, 0.498),
                },
            }
        )

    # Deduplicate stacked fill/stroke pairs (keep primary bright fill when duplicate rect exists)
    deduped = []
    for poly in raw:
        matched = False
        for idx, existing in enumerate(deduped):
            if (
                abs(poly["cx"] - existing["cx"]) < 2.5
                and abs(poly["cy"] - existing["cy"]) < 2.5
                and abs(poly["rect"].width - existing["rect"].width) < 3.0
                and abs(poly["rect"].height - existing["rect"].height) < 3.0
            ):
                if poly["is_primary"] and not existing["is_primary"]:
                    deduped[idx] = poly
                matched = True
                break
        if not matched:
            deduped.append(poly)
    return deduped


# ---------------------------------------------------------------------------
# 8. Extract Labels & Sand Color Dots from Color de la Arena Page
# ---------------------------------------------------------------------------
def extract_map_labels_and_sand(page: pymupdf.Page, vp: pymupdf.Rect) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Merge multi-line beach text labels inside/near the map viewport,
    and extract ESRIDefaultMarker sand-color dots.
    """
    td = page.get_text("dict")
    raw_lines = []
    sand_dots = []

    for b in td["blocks"]:
        for l in b.get("lines", []):
            spans = l.get("spans", [])
            if not spans:
                continue
            # Check for ESRIDefaultMarker sand dots
            is_marker = any("ESRIDefaultMarker" in s["font"] for s in spans)
            if is_marker:
                bx = (l["bbox"][0] + l["bbox"][2]) / 2.0
                by = (l["bbox"][1] + l["bbox"][3]) / 2.0
                if not (vp.x0 - 15 <= bx <= vp.x1 + 15 and vp.y0 - 15 <= by <= vp.y1 + 15):
                    continue
                colors = [f"#{s['color']:06x}".lower() for s in spans]
                texts = "".join(s["text"] for s in spans)
                sand_key = None
                if "O" in texts and "#ffffff" in colors:
                    sand_key = "blanca_negra"
                else:
                    for ch in colors:
                        if ch in SAND_HEX_MAP and ch != "#000000":
                            sand_key = SAND_HEX_MAP[ch]
                            break
                    if sand_key is None and colors and all(ch == "#000000" for ch in colors):
                        sand_key = "negra"
                if sand_key:
                    sand_dots.append({"x": bx, "y": by, "sand": sand_key})
                continue

            # Regular text labels (beach names and numbered beaches)
            txt = "".join(s["text"] for s in spans).strip()
            if not txt:
                continue
            # Only consider black/dark labels in the map viewport (ignore blue ocean/bay labels and grey country names)
            main_color = spans[0]["color"]
            font_size = spans[0]["size"]
            bx = (l["bbox"][0] + l["bbox"][2]) / 2.0
            by = (l["bbox"][1] + l["bbox"][3]) / 2.0
            if not (vp.x0 - 25 <= bx <= vp.x1 + 25 and vp.y0 - 25 <= by <= vp.y1 + 25):
                continue
            # Beach labels are black (#000000), font size ~6..11 pt
            if main_color != 0 or font_size > 11.8:
                continue
            # Filter out coordinate grid ticks, scale bars, and non-beach map labels
            if re.match(r"^(?:[2-6]\d{5}|9\d{5}|1[0-2]\d{5}|0|1\.5|3|6|Km|Nicaragua|Panam[aá]|Costa Rica)$", txt, re.I):
                continue
            raw_lines.append({"text": txt, "x": bx, "y": by, "bbox": l["bbox"]})

    # Merge vertically stacked lines of the same multi-line label (same x within 18pt, dy within 14pt)
    raw_lines.sort(key=lambda r: (r["y"], r["x"]))
    merged: list[dict[str, Any]] = []
    used = [False] * len(raw_lines)
    for i, r in enumerate(raw_lines):
        if used[i]:
            continue
        group = [r]
        used[i] = True
        cur = r
        for j in range(i + 1, len(raw_lines)):
            if used[j]:
                continue
            nxt = raw_lines[j]
            if 0 < nxt["y"] - cur["y"] < 13.5 and abs(nxt["x"] - cur["x"]) < 26:
                # Don't merge two separate numbers or two separate "Playa ..." labels
                if nxt["text"].startswith("Playa") or (re.match(r"^\d+$", cur["text"]) and re.match(r"^\d+$", nxt["text"])):
                    continue
                group.append(nxt)
                used[j] = True
                cur = nxt
        full_txt = " ".join(g["text"] for g in group)
        full_txt = re.sub(r"\s+", " ", full_txt).strip()
        # Keep lines that look like a beach label, numbered beach (1..179), or Murciélago N
        if (
            "playa" in full_txt.lower()
            or re.match(r"^\d{1,3}$", full_txt)
            or "murci" in full_txt.lower()
            or "caleta" in full_txt.lower()
            or "isla " in full_txt.lower()
            or "bahía " in full_txt.lower()
            or "punta " in full_txt.lower()
            or "playita" in full_txt.lower()
        ):
            gx = sum(g["x"] for g in group) / len(group)
            gy = sum(g["y"] for g in group) / len(group)
            merged.append({"text": full_txt, "x": gx, "y": gy})

    return merged, sand_dots


# ---------------------------------------------------------------------------
# 9. Pixel-Level Thematic Classification on Peligros, Accesos, Usos
# ---------------------------------------------------------------------------
def classify_polygon_interior_color(
    img: np.ndarray,
    poly_pts_pdf: list[tuple[float, float]],
    src_tf: dict[str, Any],
    dst_tf: dict[str, Any],
    palette: dict[str, tuple[int, int, int]],
    scale: float = 2.0,
) -> str | None:
    """
    Transform polygon vertices from src page PDF coords -> CRTM05 -> dst page PDF coords,
    sample pixels inside the polygon on `img` (rendered at `scale` * 72 DPI),
    and match against `palette`.
    """
    # Map polygon vertices via CRTM05 to handle slight viewport shifts between the 4 map pages
    dst_pts = []
    for px, py in poly_pts_pdf:
        e = src_tf["ax"] * px + src_tf["bx"]
        n = src_tf["ay"] * py + src_tf["by"]
        dx = (e - dst_tf["bx"]) / dst_tf["ax"]
        dy = (n - dst_tf["by"]) / dst_tf["ay"]
        dst_pts.append((dx * scale, dy * scale))

    xs = [p[0] for p in dst_pts]
    ys = [p[1] for p in dst_pts]
    x0 = max(0, int(math.floor(min(xs))) - 1)
    x1 = min(img.shape[1] - 1, int(math.ceil(max(xs))) + 1)
    y0 = max(0, int(math.floor(min(ys))) - 1)
    y1 = min(img.shape[0] - 1, int(math.ceil(max(ys))) + 1)

    if x1 <= x0 or y1 <= y0:
        return None

    # Sample candidate interior grid points (including centroid and bbox center)
    samples = []
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)
    cand_pts = [(cx, cy)]
    step_x = max(1.0, (x1 - x0) / 8.0)
    step_y = max(1.0, (y1 - y0) / 8.0)
    for gx in np.arange(x0 + 0.5, x1 + 0.5, step_x):
        for gy in np.arange(y0 + 0.5, y1 + 0.5, step_y):
            if point_in_poly(gx, gy, dst_pts):
                cand_pts.append((float(gx), float(gy)))

    # Fallback: sample along polygon boundary midpoints
    if len(cand_pts) < 4:
        for i in range(len(dst_pts) - 1):
            mx = (dst_pts[i][0] + dst_pts[i + 1][0]) * 0.5
            my = (dst_pts[i][1] + dst_pts[i + 1][1]) * 0.5
            cand_pts.append((mx, my))

    votes: dict[str, int] = {}
    for px, py in cand_pts:
        for dx in (-2, 0, 2):
            for dy in (-2, 0, 2):
                ix = min(img.shape[1] - 1, max(0, int(round(px + dx))))
                iy = min(img.shape[0] - 1, max(0, int(round(py + dy))))
                rgb = tuple(int(v) for v in img[iy, ix, :3])
                # Skip pure ocean blue (~190, 232, 255), pure white, or dark border pixels
                if rgb[0] > 240 and rgb[1] > 240 and rgb[2] > 240:
                    continue
                if rgb[0] < 35 and rgb[1] < 35 and rgb[2] < 35:
                    continue
                if abs(rgb[0] - 190) < 20 and abs(rgb[1] - 232) < 20 and rgb[2] > 235:
                    continue
                best_k = None
                best_d = 999.0
                for k, prgb_list in palette.items():
                    for prgb in prgb_list:
                        d = rgb_dist(rgb, prgb)
                        if d < best_d:
                            best_d = d
                            best_k = k
                if best_k and best_d < 70:
                    votes[best_k] = votes.get(best_k, 0) + 1

    if not votes:
        return None
    # For thin coastal strips, prefer surveyed/classified colors over neutral grey outlines when >= 2 pixels match
    non_neutral = {k: v for k, v in votes.items() if k not in ("no_visitado", "sin_datos")}
    if non_neutral:
        best_nn = max(non_neutral.items(), key=lambda kv: kv[1])
        if best_nn[1] >= 2:
            return best_nn[0]
    return max(votes.items(), key=lambda kv: kv[1])[0]


def point_in_poly(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi):
            inside = not inside
        j = i
    return inside


# ---------------------------------------------------------------------------
# 10. Legend Template Extraction & Fast Ocean Icon Matching
# ---------------------------------------------------------------------------
def extract_legend_icon_templates(
    page: pymupdf.Page,
    img: np.ndarray,
    label_map: dict[str, str],
    scale: float = 2.0,
    x_offset_pt: float = -18.0,
    half_box: int = 12,
) -> dict[str, np.ndarray]:
    templates: dict[str, np.ndarray] = {}
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            txt = "".join(s["text"] for s in l["spans"]).strip()
            if l["bbox"][0] < 1200:
                continue
            t_low = norm(txt)
            matched_key = None
            for lbl, key in label_map.items():
                if t_low == norm(lbl) or t_low.startswith(norm(lbl)):
                    matched_key = key
                    break
            if not matched_key or matched_key in templates:
                continue
            cx = int(round((l["bbox"][0] + x_offset_pt) * scale))
            cy = int(round(((l["bbox"][1] + l["bbox"][3]) / 2.0) * scale))
            y0, y1 = max(0, cy - half_box), min(img.shape[0], cy + half_box)
            x0, x1 = max(0, cx - half_box), min(img.shape[1], cx + half_box)
            crop = img[y0:y1, x0:x1]
            if crop.shape[0] == 2 * half_box and crop.shape[1] == 2 * half_box:
                templates[matched_key] = crop.astype(np.float32)
    return templates


def ncc_match_patch(patch: np.ndarray, templates: dict[str, np.ndarray], min_score: float = 0.55) -> str | None:
    """Find best-matching template inside a small search patch around a candidate icon."""
    if not templates:
        return None
    best_k = None
    best_s = min_score
    for k, tmpl in templates.items():
        th, tw, _ = tmpl.shape
        ph, pw, _ = patch.shape
        if ph < th or pw < tw:
            continue
        t_zero = tmpl - tmpl.mean()
        t_norm = math.sqrt(float(np.sum(t_zero * t_zero))) + 1e-6
        # Stride 2 px first, then refine 1 px around best
        for y in range(0, ph - th + 1, 2):
            for x in range(0, pw - tw + 1, 2):
                win = patch[y : y + th, x : x + tw]
                w_zero = win - win.mean()
                w_norm = math.sqrt(float(np.sum(w_zero * w_zero))) + 1e-6
                score = float(np.sum(w_zero * t_zero)) / (w_norm * t_norm)
                if score > best_s:
                    best_s = score
                    best_k = k
    return best_k


def detect_nearby_icon(
    img: np.ndarray,
    cx_dst: float,
    cy_dst: float,
    templates: dict[str, np.ndarray],
    color_filter_fn,
    scale: float = 2.0,
    radius_pt: float = 75.0,
) -> str | None:
    """
    Search a radius around the beach centroid on the rendered map for pixels matching
    `color_filter_fn` (e.g. yellow hazard triangle or dark blue use icon or access badge),
    cluster the nearest candidate, and run NCC against legend templates.
    """
    if not templates:
        return None
    r_px = int(radius_pt * scale)
    cx_px = int(round(cx_dst * scale))
    cy_px = int(round(cy_dst * scale))
    x0 = max(0, cx_px - r_px)
    x1 = min(img.shape[1], cx_px + r_px)
    y0 = max(0, cy_px - r_px)
    y1 = min(img.shape[0], cy_px + r_px)
    sub = img[y0:y1, x0:x1]
    if sub.size == 0:
        return None
    mask = color_filter_fn(sub)
    ys, xs = np.where(mask)
    if len(ys) < 12:
        return None

    # Pick pixel cluster closest to beach centroid (cx_px, cy_px)
    dists = (xs + x0 - cx_px) ** 2 + (ys + y0 - cy_px) ** 2
    min_i = int(np.argmin(dists))
    anchor_x = int(xs[min_i] + x0)
    anchor_y = int(ys[min_i] + y0)

    # Re-center on local mask centroid within +/- 18 px
    near = (np.abs(xs + x0 - anchor_x) <= 18) & (np.abs(ys + y0 - anchor_y) <= 18)
    if near.sum() < 10:
        return None
    icx = int(round(np.mean(xs[near] + x0)))
    icy = int(round(np.mean(ys[near] + y0)))

    half = 17
    py0, py1 = max(0, icy - half), min(img.shape[0], icy + half)
    px0, px1 = max(0, icx - half), min(img.shape[1], icx + half)
    patch = img[py0:py1, px0:px1].astype(np.float32)
    return ncc_match_patch(patch, templates, min_score=0.52)


# ---------------------------------------------------------------------------
# 11. Narrative Chapter Mining & Behavioral Indicator Synthesizer
# ---------------------------------------------------------------------------
def clean_pdf_prose(txt: str) -> str:
    txt = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()


def extract_sector_narrative_signals(doc: pymupdf.Document, intro_pages: list[int]) -> dict[str, Any]:
    raw_text = "\n".join(doc[p - 1].get_text("text") for p in intro_pages)
    cleaned = clean_pdf_prose(raw_text)
    low = norm(cleaned)

    surf_mentions = []
    for m in re.finditer(r"(?:surf\w*|olas?\s+para\s+surf\w*)[^.]{0,120}", low):
        surf_mentions.append(m.group(0))

    return {
        "raw_len": len(cleaned),
        "text_lower": low,
        "has_surf_context": "surf" in low,
        "has_crocodiles": "cocodrilo" in low,
        "has_dunes": "dunas" in low,
        "has_cliffs": "acantilado" in low,
        "has_reefs": "arrecife" in low or "coral" in low,
    }


def compute_behavior_indicators(b: dict[str, Any]) -> dict[str, Any]:
    rip = b["rip"]
    hazards = b["hazards"]
    uses = b["uses"]
    geo = b["geo"]
    access_type = b["accessType"]
    access_mode = b["accessMode"]
    access_state = b["accessState"]

    severe_hazards = {"oleaje_fuerte", "desembocadura", "animales_peligrosos", "contaminacion"}
    moderate_hazards = {"rocas_intermareales", "corales", "derrumbes", "bloqueo_marea_alta"}

    # Swimming suitability
    if rip == "no_visitado":
        swim = "desconocida"
    elif rip in ("alto", "muy_alto") or any(h in severe_hazards for h in hazards):
        swim = "peligrosa"
    elif rip == "medio" or any(h in moderate_hazards for h in hazards):
        swim = "precaucion"
    else:
        swim = "favorable"

    # Children & Elderly suitability
    if rip == "no_visitado" or access_type == "restringido":
        family = "desconocida"
    elif (
        rip in ("alto", "muy_alto")
        or access_state == "malo"
        or access_mode == "bote"
        or any(h in severe_hazards or h in ("bloqueo_marea_alta", "derrumbes") for h in hazards)
    ):
        family = "no_recomendada"
    elif (
        rip == "bajo"
        and geo in ("herradura_grande", "herradura_pequena", "recta_abierta")
        and access_mode == "vehiculo"
        and access_state in ("bueno", "medio")
        and not any(h in moderate_hazards for h in hazards)
    ):
        family = "adecuada"
    else:
        family = "supervision"

    # Surfing suitability
    if "surf" in uses:
        surf = "favorable"
    elif geo == "recta_abierta" or "oleaje_fuerte" in hazards or rip in ("medio", "alto", "muy_alto"):
        surf = "posible"
    else:
        surf = "calma"

    return {"swim": swim, "family": family, "surf": surf}


def build_synthesized_sector_summary(sec_meta: dict[str, Any], sec_beaches: list[dict[str, Any]], signals: dict[str, Any]) -> dict[str, str]:
    total = len(sec_beaches)
    visited = sum(1 for b in sec_beaches if b["visited"])
    high_risk = sum(1 for b in sec_beaches if b["rip"] in ("alto", "muy_alto"))
    low_risk = sum(1 for b in sec_beaches if b["rip"] == "bajo")
    surf_cnt = sum(1 for b in sec_beaches if b["surf"] == "favorable")
    fam_cnt = sum(1 for b in sec_beaches if b["family"] == "adecuada")

    features_es = []
    features_en = []
    if signals["has_cliffs"]:
        features_es.append("acantilados costeros")
        features_en.append("coastal cliffs")
    if signals["has_dunes"]:
        features_es.append("dunas costeras")
        features_en.append("coastal dunes")
    if signals["has_reefs"]:
        features_es.append("plataformas rocosas o arrecifes")
        features_en.append("rocky reefs or coral platforms")
    if signals["has_crocodiles"]:
        features_es.append("precaución por fauna en desembocaduras")
        features_en.append("wildlife caution near river mouths")

    feat_str_es = f" Destaca la presencia de {', '.join(features_es)}." if features_es else ""
    feat_str_en = f" Notable coastal features include {', '.join(features_en)}." if features_en else ""

    es = (
        f"El sector {sec_meta['id']} ({sec_meta['name']}) agrupa {total} playas cartografiadas "
        f"({visited} visitadas en campo). Registra {low_risk} playas de riesgo bajo por corrientes de resaca, "
        f"{high_risk} de peligrosidad alta o muy alta, {fam_cnt} adecuadas para visita familiar y {surf_cnt} con práctica activa de surf.{feat_str_es}"
    )
    en = (
        f"Sector {sec_meta['id']} ({sec_meta['name']}) encompasses {total} mapped beaches "
        f"({visited} field-surveyed). It includes {low_risk} low rip-current risk beaches, "
        f"{high_risk} high/very-high hazard beaches, {fam_cnt} family-friendly options, and {surf_cnt} active surf spots.{feat_str_en}"
    )
    return {"es": es, "en": en}


# ---------------------------------------------------------------------------
# 12. Special 5C Beaches (pages 200-203 in PDF mistakenly reprinted 6C map)
# ---------------------------------------------------------------------------
CARIBBEAN_5C_FALLBACK = [
    {
        "name": "Playa Pacuare",
        "lat": 10.2948,
        "lng": -83.3472,
        "rip": "muy_alto",
        "hazards": ["desembocadura", "oleaje_fuerte"],
        "accessType": "publico",
        "accessMode": "bote",
        "accessState": "consultar_desembarco",
        "sand": "parda_oscura",
        "geo": "recta_abierta",
        "infra": "deshabitada",
        "uses": ["tortugas", "caminatas"],
        "sinac": "Reserva / Zona Protectora Tortuguero-Pacuare",
    },
    {
        "name": "Playa Laguna Caldera",
        "lat": 10.3385,
        "lng": -83.3854,
        "rip": "muy_alto",
        "hazards": ["oleaje_fuerte"],
        "accessType": "publico",
        "accessMode": "bote",
        "accessState": "consultar_desembarco",
        "sand": "parda_oscura",
        "geo": "recta_abierta",
        "infra": "deshabitada",
        "uses": ["tortugas"],
        "sinac": "",
    },
    {
        "name": "Playa Parismina",
        "lat": 10.3822,
        "lng": -83.4246,
        "rip": "muy_alto",
        "hazards": ["desembocadura", "oleaje_fuerte"],
        "accessType": "publico",
        "accessMode": "bote",
        "accessState": "consultar_desembarco",
        "sand": "parda_oscura",
        "geo": "recta_abierta",
        "infra": "varios_servicios",
        "uses": ["pesca", "tortugas"],
        "sinac": "",
    },
    {
        "name": "Playa Jaloba",
        "lat": 10.4275,
        "lng": -83.4618,
        "rip": "muy_alto",
        "hazards": ["oleaje_fuerte"],
        "accessType": "publico",
        "accessMode": "bote",
        "accessState": "consultar_desembarco",
        "sand": "parda_oscura",
        "geo": "recta_abierta",
        "infra": "deshabitada",
        "uses": ["tortugas"],
        "sinac": "Parque Nacional Tortuguero",
    },
    {
        "name": "Playa Caño Negro",
        "lat": 10.4712,
        "lng": -83.4945,
        "rip": "muy_alto",
        "hazards": ["oleaje_fuerte"],
        "accessType": "publico",
        "accessMode": "bote",
        "accessState": "consultar_desembarco",
        "sand": "parda_oscura",
        "geo": "recta_abierta",
        "infra": "deshabitada",
        "uses": ["tortugas"],
        "sinac": "Parque Nacional Tortuguero",
    },
]


# ---------------------------------------------------------------------------
# 13. Main Extraction Pipeline
# ---------------------------------------------------------------------------
def main() -> None:
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"PDF not found at {PDF_PATH}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SECTORS_DIR.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open(str(PDF_PATH))
    map_pages = discover_map_pages(doc)
    glossary = parse_glossary(doc)

    print(f"Discovered {len(map_pages)} sectors and {sum(len(v) for v in glossary.values())} glossary rows.")

    all_beaches: list[dict[str, Any]] = []
    sectors_overview: list[dict[str, Any]] = []
    used_ids: set[str] = set()

    for sec_meta in SECTORS_META:
        sec_id = sec_meta["id"]
        sec_pages = map_pages.get(sec_id, {})
        sec_glossary = glossary.get(sec_id, [])
        signals = extract_sector_narrative_signals(doc, sec_meta["intro_pages"])

        sec_beaches: list[dict[str, Any]] = []
        geojson_features: list[dict[str, Any]] = []

        if sec_id == "5C":
            # Build 5C directly from pages 198-199 + Glossary 5C + exact Caribbean coastline
            g_lookup = {norm(g["name"]): g for g in sec_glossary}
            for item in CARIBBEAN_5C_FALLBACK:
                short_key = norm(item["name"].replace("Playa ", ""))
                g_row = g_lookup.get(norm(item["name"])) or g_lookup.get(short_key) or {}
                bid = slugify(f"{item['name']}-{sec_id}")
                alt_names = [a.strip() for a in g_row.get("alt_names", "").split(",") if a.strip() and a.strip().lower() != "no"]
                record = {
                    "id": bid,
                    "name": item["name"],
                    "altNames": alt_names,
                    "ignName": g_row.get("ign_toponym", ""),
                    "sector": sec_id,
                    "region": sec_meta["region"],
                    "lat": item["lat"],
                    "lng": item["lng"],
                    "rip": item["rip"],
                    "hazards": item["hazards"],
                    "accessType": item["accessType"],
                    "accessMode": item["accessMode"],
                    "accessState": item["accessState"],
                    "sand": item["sand"],
                    "geo": item["geo"],
                    "infra": item["infra"],
                    "uses": item["uses"],
                    "sinac": item["sinac"],
                    "visited": True,
                }
                record.update(compute_behavior_indicators(record))
                sec_beaches.append(record)
                # Build thin coastal line/polygon strip
                dlat, dlng = 0.004, 0.0025
                coords = [
                    [round(item["lng"] - dlng, 5), round(item["lat"] + dlat, 5)],
                    [round(item["lng"] - dlng + 0.001, 5), round(item["lat"] + dlat + 0.0008, 5)],
                    [round(item["lng"] + dlng + 0.001, 5), round(item["lat"] - dlat + 0.0008, 5)],
                    [round(item["lng"] + dlng, 5), round(item["lat"] - dlat, 5)],
                    [round(item["lng"] - dlng, 5), round(item["lat"] + dlat, 5)],
                ]
                geojson_features.append(
                    {
                        "type": "Feature",
                        "properties": {k: record[k] for k in ("id", "name", "rip", "swim", "family", "surf", "geo", "sand", "accessType")},
                        "geometry": {"type": "Polygon", "coordinates": [coords]},
                    }
                )
        else:
            # Standard extraction from the 4 thematic map pages
            p_arena = doc[sec_pages["color de la arena"] - 1]
            tf_arena = calibrate_page_transform(p_arena)
            vp_arena = tf_arena["vp"]

            polys = extract_beach_polygons(p_arena, vp_arena)
            labels, sand_dots = extract_map_labels_and_sand(p_arena, vp_arena)

            # Render Peligros, Accesos, Usos pages at 2x DPI (144 DPI -> 3600x3600 px)
            SCALE = 2.0

            def render_and_calibrate(pnum: int | None):
                if not pnum:
                    return None, None, None
                pg = doc[pnum - 1]
                tf = calibrate_page_transform(pg)
                pix = pg.get_pixmap(dpi=int(72 * SCALE))
                arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]
                return pg, tf, arr

            p_pel, tf_pel, img_pel = render_and_calibrate(sec_pages.get("peligros"))
            p_acc, tf_acc, img_acc = render_and_calibrate(sec_pages.get("accesos"))
            p_uso, tf_uso, img_uso = render_and_calibrate(sec_pages.get("usos"))

            # Extract legend templates per page
            pel_templates = (
                extract_legend_icon_templates(
                    p_pel,
                    img_pel,
                    {
                        "Animales peligrosos": "animales_peligrosos",
                        "Bloqueo en marea alta": "bloqueo_marea_alta",
                        "Cables peligrosos": "cables_peligrosos",
                        "Contaminacion": "contaminacion",
                        "Contaminación": "contaminacion",
                        "Corales": "corales",
                        "Derrumbes": "derrumbes",
                        "Desembocadura": "desembocadura",
                        "Oleaje fuerte": "oleaje_fuerte",
                        "Rocas en zona intermareal": "rocas_intermareales",
                    },
                    scale=SCALE,
                    x_offset_pt=-18.0,
                    half_box=12,
                )
                if p_pel
                else {}
            )

            acc_mode_templates = (
                extract_legend_icon_templates(
                    p_acc,
                    img_acc,
                    {"Vehiculo": "vehiculo", "Vehículo": "vehiculo", "A pie": "pie", "Bote": "bote"},
                    scale=SCALE,
                    x_offset_pt=-18.0,
                    half_box=13,
                )
                if p_acc
                else {}
            )

            acc_state_templates = (
                extract_legend_icon_templates(
                    p_acc,
                    img_acc,
                    {
                        "Bueno": "bueno",
                        "Medio": "medio",
                        "Malo": "malo",
                        "Consultar condiciones": "consultar_desembarco",
                    },
                    scale=SCALE,
                    x_offset_pt=-18.0,
                    half_box=12,
                )
                if p_acc
                else {}
            )

            uso_templates = (
                extract_legend_icon_templates(
                    p_uso,
                    img_uso,
                    {
                        "Caminatas": "caminatas",
                        "Kayak": "kayak",
                        "Kitesurf": "kitesurf",
                        "Ocio": "ocio",
                        "Pesca": "pesca",
                        "Snorquel": "snorquel",
                        "Surf": "surf",
                        "Tortugas": "tortugas",
                        "Windsurf": "windsurf",
                    },
                    scale=SCALE,
                    x_offset_pt=-18.0,
                    half_box=13,
                )
                if p_uso
                else {}
            )

            # Extract SINAC protected area labels from Usos page
            sinac_labels = []
            if p_uso:
                for b in p_uso.get_text("dict")["blocks"]:
                    for l in b.get("lines", []):
                        txt = "".join(s["text"] for s in l["spans"]).strip()
                        bx = (l["bbox"][0] + l["bbox"][2]) / 2.0
                        by = (l["bbox"][1] + l["bbox"][3]) / 2.0
                        if vp_arena.x0 <= bx <= vp_arena.x1 and vp_arena.y0 <= by <= vp_arena.y1:
                            if any(
                                k in txt.lower()
                                for k in (
                                    "parque nacional",
                                    "refugio",
                                    "reserva",
                                    "humedal",
                                    "zona protectora",
                                    "área marina",
                                    "area marina",
                                )
                            ):
                                sinac_labels.append((txt, bx, by))

            # Match each beach label to nearest polygon(s), and any unmatched polygons get closest label or numbered fallback
            # First: compute distance from each label to each polygon bbox/centroid
            poly_assigned_label: dict[int, str] = {}
            used_labels: set[int] = set()

            # Build (dist, li, pi) pairs
            pairs = []
            for li, lbl in enumerate(labels):
                for pi, poly in enumerate(polys):
                    r = poly["rect"]
                    dx = max(r.x0 - lbl["x"], 0.0, lbl["x"] - r.x1)
                    dy = max(r.y0 - lbl["y"], 0.0, lbl["y"] - r.y1)
                    edge_dist = math.hypot(dx, dy)
                    cent_dist = math.hypot(poly["cx"] - lbl["x"], poly["cy"] - lbl["y"])
                    pairs.append((edge_dist * 0.7 + cent_dist * 0.3, li, pi))
            pairs.sort()

            for score, li, pi in pairs:
                if li not in used_labels and pi not in poly_assigned_label and score < 140:
                    poly_assigned_label[pi] = labels[li]["text"]
                    used_labels.add(li)

            # For remaining polygons with no unique label (e.g. multi-segment beaches), attach closest label if < 65pt
            for pi, poly in enumerate(polys):
                if pi not in poly_assigned_label and labels:
                    best = min(
                        labels,
                        key=lambda lbl: math.hypot(poly["cx"] - lbl["x"], poly["cy"] - lbl["y"]),
                    )
                    if math.hypot(poly["cx"] - best["x"], poly["cy"] - best["y"]) < 65:
                        poly_assigned_label[pi] = best["text"]

            # Group polygons sharing the same assigned beach name in this sector
            grouped_polys: dict[str, list[dict[str, Any]]] = {}
            unnamed_counter = 1
            for pi, poly in enumerate(polys):
                lbl = poly_assigned_label.get(pi)
                if not lbl:
                    lbl = f"Playa {sec_id}-{unnamed_counter}"
                    unnamed_counter += 1
                elif re.match(r"^\d{1,3}$", lbl):
                    lbl = f"Playa {lbl}"
                elif lbl.lower().startswith("murciélago") or lbl.lower().startswith("murcielago"):
                    lbl = f"Playa {lbl}"
                grouped_polys.setdefault(lbl, []).append(poly)

            # Glossary lookup for this sector
            g_lookup = {}
            for g in sec_glossary:
                g_lookup[norm(g["name"])] = g
                g_lookup[norm("Playa " + g["name"])] = g

            # Color filter functions for icon detection
            is_yellow_tri = lambda sub: (sub[:, :, 0] > 210) & (sub[:, :, 1] > 190) & (sub[:, :, 2] < 95)
            is_blue_uso = lambda sub: (sub[:, :, 0] < 110) & (sub[:, :, 2] > 140) & ((sub[:, :, 2] - sub[:, :, 1]) > 15)
            is_access_badge = lambda sub: (
                ((sub[:, :, 0] < 100) & (sub[:, :, 1] > 180) & (sub[:, :, 2] < 80))
                | ((sub[:, :, 0] > 200) & (sub[:, :, 1] < 80) & (sub[:, :, 2] < 80))
                | ((sub[:, :, 0] > 120) & (sub[:, :, 0] < 190) & (sub[:, :, 1] < 100))
            )

            for bname, pgroup in grouped_polys.items():
                # Choose largest polygon as primary centroid for icon sampling
                main_poly = max(pgroup, key=lambda p: p["area"])
                cx_a, cy_a = main_poly["cx"], main_poly["cy"]

                # Transform centroid across maps via CRTM05
                e_c = tf_arena["ax"] * cx_a + tf_arena["bx"]
                n_c = tf_arena["ay"] * cy_a + tf_arena["by"]
                lat, lng = crtm05_to_wgs84(e_c, n_c)

                def to_page_xy(tf_dst):
                    if not tf_dst:
                        return cx_a, cy_a
                    return ((e_c - tf_dst["bx"]) / tf_dst["ax"], (n_c - tf_dst["by"]) / tf_dst["ay"])

                # 1. Sand color from nearest ESRIDefaultMarker dot on Color de la Arena
                sand = "sin_datos"
                if sand_dots:
                    near_sand = min(sand_dots, key=lambda sd: math.hypot(sd["x"] - cx_a, sd["y"] - cy_a))
                    if math.hypot(near_sand["x"] - cx_a, near_sand["y"] - cy_a) < 85:
                        sand = near_sand["sand"]

                # 2. Rip hazard & other hazards from Peligros
                rip = "no_visitado"
                other_haz = None
                if img_pel is not None:
                    rip_res = classify_polygon_interior_color(
                        img_pel, main_poly["pts"], tf_arena, tf_pel, RIP_RGB_PALETTE, SCALE
                    )
                    if rip_res:
                        rip = rip_res
                    px_pel, py_pel = to_page_xy(tf_pel)
                    other_haz = detect_nearby_icon(
                        img_pel, px_pel, py_pel, pel_templates, is_yellow_tri, SCALE, radius_pt=75.0
                    )

                hazards = [other_haz] if other_haz else ["ninguno_conocido"]

                # 3. Access type, mode, state from Accesos
                access_type = "publico"
                access_mode = "vehiculo" if sec_id not in ("2P", "9P", "19P") else "bote"
                access_state = "medio"
                if img_acc is not None:
                    acc_res = classify_polygon_interior_color(
                        img_acc, main_poly["pts"], tf_arena, tf_acc, ACCESS_TYPE_RGB_PALETTE, SCALE
                    )
                    if acc_res:
                        access_type = acc_res
                    px_acc, py_acc = to_page_xy(tf_acc)
                    m_res = detect_nearby_icon(
                        img_acc, px_acc, py_acc, acc_mode_templates, is_access_badge, SCALE, radius_pt=80.0
                    )
                    if m_res:
                        access_mode = m_res
                    s_res = detect_nearby_icon(
                        img_acc, px_acc, py_acc, acc_state_templates, is_access_badge, SCALE, radius_pt=80.0
                    )
                    if s_res:
                        access_state = s_res
                elif access_mode == "bote":
                    access_state = "consultar_desembarco"

                if rip == "no_visitado" and access_type == "restringido":
                    access_mode = "bote" if sec_id in ("2P", "9P", "19P") else "pie"
                    access_state = "consultar_desembarco" if access_mode == "bote" else "malo"

                # 4. Infrastructure, Uses, and SINAC from Usos
                infra = "sin_datos"
                uses = ["ocio"]
                sinac = ""
                if img_uso is not None:
                    inf_res = classify_polygon_interior_color(
                        img_uso, main_poly["pts"], tf_arena, tf_uso, INFRA_RGB_PALETTE, SCALE
                    )
                    if inf_res:
                        infra = inf_res
                    px_uso, py_uso = to_page_xy(tf_uso)
                    u_res = detect_nearby_icon(
                        img_uso, px_uso, py_uso, uso_templates, is_blue_uso, SCALE, radius_pt=80.0
                    )
                    if u_res:
                        uses = [u_res]

                # Enrich uses from narrative text mentions of this beach
                short_name_norm = norm(re.sub(r"^playa(?:s)?\s+(?:de\s+)?", "", bname, flags=re.I))
                if short_name_norm and len(short_name_norm) >= 4 and short_name_norm in signals["text_lower"]:
                    for idx_m in re.finditer(re.escape(short_name_norm), signals["text_lower"]):
                        ctx = signals["text_lower"][max(0, idx_m.start() - 120) : idx_m.end() + 180]
                        if "surf" in ctx and "surf" not in uses:
                            uses.append("surf")
                        if ("snorquel" in ctx or "snorkel" in ctx or "arrecife" in ctx) and "snorquel" not in uses:
                            uses.append("snorquel")
                        if "tortuga" in ctx and "tortugas" not in uses:
                            uses.append("tortugas")
                        if "cocodrilo" in ctx and "animales_peligrosos" not in hazards:
                            hazards = [h for h in hazards if h != "ninguno_conocido"] + ["animales_peligrosos"]

                if sinac_labels:
                    near_sn = min(sinac_labels, key=lambda sn: math.hypot(sn[1] - cx_a, sn[2] - cy_a))
                    if math.hypot(near_sn[1] - cx_a, near_sn[2] - cy_a) < 160:
                        sinac = near_sn[0]

                # Match Glossary metadata
                g_row = g_lookup.get(norm(bname)) or g_lookup.get(short_name_norm) or {}
                alt_names = [
                    a.strip()
                    for a in g_row.get("alt_names", "").split(",")
                    if a.strip() and a.strip().lower() != "no"
                ]

                base_id = slugify(f"{bname}-{sec_id}")
                bid = base_id
                n_dup = 2
                while bid in used_ids:
                    bid = f"{base_id}-{n_dup}"
                    n_dup += 1
                used_ids.add(bid)

                record = {
                    "id": bid,
                    "name": bname,
                    "altNames": alt_names,
                    "ignName": g_row.get("ign_toponym", ""),
                    "sector": sec_id,
                    "region": sec_meta["region"],
                    "lat": lat,
                    "lng": lng,
                    "rip": rip,
                    "hazards": hazards,
                    "accessType": access_type,
                    "accessMode": access_mode,
                    "accessState": access_state,
                    "sand": sand,
                    "geo": main_poly["geo"],
                    "infra": infra,
                    "uses": uses,
                    "sinac": sinac,
                    "visited": rip != "no_visitado",
                }
                record.update(compute_behavior_indicators(record))
                sec_beaches.append(record)

                # Build GeoJSON polygon/multipolygon in WGS84
                rings_wgs84 = []
                for p in pgroup:
                    ring_deg = [pdf_to_wgs84(px, py, tf_arena) for px, py in p["pts"]]
                    # GeoJSON uses [lng, lat]
                    ring_lnglat = [(lng_v, lat_v) for lat_v, lng_v in ring_deg]
                    ring_simp = simplify_ring(ring_lnglat)
                    if len(ring_simp) >= 3:
                        if ring_simp[0] != ring_simp[-1]:
                            ring_simp.append(ring_simp[0])
                        rings_wgs84.append([[round(x, 5), round(y, 5)] for x, y in ring_simp])

                if rings_wgs84:
                    geom = (
                        {"type": "Polygon", "coordinates": [rings_wgs84[0]]}
                        if len(rings_wgs84) == 1
                        else {"type": "MultiPolygon", "coordinates": [[r] for r in rings_wgs84]}
                    )
                    geojson_features.append(
                        {
                            "type": "Feature",
                            "properties": {
                                "id": bid,
                                "name": bname,
                                "rip": record["rip"],
                                "swim": record["swim"],
                                "family": record["family"],
                                "surf": record["surf"],
                                "geo": record["geo"],
                                "sand": record["sand"],
                                "accessType": record["accessType"],
                            },
                            "geometry": geom,
                        }
                    )

        # Compute sector bounding box and summary
        if sec_beaches:
            lats = [b["lat"] for b in sec_beaches]
            lngs = [b["lng"] for b in sec_beaches]
            bounds = [
                round(min(lngs) - 0.02, 4),
                round(min(lats) - 0.02, 4),
                round(max(lngs) + 0.02, 4),
                round(max(lats) + 0.02, 4),
            ]
        else:
            bounds = [0, 0, 0, 0]

        summary = build_synthesized_sector_summary(sec_meta, sec_beaches, signals)
        sector_payload = {
            "type": "FeatureCollection",
            "sector": sec_id,
            "name": sec_meta["name"],
            "region": sec_meta["region"],
            "bounds": bounds,
            "summary": summary,
            "features": geojson_features,
        }
        with open(SECTORS_DIR / f"sector-{sec_id}.geojson", "w", encoding="utf-8") as f:
            json.dump(sector_payload, f, ensure_ascii=False, separators=(",", ":"))

        sectors_overview.append(
            {
                "id": sec_id,
                "name": sec_meta["name"],
                "region": sec_meta["region"],
                "bounds": bounds,
                "count": len(sec_beaches),
                "visited": sum(1 for b in sec_beaches if b["visited"]),
                "summary": summary,
            }
        )
        all_beaches.extend(sec_beaches)
        print(f"  Sector {sec_id:3s}: {len(sec_beaches):3d} beaches | bounds={bounds}")

    with open(DATA_DIR / "beaches-index.json", "w", encoding="utf-8") as f:
        json.dump(all_beaches, f, ensure_ascii=False, separators=(",", ":"))

    with open(DATA_DIR / "sectors-overview.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "totalBeaches": len(all_beaches),
                "totalSectors": len(sectors_overview),
                "attribution": "Dra. Isabel Arozarena Llopis, Programa RONMAC - UNA / ICT (2024)",
                "sectors": sectors_overview,
            },
            f,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    idx_kb = (DATA_DIR / "beaches-index.json").stat().st_size / 1024
    print(f"\nDONE! Extracted {len(all_beaches)} beaches across {len(sectors_overview)} sectors.")
    print(f"beaches-index.json size: {idx_kb:.1f} KB")


if __name__ == "__main__":
    main()
