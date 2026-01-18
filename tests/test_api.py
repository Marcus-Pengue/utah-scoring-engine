"""
API Test Harness
=================
Validates all endpoints work correctly.
Run: python tests/test_api.py
"""

import requests
import json
import time
import sys

# Config
BASE_URL = "https://utah-pollinator-path.onrender.com"
ADMIN_KEY = "8a56becc816d0f70f64bde106f5a8c13"
USER_TOKEN = None

# Test results
results = {"passed": 0, "failed": 0, "skipped": 0, "errors": []}


def test(name, condition, details=""):
    if condition:
        results["passed"] += 1
        print(f"  ✅ {name}")
    else:
        results["failed"] += 1
        results["errors"].append(f"{name}: {details}")
        print(f"  ❌ {name} - {details}")


def skip(name, reason=""):
    results["skipped"] += 1
    print(f"  ⏭️  {name} (skipped: {reason})")


def get(endpoint, headers=None, params=None):
    try:
        r = requests.get(f"{BASE_URL}{endpoint}", headers=headers, params=params, timeout=30)
        return r.status_code, r.json() if r.headers.get('content-type', '').startswith('application/json') else r.text
    except Exception as e:
        return 0, str(e)


def post(endpoint, data=None, headers=None):
    try:
        h = {"Content-Type": "application/json"}
        if headers:
            h.update(headers)
        r = requests.post(f"{BASE_URL}{endpoint}", json=data, headers=h, timeout=30)
        return r.status_code, r.json() if r.headers.get('content-type', '').startswith('application/json') else r.text
    except Exception as e:
        return 0, str(e)


def admin_headers():
    return {"X-Admin-Key": ADMIN_KEY}


def test_health():
    print("\n📋 Health Check")
    status, data = get("/health")
    test("GET /health returns 200", status == 200)


def test_public_endpoints():
    print("\n📋 Public Endpoints")
    status, data = get("/api/species/plants")
    test("GET /api/species/plants", status == 200)
    status, data = get("/api/scoring/methodology")
    test("GET /api/scoring/methodology", status == 200)
    status, data = get("/api/badges")
    test("GET /api/badges", status == 200)
    status, data = get("/api/challenges")
    test("GET /api/challenges", status == 200)
    status, data = get("/api/observations")
    test("GET /api/observations", status == 200)
    status, data = get("/api/stats")
    test("GET /api/stats", status == 200)


def test_scoring_endpoints():
    print("\n📋 Scoring Endpoints")
    payload = {
        "lat": 40.6655, "lng": -111.8965,
        "plants": [{"species": "Showy Milkweed", "count": 3, "is_native": True, "is_milkweed": True}],
        "flower_coverage_pct": 20, "has_bare_ground": True, "bare_ground_sqft": 25
    }
    status, data = post("/api/v2/score", payload)
    test("POST /api/v2/score", status == 200)
    test("Score has score field", isinstance(data, dict) and "score" in data)


def test_admin_endpoints():
    print("\n📋 Admin Endpoints")
    status, data = get("/api/admin/export")
    test("Admin export without key fails", status == 403)
    status, data = get("/api/admin/verify", headers=admin_headers())
    test("Admin verify with key succeeds", status == 200)
    status, data = get("/api/admin/export", headers=admin_headers())
    test("GET /api/admin/export", status == 200)


def test_jobs_endpoints():
    print("\n📋 Jobs Endpoints")
    status, data = get("/api/jobs/list")
    test("GET /api/jobs/list", status == 200)
    status, data = get("/api/jobs/history")
    test("GET /api/jobs/history", status == 200)


def test_stats_endpoints():
    print("\n📋 Stats Endpoints")
    status, data = get("/api/stats/growth?days=7")
    test("GET /api/stats/growth", status == 200)
    status, data = get("/api/stats/dashboard")
    test("GET /api/stats/dashboard", status == 200)


def test_events_endpoints():
    print("\n📋 Events Endpoints")
    status, data = get("/api/events/types")
    test("GET /api/events/types", status == 200)
    status, data = get("/api/events/daily?days=7")
    test("GET /api/events/daily", status == 200)


def test_government_endpoints():
    print("\n📋 Government Endpoints")
    status, data = get("/api/gov/overview")
    test("GET /api/gov/overview", status == 200)
    test("Overview has participants", isinstance(data, dict) and "participants" in data)
    status, data = get("/api/gov/wards")
    test("GET /api/gov/wards", status == 200)
    status, data = get("/api/gov/priority-areas")
    test("GET /api/gov/priority-areas", status == 200)
    status, data = get("/api/gov/geojson/participation")
    test("GET /api/gov/geojson/participation", status == 200)
    status, data = get("/api/gov/report/council", headers=admin_headers())
    test("GET /api/gov/report/council", status == 200)


def test_external_data_endpoints():
    print("\n📋 External Data Endpoints")
    status, data = get("/api/external/sources")
    test("GET /api/external/sources", status == 200)
    status, data = get("/api/external/species?lat=40.666&lng=-111.897")
    test("GET /api/external/species", status == 200)
    status, data = get("/api/external/enrich?lat=40.666&lng=-111.897")
    test("GET /api/external/enrich", status == 200)


def test_unified_map_endpoints():
    print("\n📋 Unified Map Endpoints")
    status, data = get("/api/map/layers")
    test("GET /api/map/layers", status == 200)
    status, data = get("/api/map/unified")
    test("GET /api/map/unified", status == 200)
    test("Unified has features", isinstance(data, dict) and "features" in data)
    status, data = get("/api/map/bloom-calendar")
    test("GET /api/map/bloom-calendar", status == 200)


def test_enhanced_map_endpoints():
    print("\n📋 Enhanced Map Endpoints")
    status, data = get("/api/map/monarch-status")
    test("GET /api/map/monarch-status", status == 200)
    status, data = get("/api/map/frost-dates?lat=40.666&lng=-111.897")
    test("GET /api/map/frost-dates", status == 200)
    status, data = get("/api/map/waystations")
    test("GET /api/map/waystations", status == 200)
    status, data = get("/api/map/bee-cities")
    test("GET /api/map/bee-cities", status == 200)
    status, data = get("/api/map/corridors")
    test("GET /api/map/corridors", status == 200)
    status, data = get("/api/map/parks")
    test("GET /api/map/parks", status == 200)
    status, data = get("/api/map/elevation?lat=40.666&lng=-111.897")
    test("GET /api/map/elevation", status == 200)
    status, data = get("/api/map/enhanced?lat=40.666&lng=-111.897")
    test("GET /api/map/enhanced", status == 200)


def test_wildlife_endpoints():
    print("\n📋 Wildlife Data Endpoints")
    status, data = get("/api/wildlife/sources")
    test("GET /api/wildlife/sources", status == 200)
    test("Sources has sources array", isinstance(data, dict) and "sources" in data)
    status, data = get("/api/wildlife/motus")
    test("GET /api/wildlife/motus", status == 200)
    test("Motus has stations", isinstance(data, dict) and "stations" in data)
    status, data = get("/api/wildlife/motus/tracks")
    test("GET /api/wildlife/motus/tracks", status == 200)
    status, data = get("/api/wildlife/inaturalist?lat=40.666&lng=-111.897&radius=10")
    test("GET /api/wildlife/inaturalist", status == 200)
    test("iNaturalist has observations", isinstance(data, dict) and "observations" in data)
    status, data = get("/api/wildlife/gbif?lat=40.666&lng=-111.897")
    test("GET /api/wildlife/gbif", status == 200)
    status, data = get("/api/wildlife/unified?lat=40.666&lng=-111.897&radius=10")
    test("GET /api/wildlife/unified", status == 200)
    test("Unified has features", isinstance(data, dict) and "features" in data)


def print_summary():
    total = results["passed"] + results["failed"] + results["skipped"]
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS")
    print("=" * 50)
    print(f"  ✅ Passed:  {results['passed']}")
    print(f"  ❌ Failed:  {results['failed']}")
    print(f"  ⏭️  Skipped: {results['skipped']}")
    print(f"  📋 Total:   {total}")
    if results["errors"]:
        print("\n❌ FAILURES:")
        for err in results["errors"]:
            print(f"  - {err}")
    return results["failed"] == 0


if __name__ == "__main__":
    print("=" * 50)
    print("🧪 Utah Pollinator Path - API Test Suite")
    print(f"🌐 Testing: {BASE_URL}")
    print("=" * 50)
    
    start = time.time()
    
    test_health()
    test_public_endpoints()
    test_scoring_endpoints()
    test_admin_endpoints()
    test_jobs_endpoints()
    test_stats_endpoints()
    test_events_endpoints()
    test_government_endpoints()
    test_external_data_endpoints()
    test_unified_map_endpoints()
    test_enhanced_map_endpoints()
    test_wildlife_endpoints()
    
    elapsed = time.time() - start
    print(f"\n⏱️  Completed in {elapsed:.1f}s")
    
    success = print_summary()
    sys.exit(0 if success else 1)
