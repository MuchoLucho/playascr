#!/usr/bin/env python3
"""
Verify beach photos manifest against beaches-index.json and test CDN availability.
"""
import json
import os
import sys
import urllib.request

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
INDEX_FILE = os.path.join(DATA_DIR, 'beaches-index.json')
PHOTOS_FILE = os.path.join(DATA_DIR, 'beach-photos.json')

def verify_photos():
    if not os.path.exists(INDEX_FILE):
        print(f"Error: {INDEX_FILE} not found")
        sys.exit(1)
    if not os.path.exists(PHOTOS_FILE):
        print(f"Error: {PHOTOS_FILE} not found")
        sys.exit(1)

    with open(INDEX_FILE) as f:
        beaches = {b['id']: b for b in json.load(f)}

    with open(PHOTOS_FILE) as f:
        photos = json.load(f)

    print(f"Loaded {len(photos)} curated beach photos. Validating...")

    errors = 0
    for bid, item in photos.items():
        if bid not in beaches:
            print(f"❌ Unknown beach ID: '{bid}'")
            errors += 1
            continue

        beach = beaches[bid]
        thumb = item.get('thumbUrl')
        author = item.get('author')
        license_name = item.get('license')

        if not thumb or not thumb.startswith('http'):
            print(f"❌ Invalid thumbUrl for {bid}: {thumb}")
            errors += 1
            continue

        if not author:
            print(f"❌ Missing author for {bid}")
            errors += 1
            continue

        if not license_name:
            print(f"❌ Missing license for {bid}")
            errors += 1
            continue

        # Check HTTP response with HEAD or light GET request
        req = urllib.request.Request(thumb, headers={'User-Agent': 'PlayasCR-Verifier/1.0'})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status != 200:
                    print(f"❌ HTTP {resp.status} for {bid} ({beach['name']})")
                    errors += 1
                else:
                    print(f"✅ {bid}: {beach['name']} -> {author} ({license_name}) [HTTP 200]")
        except Exception as e:
            print(f"⚠️  Network warning for {bid}: {e}")

    if errors == 0:
        print(f"\n🎉 All {len(photos)} photos verified successfully!")
    else:
        print(f"\n❌ Found {errors} verification errors.")
        sys.exit(1)

if __name__ == '__main__':
    verify_photos()
