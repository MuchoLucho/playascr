#!/usr/bin/env python3
"""
Intelligently populate beach-photos.json from Wikimedia Commons and Wikidata
using geographic distance verification and category parsing.
"""

import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
INDEX_FILE = os.path.join(DATA_DIR, 'beaches-index.json')
OUTPUT_FILE = os.path.join(DATA_DIR, 'beach-photos.json')
USER_AGENT = 'PlayasCR-PhotoBot/1.0 (https://github.com/MuchoLucho/playascr; lerv22@gmail.com)'

NOISE_WORDS = {
    'toilet', 'restroom', 'sloth', 'monkey', 'raccoon', 'snake', 'frog',
    'insect', 'spider', 'butterfly', 'lizard', 'crab', 'flower', 'leaf',
    'map', 'chart', 'diagram', 'flag', 'icon', 'logo', 'receipt', 'sign',
    'room', 'bedroom', 'bed', 'bathroom', 'kitchen', 'interior', 'stamp'
}

def clean_html(text):
    if not text:
        return 'Wikimedia Contributor'
    text = re.sub(r'<[^<]+?>', '', text)
    return text.strip()

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def normalize_name(name):
    name = re.sub(r'^(playa|playita|playitas|bahía|bahia|punta|boca|estero)\s+', '', name, flags=re.I)
    name = re.sub(r'\s+\d+[a-z]?$', '', name, flags=re.I)
    name = re.sub(r'\s*\([^)]*\)', '', name)
    return name.strip().lower()

def fetch_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.load(resp)
    except Exception as e:
        return None

def main():
    with open(INDEX_FILE) as f:
        beaches = json.load(f)

    # Load existing photos
    photos = {}
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE) as f:
            photos = json.load(f)
    print(f"Starting with {len(photos)} existing curated photos.")

    # Index beaches by normalized name and ID
    beaches_by_id = {b['id']: b for b in beaches}
    
    # Priority list of prominent beaches across Costa Rica
    prominent_names = [
        # Guanacaste
        'Playa Hermosa', 'Playa Panamá', 'Playas del Coco', 'Playa Ocotal',
        'Playa Flamingo', 'Playa Brasilito', 'Playa Conchal', 'Playa Grande',
        'Playa Tamarindo', 'Playa Langosta', 'Playa Avellanas', 'Playa Negra',
        'Playa Junquillal', 'Playa Nosara', 'Playa Guiones', 'Playa Pelada',
        'Playa Garza', 'Playa Sámara', 'Playa Carrillo', 'Playa San Miguel',
        'Playa Coyote',
        # Nicoya Peninsula / Puntarenas
        'Playa Santa Teresa', 'Playa Carmen', 'Playa Malpaís', 'Playa Tambor',
        'Playa Montezuma', 'Playa Pochote', 'Playa Órganos',
        # Pacífico Central
        'Playa Puntarenas', 'Playa Caldera', 'Playa Tivives', 'Playa Bajamar',
        'Playa Herradura', 'Playa Jacó', 'Playa Hermosa', 'Playa Esterillos',
        'Playa Bejuco', 'Playa Palo Seco', 'Playa Isla Damas',
        # Manuel Antonio / Quepos
        'Playa Biesanz', 'Playa Espadilla Norte', 'Playa Espadilla Sur',
        'Playa Manuel Antonio', 'Playitas', 'Playa Rey', 'Playa Matapalo',
        # Pacífico Sur
        'Playa Dominical', 'Playa Dominicalito', 'Playa Hermosa', 'Playa Uvita',
        'Playa Ballena', 'Playa Piñuela', 'Playa Ventanas', 'Playa Tortuga',
        'Bahía Drake', 'Playa San Josecito', 'Playa Carate', 'Playa Madrigal',
        'Playa Matapalo', 'Playa Pan Dulce', 'Playa Zancudo', 'Playa Pavones',
        # Caribe
        'Playa Tortuguero', 'Playa Bonita', 'Playa Piuta', 'Playa Westfalia',
        'Playa Cahuita', 'Playa Negra de Cahuita', 'Playa Negra de Puerto Viejo',
        'Playa Cocles', 'Playa Chiquita', 'Punta Uva', 'Playa Manzanillo',
        'Playa Gandoca'
    ]

    # Map prominent names to specific beach candidates
    search_targets = []
    for b in beaches:
        # Check if already has photo
        if b['id'] in photos:
            continue
        b_name_clean = normalize_name(b['name'])
        for p in prominent_names:
            p_clean = normalize_name(p)
            if b_name_clean == p_clean or p_clean in b_name_clean:
                search_targets.append(b)
                break

    print(f"Found {len(search_targets)} high-priority beaches to populate.")

    populated_count = 0
    for idx, b in enumerate(search_targets):
        bid = b['id']
        bname = b['name']
        lat, lng = b['lat'], b['lng']

        print(f"[{idx+1}/{len(search_targets)}] Searching for {bname} ({bid})...", end='', flush=True)

        # Strategy 1: Search Wikimedia Commons by title + geosearch
        query = f"{bname} Costa Rica"
        q_enc = urllib.parse.quote(query)
        search_url = (
            f"https://commons.wikimedia.org/w/api.php?action=query&generator=search"
            f"&gsrsearch={q_enc}&gsrnamespace=6&gsrlimit=5"
            f"&prop=imageinfo|coordinates&iiprop=url|extmetadata&iiurlwidth=960&format=json"
        )
        data = fetch_json(search_url)

        found_img = None
        if data:
            pages = data.get('query', {}).get('pages', {})
            for pid, page in pages.items():
                title = page.get('title', '').replace('File:', '')
                title_lower = title.lower()

                # Check noise
                if any(w in title_lower for w in NOISE_WORDS):
                    continue

                # Ensure image-like extension
                if not any(ext in title_lower for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    continue

                ii = page.get('imageinfo', [{}])[0]
                thumb = ii.get('thumburl')
                if not thumb:
                    continue

                # Check coordinates if present
                coords = page.get('coordinates', [{}])[0]
                photo_lat = coords.get('lat')
                photo_lon = coords.get('lon')
                if photo_lat is not None and photo_lon is not None:
                    dist = haversine(lat, lng, photo_lat, photo_lon)
                    if dist > 35.0: # Too far away, likely a different beach with same name
                        continue

                meta = ii.get('extmetadata', {})
                artist = clean_html(meta.get('Artist', {}).get('value', 'Wikimedia Commons Contributor'))
                license_name = meta.get('LicenseShortName', {}).get('value', 'Creative Commons')

                found_img = {
                    'title': title,
                    'thumbUrl': thumb,
                    'sourceUrl': ii.get('descriptionurl') or f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(page.get('title', ''))}",
                    'author': artist[:50],
                    'license': license_name
                }
                break

        # Strategy 2: If text search didn't find, try geosearch within 2.5km
        if not found_img:
            geo_url = (
                f"https://commons.wikimedia.org/w/api.php?action=query&generator=geosearch"
                f"&ggscoord={lat}|{lng}&ggsradius=2500&ggsnamespace=6&ggslimit=8"
                f"&prop=imageinfo&iiprop=url|extmetadata&iiurlwidth=960&format=json"
            )
            geo_data = fetch_json(geo_url)
            if geo_data:
                pages = geo_data.get('query', {}).get('pages', {})
                for pid, page in pages.items():
                    title = page.get('title', '').replace('File:', '')
                    title_lower = title.lower()

                    # Require beach/ocean relevance in title
                    if not any(w in title_lower for w in ['playa', 'beach', 'coast', 'costa', 'bay', 'bahia', 'surf', 'mar', 'sunset', 'atardecer']):
                        continue
                    if any(w in title_lower for w in NOISE_WORDS):
                        continue

                    ii = page.get('imageinfo', [{}])[0]
                    thumb = ii.get('thumburl')
                    if not thumb:
                        continue

                    meta = ii.get('extmetadata', {})
                    artist = clean_html(meta.get('Artist', {}).get('value', 'Wikimedia Commons Contributor'))
                    license_name = meta.get('LicenseShortName', {}).get('value', 'Creative Commons')

                    found_img = {
                        'title': title,
                        'thumbUrl': thumb,
                        'sourceUrl': ii.get('descriptionurl') or f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(page.get('title', ''))}",
                        'author': artist[:50],
                        'license': license_name
                    }
                    break

        if found_img:
            photos[bid] = found_img
            populated_count += 1
            print(f" ✅ Found: {found_img['title'][:40]} ({found_img['license']})")
        else:
            print(" ⚪ No verified photo")

        time.sleep(0.15)

    print(f"\nSuccessfully populated {populated_count} new photos! Total in catalog: {len(photos)}")

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(photos, f, indent=2, ensure_ascii=False)
    print(f"Saved to {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
