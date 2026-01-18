"""
Score Engine
=============
Persists and recalculates scores when data changes.
Powers leaderboards and progress tracking.
"""

import aiohttp
import asyncio
import ssl
import certifi
from datetime import datetime
from scoring_v2 import score_property, PropertyData, PlantInventory, Season
from scoring_config import get_model_version, get_active_model

SUPABASE_URL = "https://gqexnqmqwhpcrleksrkb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdxZXhucW1xd2hwY3JsZWtzcmtiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjYyNzg1OTEsImV4cCI6MjA4MTg1NDU5MX0.glfXIcO8ofdyWUC9nlf9Y-6EzF30BXlxtIY8NXVEORM"

def _ssl_context():
    return ssl.create_default_context(cafile=certifi.where())

def _headers(token=None):
    h = {"apikey": SUPABASE_KEY, "Content-Type": "application/json"}
    h["Authorization"] = f"Bearer {token}" if token else f"Bearer {SUPABASE_KEY}"
    return h


async def get_user_data(user_id, grid_hash, token):
    """Gather all user data needed for score calculation."""
    data = {
        "plants": [],
        "assessment": None,
        "neighbors": 0,
    }
    
    async with aiohttp.ClientSession() as session:
        # Get plant inventory
        url = f"{SUPABASE_URL}/rest/v1/plant_inventories?user_id=eq.{user_id}"
        if grid_hash:
            url += f"&grid_hash=eq.{grid_hash}"
        
        async with session.get(url, headers=_headers(token), ssl=_ssl_context()) as resp:
            if resp.status == 200:
                data['plants'] = await resp.json()
        
        # Get latest assessment
        url = f"{SUPABASE_URL}/rest/v1/habitat_assessments?user_id=eq.{user_id}&order=assessment_date.desc&limit=1"
        if grid_hash:
            url = f"{SUPABASE_URL}/rest/v1/habitat_assessments?user_id=eq.{user_id}&grid_hash=eq.{grid_hash}&order=assessment_date.desc&limit=1"
        
        async with session.get(url, headers=_headers(token), ssl=_ssl_context()) as resp:
            if resp.status == 200:
                assessments = await resp.json()
                if assessments:
                    data['assessment'] = assessments[0]
        
        # Get referral connections
        url = f"{SUPABASE_URL}/rest/v1/referrals?referrer_id=eq.{user_id}&status=eq.joined"
        async with session.get(url, headers=_headers(token), ssl=_ssl_context()) as resp:
            if resp.status == 200:
                referrals = await resp.json()
                data['neighbors'] = len(referrals)
    
    return data


def build_property_data(user_data):
    """Convert user data to PropertyData for scoring."""
    plants = user_data.get('plants', [])
    assessment = user_data.get('assessment') or {}
    
    # Build plant inventory
    plant_list = []
    for p in plants:
        seasons = p.get('bloom_seasons', []) or []
        plant_list.append(PlantInventory(
            species=p.get('species', ''),
            count=p.get('count', 1),
            bloom_seasons=seasons,
            is_native=p.get('is_native', True),
            is_milkweed=p.get('is_milkweed', False),
        ))
    
    # Calculate coverage estimate from plants if not in assessment
    total_plants = sum(p.get('count', 1) for p in plants)
    coverage = assessment.get('flower_coverage_pct') or min(total_plants * 2, 50)
    
    return PropertyData(
        lat=0,
        lng=0,
        grid_hash=assessment.get('grid_hash', ''),
        plants=plant_list,
        flower_coverage_pct=coverage,
        has_bare_ground=assessment.get('has_bare_ground', False),
        bare_ground_sqft=assessment.get('bare_ground_sqft', 0),
        has_dead_wood=assessment.get('has_dead_wood', False),
        has_bee_hotel=assessment.get('has_bee_hotel', False),
        has_brush_pile=assessment.get('has_brush_pile', False),
        leaves_stems_over_winter=assessment.get('leaves_stems_over_winter', False),
        uses_pesticides=assessment.get('pesticide_frequency', 'sometimes') not in ['never', 'rarely'],
        pesticide_frequency=assessment.get('pesticide_frequency', 'sometimes'),
        mowing_frequency=assessment.get('mowing_frequency', 'weekly'),
        neighbors_in_program=user_data.get('neighbors', 0) + assessment.get('neighbors_in_program', 0),
        green_space_within_500m=0,  # Would need geo lookup
        impervious_surface_pct=assessment.get('impervious_surface_pct', 30),
        lot_size_sqft=assessment.get('lot_size_sqft', 5000),
    )


async def recalculate_and_store_score(user_id, grid_hash, token, source='auto'):
    """
    Recalculate user's score and persist it.
    
    Returns the new score data.
    """
    # Gather data
    user_data = await get_user_data(user_id, grid_hash, token)
    
    # Build property data
    property_data = build_property_data(user_data)
    
    # Calculate score
    score_result = score_property(property_data)
    
    # Prepare record
    record = {
        "user_id": user_id,
        "grid_hash": grid_hash or property_data.grid_hash,
        "total_score": score_result.final_score,
        "grade": score_result.grade,
        "floral_score": score_result.floral_score,
        "nesting_score": score_result.nesting_score,
        "connectivity_score": score_result.connectivity_score,
        "management_score": score_result.management_score,
        "impervious_penalty": score_result.impervious_penalty,
        "confidence": score_result.confidence,
        "data_completeness": score_result.data_completeness,
        "calculated_at": datetime.utcnow().isoformat(),
        "source": source,
    }
    
    async with aiohttp.ClientSession() as session:
        # Upsert score (update if exists, insert if not)
        # First try to find existing
        url = f"{SUPABASE_URL}/rest/v1/user_scores?user_id=eq.{user_id}"
        if grid_hash:
            url += f"&grid_hash=eq.{grid_hash}"
        
        async with session.get(url, headers=_headers(token), ssl=_ssl_context()) as resp:
            existing = await resp.json() if resp.status == 200 else []
        
        headers = _headers(token)
        headers["Prefer"] = "return=representation"
        
        if existing:
            # Update
            update_url = f"{SUPABASE_URL}/rest/v1/user_scores?id=eq.{existing[0]['id']}"
            async with session.patch(update_url, headers=headers, ssl=_ssl_context(), json=record) as resp:
                pass
        else:
            # Insert
            async with session.post(f"{SUPABASE_URL}/rest/v1/user_scores", headers=headers, ssl=_ssl_context(), json=record) as resp:
                pass
        
        # Also log to history
        history_record = {
            "user_id": user_id,
            "grid_hash": grid_hash,
            "total_score": score_result.final_score,
            "grade": score_result.grade,
        }
        async with session.post(f"{SUPABASE_URL}/rest/v1/score_history", headers=headers, ssl=_ssl_context(), json=history_record) as resp:
            pass
    
    return {
        "score": score_result.final_score,
        "grade": score_result.grade,
        "breakdown": {
            "floral": score_result.floral_score,
            "nesting": score_result.nesting_score,
            "connectivity": score_result.connectivity_score,
            "management": score_result.management_score,
            "impervious_penalty": score_result.impervious_penalty,
        },
        "confidence": score_result.confidence,
    }


async def get_stored_score(user_id, grid_hash, token):
    """Get user's stored score."""
    url = f"{SUPABASE_URL}/rest/v1/user_scores?user_id=eq.{user_id}"
    if grid_hash:
        url += f"&grid_hash=eq.{grid_hash}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=_headers(token), ssl=_ssl_context()) as resp:
            if resp.status == 200:
                scores = await resp.json()
                return scores[0] if scores else None
    return None


async def get_score_history(user_id, grid_hash, token, limit=30):
    """Get user's score history."""
    url = f"{SUPABASE_URL}/rest/v1/score_history?user_id=eq.{user_id}&order=recorded_at.desc&limit={limit}"
    if grid_hash:
        url = f"{SUPABASE_URL}/rest/v1/score_history?user_id=eq.{user_id}&grid_hash=eq.{grid_hash}&order=recorded_at.desc&limit={limit}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=_headers(token), ssl=_ssl_context()) as resp:
            if resp.status == 200:
                return await resp.json()
    return []


async def get_leaderboard(grid_hash=None, limit=20):
    """Get top scores, optionally filtered by grid."""
    url = f"{SUPABASE_URL}/rest/v1/user_scores?order=total_score.desc&limit={limit}"
    if grid_hash:
        # Get nearby grids for local leaderboard
        url += f"&grid_hash=eq.{grid_hash}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=_headers(), ssl=_ssl_context()) as resp:
            if resp.status == 200:
                return await resp.json()
    return []


# Sync wrappers
def recalculate_score_sync(user_id, grid_hash, token, source='auto'):
    return asyncio.run(recalculate_and_store_score(user_id, grid_hash, token, source))

def get_score_sync(user_id, grid_hash, token):
    return asyncio.run(get_stored_score(user_id, grid_hash, token))

def get_history_sync(user_id, grid_hash, token, limit=30):
    return asyncio.run(get_score_history(user_id, grid_hash, token, limit))

def get_leaderboard_sync(grid_hash=None, limit=20):
    return asyncio.run(get_leaderboard(grid_hash, limit))


def register_score_routes(app):
    """Register score API routes."""
    from flask import request, jsonify
    
    @app.route('/api/scores/my', methods=['GET'])
    def get_my_score():
        """Get current user's stored score."""
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization required"}), 401
        
        token = auth_header.split(' ')[1]
        grid_hash = request.args.get('grid_hash')
        
        async def fetch():
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{SUPABASE_URL}/auth/v1/user",
                    headers=_headers(token),
                    ssl=_ssl_context()
                ) as resp:
                    if resp.status != 200:
                        return None, "Invalid token"
                    user = await resp.json()
                    user_id = user.get('id')
            
            score = await get_stored_score(user_id, grid_hash, token)
            history = await get_score_history(user_id, grid_hash, token, limit=10)
            
            return {"score": score, "history": history}, None
        
        result, error = asyncio.run(fetch())
        if error:
            return jsonify({"error": error}), 401
        
        return jsonify(result)
    
    @app.route('/api/scores/recalculate', methods=['POST'])
    def recalculate_my_score():
        """Force recalculate current user's score."""
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization required"}), 401
        
        token = auth_header.split(' ')[1]
        data = request.get_json() or {}
        grid_hash = data.get('grid_hash')
        
        async def recalc():
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{SUPABASE_URL}/auth/v1/user",
                    headers=_headers(token),
                    ssl=_ssl_context()
                ) as resp:
                    if resp.status != 200:
                        return None, "Invalid token"
                    user = await resp.json()
                    user_id = user.get('id')
            
            result = await recalculate_and_store_score(user_id, grid_hash, token, source='manual')
            return result, None
        
        result, error = asyncio.run(recalc())
        if error:
            return jsonify({"error": error}), 401
        
        return jsonify(result)
    
    @app.route('/api/scores/leaderboard', methods=['GET'])
    def score_leaderboard():
        """Get score leaderboard."""
        grid_hash = request.args.get('grid_hash')
        limit = request.args.get('limit', 20, type=int)
        
        leaders = get_leaderboard_sync(grid_hash, limit)
        
        # Add rank
        for i, l in enumerate(leaders):
            l['rank'] = i + 1
        
        return jsonify({"leaderboard": leaders})
