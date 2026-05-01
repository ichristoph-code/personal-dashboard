"""macOS AddressBook contact resolution via direct SQLite access.

Scans all AddressBook databases (main + iCloud/Exchange sources) to build
a fast phone/email → contact name lookup.  Thumbnails are fetched on-demand
for specific contacts to avoid loading hundreds of images into memory.

Also provides full contact list with birthdays for the Contacts tab and
birthday cards.

Requires Full Disk Access for the process (Terminal.app has it).
Name map cached to disk for 30 minutes as a fallback.
"""

import base64
import json
import re
import sqlite3
import subprocess

from . import atomic_write_json
import time
from datetime import date
from pathlib import Path

_AB_BASE = Path.home() / "Library" / "Application Support" / "AddressBook"
_AB_CONTAINER = (
    Path.home() / "Library" / "Containers" / "com.apple.AddressBook"
    / "Data" / "Library" / "Application Support" / "AddressBook"
)
_CACHE_FILE = Path(__file__).parent.parent / ".contacts_cache.json"
_CACHE_TTL = 30 * 60  # 30 minutes

# In-memory caches
_name_map = None       # { normalized_key: {"name": str, "pk": int, "db": str} }
_thumb_cache = {}      # { normalized_key: str|None (data URI) }
_loaded_at = 0


def _normalize_phone(phone):
    """Strip to digits, return last 10 (US numbers without country code)."""
    digits = re.sub(r'\D', '', phone or '')
    if len(digits) > 10 and digits.startswith('1'):
        digits = digits[1:]  # strip US country code
    return digits[-10:] if len(digits) >= 7 else digits


def _normalize_email(email):
    """Lowercase and strip whitespace."""
    return (email or '').strip().lower()


def _get_db_paths():
    """Collect all AddressBook database paths (classic + container locations)."""
    seen = set()
    paths = []

    def _add(p):
        rp = str(p.resolve())
        if rp not in seen and p.exists():
            seen.add(rp)
            paths.append(p)

    for base in (_AB_BASE, _AB_CONTAINER):
        _add(base / "AddressBook-v22.abcddb")
        for src_db in sorted(base.glob("Sources/*/AddressBook-v22.abcddb")):
            _add(src_db)

    return paths


def _scan_databases():
    """Scan all AddressBook databases — names only (fast, no blobs)."""
    name_map = {}

    for db_path in _get_db_paths():
        db_str = str(db_path)
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True,
                                   check_same_thread=False)
        except Exception:
            continue

        try:
            # Phone number → contact name + pk
            rows = conn.execute("""
                SELECT r.Z_PK, r.ZFIRSTNAME, r.ZLASTNAME, r.ZORGANIZATION,
                       p.ZFULLNUMBER
                FROM ZABCDRECORD r
                JOIN ZABCDPHONENUMBER p ON r.Z_PK = p.ZOWNER
                WHERE p.ZFULLNUMBER IS NOT NULL
                  AND (r.ZFIRSTNAME IS NOT NULL OR r.ZLASTNAME IS NOT NULL
                       OR r.ZORGANIZATION IS NOT NULL)
            """).fetchall()

            for pk, first, last, org, phone in rows:
                name = _build_name(first, last, org)
                if not name:
                    continue
                key = "phone:" + _normalize_phone(phone)
                if key and key != "phone:" and key not in name_map:
                    name_map[key] = {"name": name, "pk": pk, "db": db_str}

            # Email → contact name + pk
            rows = conn.execute("""
                SELECT r.Z_PK, r.ZFIRSTNAME, r.ZLASTNAME, r.ZORGANIZATION,
                       e.ZADDRESS
                FROM ZABCDRECORD r
                JOIN ZABCDEMAILADDRESS e ON r.Z_PK = e.ZOWNER
                WHERE e.ZADDRESS IS NOT NULL
                  AND (r.ZFIRSTNAME IS NOT NULL OR r.ZLASTNAME IS NOT NULL
                       OR r.ZORGANIZATION IS NOT NULL)
            """).fetchall()

            for pk, first, last, org, email in rows:
                name = _build_name(first, last, org)
                if not name:
                    continue
                key = "email:" + _normalize_email(email)
                if key and key != "email:" and key not in name_map:
                    name_map[key] = {"name": name, "pk": pk, "db": db_str}

        except Exception as e:
            print(f"  Contacts: error reading {db_path.parent.name}: {e}")
        finally:
            conn.close()

    return name_map


def _build_name(first, last, org):
    """Build a display name from first/last/org fields."""
    parts = []
    if first:
        parts.append(first)
    if last:
        parts.append(last)
    if parts:
        return " ".join(parts)
    if org:
        return org
    return None


def _save_cache(name_map):
    """Save name-only map to disk as fallback cache."""
    slim = {k: v["name"] for k, v in name_map.items()}
    atomic_write_json(_CACHE_FILE, {"ts": time.time(), "map": slim})


def _load_cache_fallback():
    """Load name-only cache from disk — used ONLY if DB scan fails."""
    try:
        if _CACHE_FILE.exists():
            with open(_CACHE_FILE) as f:
                data = json.load(f)
            if time.time() - data.get("ts", 0) < _CACHE_TTL:
                return {k: {"name": v, "pk": None, "db": None}
                        for k, v in data["map"].items()}
    except Exception:
        pass
    return None


def _get_name_map():
    """Get the name map, always doing a fresh DB scan if possible."""
    global _name_map, _loaded_at

    if _name_map and (time.time() - _loaded_at < _CACHE_TTL):
        return _name_map

    # Always try a fresh scan first (fast — no blob reads)
    try:
        print("  Contacts: scanning AddressBook databases...")
        _name_map = _scan_databases()
        _loaded_at = time.time()
        _save_cache(_name_map)
        phones = sum(1 for k in _name_map if k.startswith("phone:"))
        emails = sum(1 for k in _name_map if k.startswith("email:"))
        print(f"  Contacts: indexed {phones} phone numbers, {emails} emails")
        return _name_map
    except Exception as e:
        print(f"  Contacts: scan failed ({e}), trying disk cache...")

    # Fallback to disk cache
    cached = _load_cache_fallback()
    if cached:
        _name_map = cached
        _loaded_at = time.time()
        print(f"  Contacts: loaded {len(cached)} entries from fallback cache")
        return _name_map

    _name_map = {}
    _loaded_at = time.time()
    return _name_map


def _fetch_thumbnail(pk, db_path):
    """Fetch a single contact's thumbnail from the database on-demand."""
    if pk is None or db_path is None:
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True,
                               check_same_thread=False)
        row = conn.execute(
            "SELECT ZTHUMBNAILIMAGEDATA FROM ZABCDRECORD WHERE Z_PK = ?",
            (pk,)
        ).fetchone()
        conn.close()
        if row and row[0]:
            b64 = base64.b64encode(row[0]).decode('ascii')
            return f"data:image/jpeg;base64,{b64}"
    except Exception:
        pass
    return None


def _lookup_key(identifier):
    """Return the normalized cache key for an identifier."""
    if not identifier:
        return None

    nmap = _get_name_map()

    # Try as phone
    phone_key = "phone:" + _normalize_phone(identifier)
    if phone_key in nmap:
        return phone_key

    # Try as email
    email_key = "email:" + _normalize_email(identifier)
    if email_key in nmap:
        return email_key

    return None


def resolve_contact(identifier):
    """Resolve a phone number or email to (display_name, thumbnail_data_uri).

    Returns (name, thumb) where thumb may be None.
    Falls back to the raw identifier if not found.
    """
    if not identifier:
        return identifier, None

    key = _lookup_key(identifier)
    if key is None:
        return identifier, None

    entry = _get_name_map()[key]

    # Fetch thumbnail on-demand (cached in memory)
    if key not in _thumb_cache:
        _thumb_cache[key] = _fetch_thumbnail(entry.get("pk"), entry.get("db"))

    return entry["name"], _thumb_cache.get(key)


def resolve_contacts_bulk(identifiers):
    """Resolve a list of identifiers at once.

    Returns { identifier: { "name": str, "thumb": str|None } }
    """
    # Ensure name map is loaded
    _get_name_map()

    results = {}
    for ident in identifiers:
        if not ident:
            continue
        name, thumb = resolve_contact(ident)
        results[ident] = {"name": name, "thumb": thumb}

    return results


# ── Full contact list + birthdays ──

_FULL_CACHE_FILE = Path(__file__).parent.parent / ".contacts_full_cache.json"
_FULL_CACHE_TTL = 30 * 60  # 30 minutes
_full_contacts = None
_full_loaded_at = 0


_JXA_SCRIPT = r"""
var app = Application('Contacts');
var people = app.people;
var n = people.length;

// Bulk-fetch scalar properties — one bridge call each (fast, no per-person loops)
var ids        = people.id();
var names      = people.name();
var firsts     = people.firstName();
var lasts      = people.lastName();
var orgs       = people.organization();
var jobtitles  = people.jobTitle();
var depts      = people.department();
var nicknames  = people.nickname();
var notes_arr  = people.note();
var birthdays  = people.birthDate();

var result = [];
for (var i = 0; i < n; i++) {
    var nm = String(names[i] || '').trim();
    if (!nm) continue;

    var obj = {
        contact_id: String(ids[i] || ''),
        name:       nm,
        first:      String(firsts[i]    || '').trim(),
        last:       String(lasts[i]     || '').trim(),
        org:        String(orgs[i]      || '').trim(),
        jobtitle:   String(jobtitles[i] || '').trim(),
        department: String(depts[i]     || '').trim(),
        nickname:   String(nicknames[i] || '').trim(),
        note:       String(notes_arr[i] || '').trim().slice(0, 2000),
        birthday: null, birthday_year: null
    };

    try {
        var bd = birthdays[i];
        if (bd && typeof bd.getMonth === 'function') {
            var m = bd.getMonth() + 1, d = bd.getDate(), y = bd.getFullYear();
            obj.birthday = String(m).padStart(2,'0') + '-' + String(d).padStart(2,'0');
            if (y > 1900 && y < 2100) obj.birthday_year = y;
        }
    } catch(e) {}

    result.push(obj);
}
JSON.stringify(result);
"""

# JXA script for fetching multi-value details for a single contact by UUID.
# __CONTACT_ID__ is replaced at call time with the actual UUID.
_JXA_DETAIL_SCRIPT = r"""
function cleanLabel(lbl, fallback) {
    var s = String(lbl || '').trim();
    // Convert _$!<Mobile>!$_ style to "mobile"
    var m = s.match(/<([^>]+)>/);
    if (m) return m[1].charAt(0).toUpperCase() + m[1].slice(1).toLowerCase();
    return s || fallback;
}

var app = Application('Contacts');
var matches = app.people.whose({id: '__CONTACT_ID__'})();
if (!matches.length) {
    JSON.stringify({});
} else {
    var p = matches[0];
    var obj = {phones: [], emails: [], addresses: [], urls: [], ims: [], related: []};

    try {
        var ph = p.phones();
        for (var j = 0; j < ph.length; j++)
            obj.phones.push({label: cleanLabel(ph[j].label(), 'Phone'), number: String(ph[j].value() || '')});
    } catch(e) {}

    try {
        var em = p.emails();
        for (var j = 0; j < em.length; j++)
            obj.emails.push({label: cleanLabel(em[j].label(), 'Email'), address: String(em[j].value() || '')});
    } catch(e) {}

    try {
        var ad = p.addresses();
        for (var j = 0; j < ad.length; j++)
            obj.addresses.push({
                label:   cleanLabel(ad[j].label(), 'Address'),
                street:  String(ad[j].street()  || ''),
                city:    String(ad[j].city()    || ''),
                state:   String(ad[j].state()   || ''),
                zip:     String(ad[j].zip()     || ''),
                country: String(ad[j].country() || '')
            });
    } catch(e) {}

    try {
        var ur = p.urls();
        for (var j = 0; j < ur.length; j++)
            obj.urls.push({label: cleanLabel(ur[j].label(), 'URL'), url: String(ur[j].value() || '')});
    } catch(e) {}

    try {
        var im = p.IMs();
        for (var j = 0; j < im.length; j++)
            obj.ims.push({label: cleanLabel(im[j].label(), 'IM'), username: String(im[j].value() || '')});
    } catch(e) {}

    try {
        var rn = p.relatedNames();
        for (var j = 0; j < rn.length; j++)
            obj.related.push({label: cleanLabel(rn[j].label(), 'Related'), name: String(rn[j].value() || '')});
    } catch(e) {}

    JSON.stringify(obj);
}
"""


def _scan_via_jxa():
    """Query the Contacts app via JXA — returns scalar data for all contacts.

    Multi-value fields (phones, emails, addresses, urls) are NOT fetched here;
    they are loaded on-demand via get_contact_detail().
    """
    r = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", _JXA_SCRIPT],
        capture_output=True, text=True, timeout=45,
    )
    if r.returncode != 0:
        raise RuntimeError(f"JXA contacts error: {r.stderr.strip()[:300]}")
    return json.loads(r.stdout.strip())


def _fetch_thumbnail_by_uuid(uuid):
    """Look up a contact thumbnail from AddressBook SQLite by Contacts.app UUID."""
    if not uuid:
        return None
    for db_path in _get_db_paths():
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True,
                                   check_same_thread=False)
            try:
                row = conn.execute(
                    "SELECT Z_PK FROM ZABCDRECORD WHERE ZUNIQUEID = ?", (uuid,)
                ).fetchone()
            finally:
                conn.close()
            if row:
                thumb = _fetch_thumbnail(row[0], str(db_path))
                if thumb:
                    return thumb
        except Exception:
            pass
    return None


def get_contact_detail(contact_id):
    """Fetch multi-value details (phones, emails, addresses, urls) for one contact.

    Uses a targeted JXA call that typically completes in < 1 second.
    Also fetches the contact thumbnail from SQLite.
    Returns a dict with keys: phones, emails, addresses, urls, ims, related, thumb.
    Returns {} on error.
    """
    if not contact_id:
        return {}
    # IDs are in format "UUID:ABPerson" — strip anything that could break a JS string
    safe_id = re.sub(r'[^A-Za-z0-9\-:]', '', contact_id)
    script = _JXA_DETAIL_SCRIPT.replace('__CONTACT_ID__', safe_id)
    try:
        r = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            return {}
        text = r.stdout.strip()
        if not text:
            return {}
        result = json.loads(text) or {}
        # Fetch thumbnail from SQLite — ZUNIQUEID stores the full "UUID:ABPerson" value
        result['thumb'] = _fetch_thumbnail_by_uuid(safe_id)
        return result
    except Exception:
        return {}


def _build_thumb_map():
    """Build phone→thumbnail map from local SQLite databases (fast, no API)."""
    thumb_map = {}
    for db_path in _get_db_paths():
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True,
                                   check_same_thread=False)
            try:
                rows = conn.execute("""
                    SELECT r.ZTHUMBNAILIMAGEDATA, p.ZFULLNUMBER
                    FROM ZABCDRECORD r
                    JOIN ZABCDPHONENUMBER p ON r.Z_PK = p.ZOWNER
                    WHERE r.ZTHUMBNAILIMAGEDATA IS NOT NULL
                      AND p.ZFULLNUMBER IS NOT NULL
                """).fetchall()
            finally:
                conn.close()
            for thumb_data, phone in rows:
                nkey = _normalize_phone(phone)
                if nkey and nkey not in thumb_map and thumb_data:
                    b64 = base64.b64encode(thumb_data).decode('ascii')
                    thumb_map[nkey] = f"data:image/jpeg;base64,{b64}"
        except Exception:
            pass
    return thumb_map


def _scan_full_contacts():
    """Get all contacts via JXA (includes iCloud), merge SQLite thumbnails.

    Multi-value fields (phones, emails, addresses, urls) are intentionally
    omitted here — they are fetched on-demand via get_contact_detail().
    """
    jxa_contacts = _scan_via_jxa()

    result = []
    for idx, c in enumerate(jxa_contacts):
        result.append({
            "id": idx,
            "contact_id": c.get("contact_id", ""),
            "name": c["name"],
            "first": c.get("first", ""),
            "last": c.get("last", ""),
            "org": c.get("org", ""),
            "jobtitle": c.get("jobtitle", ""),
            "department": c.get("department", ""),
            "nickname": c.get("nickname", ""),
            "birthday": c.get("birthday"),
            "birthday_year": c.get("birthday_year"),
            "note": c.get("note", ""),
            "thumb": None,  # thumbnails not fetched in bulk; matched from SQLite below
            "phones": [],
            "emails": [],
            "addresses": [],
            "urls": [],
            "ims": [],
            "related": [],
        })

    result.sort(key=lambda c: c["name"].lower())
    return result


def _sqlite_scan_fallback():
    """Minimal SQLite scan — used only when JXA is unavailable."""
    contacts = {}
    for db_path in _get_db_paths():
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True,
                                   check_same_thread=False)
            rows = conn.execute("""
                SELECT Z_PK, ZFIRSTNAME, ZLASTNAME, ZORGANIZATION,
                       ZJOBTITLE, ZDEPARTMENT, ZNICKNAME,
                       ZBIRTHDAY, ZNOTE, ZTHUMBNAILIMAGEDATA
                FROM ZABCDRECORD
                WHERE ZFIRSTNAME IS NOT NULL OR ZLASTNAME IS NOT NULL
                      OR ZORGANIZATION IS NOT NULL
            """).fetchall()
            for pk, first, last, org, jobtitle, dept, nickname, bday_ts, note, thumb_data in rows:
                name = _build_name(first, last, org)
                if not name or (db_path, pk) in contacts:
                    continue
                thumb = None
                if thumb_data:
                    thumb = "data:image/jpeg;base64," + base64.b64encode(thumb_data).decode('ascii')
                # Parse Core Data birthday timestamp
                birthday_str = birthday_year = None
                if bday_ts is not None:
                    try:
                        from datetime import datetime
                        dt = datetime.fromtimestamp(978307200 + bday_ts)
                        if dt.year > 1900:
                            birthday_str = f"{dt.month:02d}-{dt.day:02d}"
                            birthday_year = dt.year if dt.year < 2100 else None
                    except Exception:
                        pass
                contacts[(str(db_path), pk)] = {
                    "name": name, "first": first or "", "last": last or "",
                    "org": org or "", "jobtitle": (jobtitle or "").strip(),
                    "department": (dept or "").strip(), "nickname": (nickname or "").strip(),
                    "birthday": birthday_str, "birthday_year": birthday_year,
                    "note": (note or "").strip(), "thumb": thumb,
                    "phones": [], "emails": [], "addresses": [],
                    "urls": [], "ims": [], "related": [],
                }
            # Phones
            for owner_pk, number, label in conn.execute(
                "SELECT ZOWNER, ZFULLNUMBER, ZLABEL FROM ZABCDPHONENUMBER WHERE ZFULLNUMBER IS NOT NULL"
            ).fetchall():
                c = contacts.get((str(db_path), owner_pk))
                if c:
                    c["phones"].append({"number": number, "label": re.sub(r'[_$!<>]', '', label or '').strip() or "Phone"})
            # Emails
            for owner_pk, address, label in conn.execute(
                "SELECT ZOWNER, ZADDRESS, ZLABEL FROM ZABCDEMAILADDRESS WHERE ZADDRESS IS NOT NULL"
            ).fetchall():
                c = contacts.get((str(db_path), owner_pk))
                if c:
                    c["emails"].append({"address": address, "label": re.sub(r'[_$!<>]', '', label or '').strip() or "Email"})
            conn.close()
        except Exception:
            pass
    result = list(contacts.values())
    for idx, c in enumerate(result):
        c["id"] = idx
    result.sort(key=lambda c: c["name"].lower())
    return result


def get_all_contacts():
    """Get full contact list with phones, emails, birthdays, thumbnails.

    Returns a list of contact dicts, sorted by name.
    Cached in memory for 30 minutes, with disk fallback.
    """
    global _full_contacts, _full_loaded_at

    now = time.time()
    if _full_contacts is not None and (now - _full_loaded_at < _FULL_CACHE_TTL):
        return _full_contacts

    # Try disk cache first (avoids slow JXA scan on restart within TTL)
    try:
        if _FULL_CACHE_FILE.exists():
            cached = json.loads(_FULL_CACHE_FILE.read_text())
            if now - cached.get("ts", 0) < _FULL_CACHE_TTL:
                _full_contacts = cached["contacts"]
                _full_loaded_at = now
                print(f"  Contacts: loaded {len(_full_contacts)} from disk cache")
                return _full_contacts
    except Exception:
        pass

    try:
        print("  Contacts: querying Contacts app via JXA...")
        _full_contacts = _scan_full_contacts()
        _full_loaded_at = now
        bday_count = sum(1 for c in _full_contacts if c["birthday"])
        print(f"  Contacts: loaded {len(_full_contacts)} contacts "
              f"({bday_count} with birthdays)")
        # Save to disk cache (strips thumbnail data to keep file small)
        try:
            slim = [{k: v for k, v in c.items() if k != "thumb"}
                    for c in _full_contacts]
            atomic_write_json(_FULL_CACHE_FILE, {"ts": now, "contacts": slim})
        except Exception:
            pass
        return _full_contacts
    except Exception as e:
        print(f"  Contacts: JXA scan failed ({e})")

    # Fall back to stale disk cache if available
    try:
        if _FULL_CACHE_FILE.exists():
            cached = json.loads(_FULL_CACHE_FILE.read_text())
            _full_contacts = cached.get("contacts", [])
            _full_loaded_at = now
            print(f"  Contacts: using stale cache ({len(_full_contacts)} contacts)")
            return _full_contacts
    except Exception:
        pass

    # Last resort: SQLite-only scan (local contacts only)
    try:
        print("  Contacts: falling back to SQLite scan (local contacts only)...")
        _full_contacts = _sqlite_scan_fallback()
        _full_loaded_at = now
        print(f"  Contacts: SQLite fallback loaded {len(_full_contacts)} contacts")
        return _full_contacts
    except Exception as e2:
        print(f"  Contacts: SQLite fallback also failed ({e2})")

    _full_contacts = []
    _full_loaded_at = now
    return _full_contacts


def get_upcoming_birthdays(days=30):
    """Get contacts with birthdays in the next N days.

    Returns a sorted list of dicts:
      [{name, birthday_display, days_until, age, thumb}, ...]
    """
    contacts = get_all_contacts()
    today = date.today()
    results = []

    for c in contacts:
        if not c["birthday"]:
            continue

        try:
            month, day = map(int, c["birthday"].split("-"))
            # Build this year's birthday
            try:
                bday_this_year = date(today.year, month, day)
            except ValueError:
                # Feb 29 in a non-leap year → use Feb 28
                bday_this_year = date(today.year, month, 28)

            diff = (bday_this_year - today).days

            if diff < 0:
                # Already passed this year — check next year
                try:
                    bday_next_year = date(today.year + 1, month, day)
                except ValueError:
                    bday_next_year = date(today.year + 1, month, 28)
                diff = (bday_next_year - today).days

            if diff > days:
                continue

            # Calculate age (if birth year known)
            age = None
            if c["birthday_year"]:
                age = today.year - c["birthday_year"]
                if diff > 0:
                    # Birthday hasn't happened yet this year
                    pass  # age is correct (they'll turn this age)
                elif diff == 0:
                    pass  # turning this age today
                # Note: diff can't be negative here (we already handled that)

            # Format display date
            import calendar
            month_name = calendar.month_abbr[month]
            birthday_display = f"{month_name} {day}"

            results.append({
                "name": c["name"],
                "birthday_display": birthday_display,
                "days_until": diff,
                "age": age,
                "thumb": c["thumb"],
            })

        except (ValueError, TypeError):
            continue

    results.sort(key=lambda x: x["days_until"])
    return results
