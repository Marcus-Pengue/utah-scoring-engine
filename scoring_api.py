from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from typing import List
import random

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

user_gardens = {}

class ScoringRequest(BaseModel):
    latitude: float
    longitude: float
    address: str = ""

class GardenData(BaseModel):
    lat: float
    lng: float
    plants: List[dict] = []
    features: List[str] = []
    size: str = "medium"
    score: int = 0
    name: str = "My Garden"

class AddressRequest(BaseModel):
    address: str
    zip: str

# Mock Utah addresses for demo
MOCK_ADDRESSES = {
    "84103": {"lat": 40.7608, "lng": -111.8910, "city": "Salt Lake City"},
    "84107": {"lat": 40.6461, "lng": -111.8939, "city": "Murray"},
    "84129": {"lat": 40.6021, "lng": -111.9655, "city": "Taylorsville"},
    "84121": {"lat": 40.6163, "lng": -111.8257, "city": "Cottonwood Heights"},
    "84070": {"lat": 40.5725, "lng": -111.8584, "city": "Sandy"},
}

def score_to_grade(score):
    if score >= 90: return "A+"
    if score >= 85: return "A"
    if score >= 80: return "A-"
    if score >= 77: return "B+"
    if score >= 73: return "B"
    if score >= 70: return "B-"
    if score >= 67: return "C+"
    if score >= 63: return "C"
    if score >= 60: return "C-"
    if score >= 50: return "D"
    return "F"

def get_tier(score):
    if score >= 85: return "Pollinator Champion"
    if score >= 70: return "Habitat Hero"
    if score >= 55: return "Bee Friendly"
    if score >= 40: return "Growing"
    return "Seedling"

@app.get("/health")
def health():
    return {"status": "ok", "gardens_registered": len(user_gardens)}

@app.post("/api/geocode")
def geocode_address(req: AddressRequest):
    """Mock geocoding - returns approximate location based on ZIP."""
    if req.zip in MOCK_ADDRESSES:
        loc = MOCK_ADDRESSES[req.zip]
        # Add slight randomness for different addresses in same ZIP
        random.seed(hash(req.address))
        return {
            "success": True,
            "latitude": loc["lat"] + random.uniform(-0.01, 0.01),
            "longitude": loc["lng"] + random.uniform(-0.01, 0.01),
            "city": loc["city"],
            "address": req.address,
            "zip": req.zip,
            "note": "Mock geocoding - upgrade to UGRC API for production"
        }
    return {"success": False, "error": "ZIP code not in Utah service area"}

@app.post("/api/score")
def calculate_score(req: ScoringRequest):
    seed = int((req.latitude * 1000 + req.longitude * 1000) % 10000)
    random.seed(seed)
    act_score = random.randint(5, 20)
    sept_score = random.randint(0, 18)
    conn_score = random.randint(8, 18)
    div_score = random.randint(3, 12)
    bloom_score = random.randint(2, 8)
    overall = act_score + sept_score + conn_score + div_score + bloom_score
    
    return {
        "overall_score": overall,
        "max_score": 100,
        "grade": score_to_grade(overall),
        "factors": {
            "pollinatorActivity": {"score": act_score, "max_score": 25, "percentage": round(act_score/25*100,1), "details": {}, "recommendations": []},
            "septemberGap": {"score": sept_score, "max_score": 30, "percentage": round(sept_score/30*100,1), "details": {"status": "Severe gap" if sept_score < 12 else "Moderate"}, "recommendations": ["Plant fall bloomers"] if sept_score < 18 else []},
            "connectivity": {"score": conn_score, "max_score": 20, "percentage": round(conn_score/20*100,1), "details": {}, "recommendations": []},
            "speciesDiversity": {"score": div_score, "max_score": 15, "percentage": round(div_score/15*100,1), "details": {}, "recommendations": []},
            "bloomCoverage": {"score": bloom_score, "max_score": 10, "percentage": round(bloom_score/10*100,1), "details": {}, "recommendations": []}
        },
        "top_recommendations": ["Plant fall bloomers for September"] if sept_score < 18 else [],
        "nearby_observations": random.randint(10, 100),
        "unique_species": random.randint(5, 30),
        "calculated_at": datetime.now().isoformat(),
        "methodology_version": "1.0.0"
    }

@app.get("/api/leaderboard")
def get_leaderboard(city: str = "Murray"):
    random.seed(42)
    neighborhoods = ["Liberty", "Hillcrest", "Fashion Place", "Vine Street", "Woodstock"]
    gardens = []
    for i in range(24):
        score = random.randint(30, 95)
        gardens.append({
            "id": f"garden-{i+1:03d}",
            "anonymousId": f"Garden #{i+1}",
            "city": city,
            "neighborhood": random.choice(neighborhoods),
            "score": score,
            "verifiedScore": score,
            "tier": get_tier(score),
            "plantCount": random.randint(5, 40),
            "nativePlantCount": random.randint(3, 25),
            "fallBloomerCount": random.randint(0, 10),
            "observationCount": random.randint(0, 50),
            "referralCount": random.randint(0, 5),
            "verificationLevel": random.choice(["unverified", "community", "professional"]),
            "registeredAt": f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            "isCurrentUser": False
        })
    for g in user_gardens.values():
        gardens.append(g)
    gardens.sort(key=lambda x: x["score"], reverse=True)
    return {"city": city, "gardens": gardens}

@app.post("/api/garden/register")
def register_garden(garden: GardenData):
    garden_id = f"garden-user-{len(user_gardens) + 1:03d}"
    user_gardens[garden_id] = {
        "id": garden_id,
        "anonymousId": garden.name,
        "lat": garden.lat,
        "lng": garden.lng,
        "city": "Murray",
        "neighborhood": "Your Neighborhood",
        "score": garden.score,
        "verifiedScore": garden.score,
        "tier": get_tier(garden.score),
        "plantCount": len(garden.plants),
        "nativePlantCount": len([p for p in garden.plants if p.get("native", False)]),
        "fallBloomerCount": len([p for p in garden.plants if "fall" in str(p.get("season", ""))]),
        "observationCount": 0,
        "referralCount": 0,
        "verificationLevel": "unverified",
        "registeredAt": datetime.now().strftime("%Y-%m-%d"),
        "isCurrentUser": True
    }
    return {"success": True, "gardenId": garden_id, "garden": user_gardens[garden_id]}

@app.get("/api/garden/mine")
def get_my_garden():
    if user_gardens:
        return {"garden": list(user_gardens.values())[-1]}
    return {"garden": None}

if __name__ == "__main__":
    import uvicorn
    print("🐝 BeehiveConnect API (Mock Mode)")
    uvicorn.run(app, host="0.0.0.0", port=8000)
