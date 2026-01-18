"""
Utah Pollinator Path - Supabase Database Client
================================================
Uses REST API directly - no extra dependencies.
"""

import aiohttp
import ssl
import certifi
from typing import Dict, List, Optional

# Supabase credentials
SUPABASE_URL = "https://gqexnqmqwhpcrleksrkb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdxZXhucW1xd2hwY3JsZWtzcmtiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjYyNzg1OTEsImV4cCI6MjA4MTg1NDU5MX0.glfXIcO8ofdyWUC9nlf9Y-6EzF30BXlxtIY8NXVEORM"

TABLE = "leaderboard_entries"


def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _ssl_context():
    return ssl.create_default_context(cafile=certifi.where())


async def add_entry(
    lat: float,
    lng: float,
    grid_hash: str,
    score: float,
    grade: str,
    display_name: str = "Anonymous Gardener",
    city: Optional[str] = None,
    county: Optional[str] = None,
    state: str = "Utah",
    zip_code: Optional[str] = None,
    ward: Optional[str] = None,
    identity_level: str = "seedling",
) -> Dict:
    """Add or update a leaderboard entry."""
    
    data = {
        "lat": lat,
        "lng": lng,
        "grid_hash": grid_hash,
        "score": score,
        "grade": grade,
        "display_name": display_name,
        "city": city,
        "county": county,
        "state": state,
        "zip_code": zip_code,
        "ward": ward,
        "identity_level": identity_level,
    }
    
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}"
    headers = _headers()
    headers["Prefer"] = "resolution=merge-duplicates,return=representation"
    
    connector = aiohttp.TCPConnector(ssl=_ssl_context())
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.post(url, json=data, headers=headers) as resp:
            if resp.status in (200, 201):
                result = await resp.json()
                return result[0] if result else {}
            else:
                error = await resp.text()
                return {"error": error, "status": resp.status}


async def get_leaderboard(
    level: str = "state",
    filter_value: Optional[str] = None,
    limit: int = 20,
) -> Dict:
    """Get leaderboard for a specific level."""
    
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?select=*&order=score.desc&limit={limit}"
    
    # Apply filter
    if level == "state":
        url += "&state=eq.Utah"
    elif level == "county" and filter_value:
        url += f"&county=eq.{filter_value}"
    elif level == "city" and filter_value:
        url += f"&city=eq.{filter_value}"
    elif level == "zip" and filter_value:
        url += f"&zip_code=eq.{filter_value}"
    elif level == "ward" and filter_value:
        url += f"&ward=eq.{filter_value}"
    
    connector = aiohttp.TCPConnector(ssl=_ssl_context())
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.get(url, headers=_headers()) as resp:
            entries = await resp.json() if resp.status == 200 else []
    
    # Add ranks
    for i, entry in enumerate(entries):
        entry["rank"] = i + 1
    
    # Stats
    scores = [e["score"] for e in entries]
    
    return {
        "level": level,
        "filter": filter_value,
        "total_participants": len(entries),
        "entries": entries,
        "stats": {
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "top_score": max(scores) if scores else 0,
            "pioneers": len([e for e in entries if e.get("identity_level") == "pioneer"]),
            "champions": len([e for e in entries if e.get("identity_level") == "migration_champion"]),
        },
    }


async def get_user_rankings(grid_hash: str) -> Dict:
    """Get all rankings for a user."""
    
    # Get user
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?grid_hash=eq.{grid_hash}"
    
    connector = aiohttp.TCPConnector(ssl=_ssl_context())
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.get(url, headers=_headers()) as resp:
            users = await resp.json() if resp.status == 200 else []
    
    if not users:
        return {"error": "User not found"}
    
    user = users[0]
    rankings = {}
    
    # Get state ranking
    state_url = f"{SUPABASE_URL}/rest/v1/{TABLE}?select=grid_hash,score&state=eq.Utah&order=score.desc"
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=_ssl_context())) as session:
        async with session.get(state_url, headers=_headers()) as resp:
            state_entries = await resp.json() if resp.status == 200 else []
    
    state_rank = next((i+1 for i, e in enumerate(state_entries) if e["grid_hash"] == grid_hash), None)
    rankings["state"] = {"rank": state_rank, "total": len(state_entries), "label": "Utah"}
    
    # City ranking
    if user.get("city"):
        city_url = f"{SUPABASE_URL}/rest/v1/{TABLE}?select=grid_hash,score&city=eq.{user['city']}&order=score.desc"
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=_ssl_context())) as session:
            async with session.get(city_url, headers=_headers()) as resp:
                city_entries = await resp.json() if resp.status == 200 else []
        city_rank = next((i+1 for i, e in enumerate(city_entries) if e["grid_hash"] == grid_hash), None)
        rankings["city"] = {"rank": city_rank, "total": len(city_entries), "label": user["city"]}
    
    # ZIP ranking
    if user.get("zip_code"):
        zip_url = f"{SUPABASE_URL}/rest/v1/{TABLE}?select=grid_hash,score&zip_code=eq.{user['zip_code']}&order=score.desc"
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=_ssl_context())) as session:
            async with session.get(zip_url, headers=_headers()) as resp:
                zip_entries = await resp.json() if resp.status == 200 else []
        zip_rank = next((i+1 for i, e in enumerate(zip_entries) if e["grid_hash"] == grid_hash), None)
        rankings["zip"] = {"rank": zip_rank, "total": len(zip_entries), "label": user["zip_code"]}
    
    # Ward ranking
    if user.get("ward"):
        ward_url = f"{SUPABASE_URL}/rest/v1/{TABLE}?select=grid_hash,score&ward=eq.{user['ward']}&order=score.desc"
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=_ssl_context())) as session:
            async with session.get(ward_url, headers=_headers()) as resp:
                ward_entries = await resp.json() if resp.status == 200 else []
        ward_rank = next((i+1 for i, e in enumerate(ward_entries) if e["grid_hash"] == grid_hash), None)
        rankings["ward"] = {"rank": ward_rank, "total": len(ward_entries), "label": user["ward"]}
    
    return {"user": user, "rankings": rankings}


# Test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        print("Testing Supabase connection...")
        
        entry = await add_entry(
            lat=40.6655,
            lng=-111.8965,
            grid_hash="40.666_-111.897",
            score=80.0,
            grade="A",
            display_name="Test User",
            city="Murray",
            county="Salt Lake",
            zip_code="84107",
            ward="Murray 4th Ward",
            identity_level="migration_champion",
        )
        print(f"Added: {entry}")
        
        lb = await get_leaderboard("state")
        print(f"Leaderboard: {lb['total_participants']} entries")
        
        print("✅ Supabase connected!")
    
    asyncio.run(test())
