"""
Evidence-Based Pollinator Habitat Scoring System v2
====================================================
Based on validated research synthesis with documented R² values.

Weights derived from:
- ESTIMAP-Pollination model (R² up to 0.80)
- InVEST Pollination Model (R² 0.65-0.80)
- Meta-analysis of 80+ validated frameworks

Key insight: September resources get 1.5-2× weight due to
84.5% nectar deficit during peak pollinator activity.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class Season(Enum):
    SPRING = "spring"      # March-May
    SUMMER = "summer"      # June-August
    FALL = "fall"          # September-October (CRITICAL)


@dataclass
class PlantInventory:
    """User-reported plant inventory."""
    species: str
    count: int = 1
    bloom_seasons: List[Season] = field(default_factory=list)
    is_native: bool = True
    is_milkweed: bool = False


@dataclass
class PropertyData:
    """All data needed to score a property."""
    # Location
    lat: float
    lng: float
    grid_hash: str = ""
    
    # Floral resources (user-reported)
    plants: List[PlantInventory] = field(default_factory=list)
    estimated_flower_coverage_pct: float = 0  # 0-100
    
    # Nesting habitat (user-reported)
    has_bare_ground: bool = False
    bare_ground_sqft: float = 0
    has_dead_wood: bool = False
    has_brush_pile: bool = False
    has_bee_hotel: bool = False
    leaves_stems_over_winter: bool = False
    
    # Connectivity (calculated)
    neighbors_in_program: int = 0
    green_space_within_500m: float = 0  # percentage
    distance_to_nearest_habitat_m: float = 1000
    
    # Management (user-reported)
    uses_pesticides: bool = False
    pesticide_frequency: str = "never"  # never, rarely, sometimes, often
    mowing_frequency: str = "weekly"  # weekly, biweekly, monthly, rarely
    
    # Property characteristics (from parcel data or estimate)
    lot_size_sqft: float = 5000
    impervious_surface_pct: float = 30  # buildings, driveway, etc.


@dataclass
class ScoreBreakdown:
    """Detailed score breakdown for transparency."""
    
    # Main components (sum to 100 before penalty)
    floral_score: float = 0          # 0-35
    nesting_score: float = 0         # 0-30
    connectivity_score: float = 0
    connectivity_pioneer: float = 0    # 0-20
    management_score: float = 0      # 0-15
    
    # Sub-scores for floral
    floral_diversity: float = 0      # 0-12
    floral_coverage: float = 0       # 0-8
    floral_spring: float = 0         # 0-2
    floral_summer: float = 0         # 0-2
    floral_fall: float = 0           # 0-6 (WEIGHTED)
    floral_milkweed_bonus: float = 0 # 0-5
    
    # Sub-scores for nesting
    nesting_ground: float = 0        # 0-10
    nesting_cavity: float = 0        # 0-10
    nesting_undisturbed: float = 0   # 0-10
    
    # Penalty
    impervious_penalty: float = 0    # 0 to -10
    
    # Final
    raw_score: float = 0             # Before penalty
    final_score: float = 0           # After penalty, 0-100
    grade: str = "F"
    
    # Metadata
    confidence: str = "low"          # low, medium, high
    data_completeness: float = 0     # 0-100%
    recommendations: List[str] = field(default_factory=list)


# =============================================================================
# SCORING FUNCTIONS
# =============================================================================

def score_floral_resources(data: PropertyData) -> Dict[str, float]:
    """
    Score floral resources (35 points max).
    
    Research basis:
    - Floral resources correlate with pollinator abundance at R²=0.45-0.75
    - Species richness, abundance, and seasonal continuity all matter
    - Fall resources get 1.5-2× weight (84.5% deficit finding)
    """
    
    scores = {
        "diversity": 0,
        "coverage": 0,
        "spring": 0,
        "summer": 0,
        "fall": 0,
        "milkweed_bonus": 0,
        "total": 0,
    }
    
    plants = data.plants
    
    # DIVERSITY: 0-12 points
    # Count unique native flowering species
    native_species = len([p for p in plants if p.is_native])
    total_species = len(plants)
    
    if native_species >= 10:
        scores["diversity"] = 12
    elif native_species >= 7:
        scores["diversity"] = 10
    elif native_species >= 5:
        scores["diversity"] = 8
    elif native_species >= 3:
        scores["diversity"] = 5
    elif native_species >= 1:
        scores["diversity"] = 2
    
    # Bonus for non-native but beneficial (capped)
    non_native_bonus = min((total_species - native_species) * 0.5, 2)
    scores["diversity"] = min(scores["diversity"] + non_native_bonus, 12)
    
    # COVERAGE: 0-8 points
    coverage = data.estimated_flower_coverage_pct
    if coverage >= 30:
        scores["coverage"] = 8
    elif coverage >= 20:
        scores["coverage"] = 6
    elif coverage >= 10:
        scores["coverage"] = 4
    elif coverage >= 5:
        scores["coverage"] = 2
    
    # SEASONAL CONTINUITY: Spring 2, Summer 2, Fall 6 (WEIGHTED)
    seasons_covered = {Season.SPRING: False, Season.SUMMER: False, Season.FALL: False}
    
    for plant in plants:
        for season in plant.bloom_seasons:
            seasons_covered[season] = True
    
    if seasons_covered[Season.SPRING]:
        scores["spring"] = 2
    if seasons_covered[Season.SUMMER]:
        scores["summer"] = 2
    if seasons_covered[Season.FALL]:
        scores["fall"] = 6  # 1.5-2× weight for September
    
    # MILKWEED BONUS: 0-5 points
    milkweed_count = sum(p.count for p in plants if p.is_milkweed)
    if milkweed_count >= 5:
        scores["milkweed_bonus"] = 5
    elif milkweed_count >= 3:
        scores["milkweed_bonus"] = 4
    elif milkweed_count >= 1:
        scores["milkweed_bonus"] = 3
    
    # TOTAL (capped at 35)
    scores["total"] = min(
        scores["diversity"] + 
        scores["coverage"] + 
        scores["spring"] + 
        scores["summer"] + 
        scores["fall"] + 
        scores["milkweed_bonus"],
        35
    )
    
    return scores


def score_nesting_habitat(data: PropertyData) -> Dict[str, float]:
    """
    Score nesting sites (30 points max).
    
    Research basis:
    - Nesting suitability correlates with species richness at R²=0.35-0.65
    - Ground nesters (70% of native bees) need bare/sandy soil
    - Cavity nesters need hollow stems, wood, or structures
    - Undisturbed areas critical for overwintering
    """
    
    scores = {
        "ground": 0,
        "cavity": 0,
        "undisturbed": 0,
        "total": 0,
    }
    
    # GROUND NESTING: 0-10 points
    # 70% of native bees are ground nesters
    if data.has_bare_ground:
        if data.bare_ground_sqft >= 50:
            scores["ground"] = 10
        elif data.bare_ground_sqft >= 25:
            scores["ground"] = 7
        elif data.bare_ground_sqft >= 10:
            scores["ground"] = 5
        else:
            scores["ground"] = 3
    
    # CAVITY NESTING: 0-10 points
    cavity_features = 0
    if data.has_dead_wood:
        cavity_features += 4
    if data.has_bee_hotel:
        cavity_features += 3
    if data.has_brush_pile:
        cavity_features += 3
    scores["cavity"] = min(cavity_features, 10)
    
    # UNDISTURBED AREAS: 0-10 points
    undisturbed = 0
    if data.leaves_stems_over_winter:
        undisturbed += 5  # Critical for overwintering
    if data.mowing_frequency in ["monthly", "rarely"]:
        undisturbed += 3
    elif data.mowing_frequency == "biweekly":
        undisturbed += 1
    if data.has_brush_pile:
        undisturbed += 2
    scores["undisturbed"] = min(undisturbed, 10)
    
    scores["total"] = scores["ground"] + scores["cavity"] + scores["undisturbed"]
    
    return scores


def score_connectivity(data: PropertyData) -> Dict[str, float]:
    """
    Score connectivity (20 points max).
    
    Pioneer adjustment:
    - Early adopters get bonus for starting the network
    - Weight shifts to neighbor count as network grows
    """
    
    scores = {
        "neighbors": 0,
        "green_space": 0,
        "pioneer_bonus": 0,
        "total": 0,
    }
    
    neighbors = data.neighbors_in_program
    
    # PIONEER BONUS: Rewards being first
    if neighbors == 0:
        scores["pioneer_bonus"] = 8  # First in area
        scores["neighbors"] = 0
    elif neighbors <= 2:
        scores["pioneer_bonus"] = 4  # Early adopter
        scores["neighbors"] = neighbors * 2
    else:
        scores["pioneer_bonus"] = 0  # Established network
        if neighbors >= 5:
            scores["neighbors"] = 10
        elif neighbors >= 3:
            scores["neighbors"] = 7
        else:
            scores["neighbors"] = 5
    
    # GREEN SPACE WITHIN 500m
    green_pct = data.green_space_within_500m
    if green_pct >= 30:
        scores["green_space"] = 10
    elif green_pct >= 20:
        scores["green_space"] = 7
    elif green_pct >= 10:
        scores["green_space"] = 5
    elif green_pct >= 5:
        scores["green_space"] = 3
    else:
        scores["green_space"] = 2  # Baseline for urban
    
    scores["total"] = min(
        scores["neighbors"] + scores["green_space"] + scores["pioneer_bonus"],
        20
    )
    
    return scores



def score_management(data: PropertyData) -> Dict[str, float]:
    """
    Score management quality (15 points max).
    
    Research basis:
    - Pesticides directly harm pollinators
    - Native plant proportion indicates long-term sustainability
    """
    
    scores = {
        "pesticide_free": 0,
        "native_proportion": 0,
        "total": 0,
    }
    
    # PESTICIDE-FREE: 0-8 points
    if not data.uses_pesticides or data.pesticide_frequency == "never":
        scores["pesticide_free"] = 8
    elif data.pesticide_frequency == "rarely":
        scores["pesticide_free"] = 5
    elif data.pesticide_frequency == "sometimes":
        scores["pesticide_free"] = 2
    # "often" = 0
    
    # NATIVE PROPORTION: 0-7 points
    total_plants = len(data.plants)
    if total_plants > 0:
        native_pct = len([p for p in data.plants if p.is_native]) / total_plants * 100
        if native_pct >= 80:
            scores["native_proportion"] = 7
        elif native_pct >= 60:
            scores["native_proportion"] = 5
        elif native_pct >= 40:
            scores["native_proportion"] = 3
        elif native_pct >= 20:
            scores["native_proportion"] = 1
    
    scores["total"] = scores["pesticide_free"] + scores["native_proportion"]
    
    return scores


def calculate_impervious_penalty(data: PropertyData) -> float:
    """
    Calculate impervious surface penalty.
    
    Research basis:
    - Berlin study: impervious surfaces at 500m explained 84% of variance
    - Pollinator abundance declines when impervious cover exceeds 22-25%
    - Each % above threshold warrants proportional reduction
    """
    
    THRESHOLD = 22  # Research-based threshold
    MAX_PENALTY = 10
    
    if data.impervious_surface_pct <= THRESHOLD:
        return 0
    
    # Penalty scales from 0 at 22% to -10 at 50%+
    excess = data.impervious_surface_pct - THRESHOLD
    penalty = min(excess * 0.35, MAX_PENALTY)
    
    return -penalty


def calculate_data_completeness(data: PropertyData) -> float:
    """Calculate how complete the user's data is."""
    
    fields_provided = 0
    total_fields = 10
    
    if len(data.plants) > 0:
        fields_provided += 1
    if data.estimated_flower_coverage_pct > 0:
        fields_provided += 1
    if data.has_bare_ground or data.bare_ground_sqft > 0:
        fields_provided += 1
    if data.has_dead_wood or data.has_bee_hotel or data.has_brush_pile:
        fields_provided += 1
    if data.leaves_stems_over_winter:
        fields_provided += 1
    if data.mowing_frequency != "weekly":  # Non-default
        fields_provided += 1
    if data.pesticide_frequency != "never":  # User considered it
        fields_provided += 1
    if data.lot_size_sqft != 5000:  # Non-default
        fields_provided += 1
    if data.impervious_surface_pct != 30:  # Non-default
        fields_provided += 1
    if data.neighbors_in_program > 0:
        fields_provided += 1
    
    return (fields_provided / total_fields) * 100


def generate_recommendations(data: PropertyData, scores: ScoreBreakdown) -> List[str]:
    """Generate actionable recommendations based on scores."""
    
    recs = []
    
    # CRITICAL: September gap
    has_fall_blooms = any(
        Season.FALL in p.bloom_seasons 
        for p in data.plants
    )
    if not has_fall_blooms:
        recs.append({
            "priority": "critical",
            "title": "September Nectar Gap",
            "message": "Add fall-blooming plants for monarch migration",
            "plants": ["Rabbitbrush", "Goldenrod", "Asters"],
            "impact": "+6 points"
        })
    
    # CRITICAL: No milkweed
    has_milkweed = any(p.is_milkweed for p in data.plants)
    if not has_milkweed:
        recs.append({
            "priority": "high",
            "title": "Missing Host Plant",
            "message": "Monarchs can only lay eggs on milkweed",
            "plants": ["Showy Milkweed", "Narrowleaf Milkweed"],
            "impact": "+3-5 points"
        })
    
    # Nesting habitat
    if scores.nesting_score < 15:
        if not data.has_bare_ground:
            recs.append({
                "priority": "medium",
                "title": "Ground Nesting Habitat",
                "message": "70% of native bees nest in bare ground",
                "action": "Leave a patch of undisturbed bare soil",
                "impact": "+5-10 points"
            })
        if not data.leaves_stems_over_winter:
            recs.append({
                "priority": "medium",
                "title": "Overwintering Habitat",
                "message": "Leave stems and leaves through winter",
                "action": "Delay spring cleanup until temps exceed 50°F",
                "impact": "+5 points"
            })
    
    # Connectivity
    if data.neighbors_in_program == 0:
        recs.append({
            "priority": "medium",
            "title": "Invite a Neighbor",
            "message": "Connected habitats are more effective",
            "action": "Invite a neighbor to join the program",
            "impact": "+3-10 points"
        })
    
    # Pesticides
    if data.uses_pesticides and data.pesticide_frequency in ["sometimes", "often"]:
        recs.append({
            "priority": "high",
            "title": "Reduce Pesticides",
            "message": "Pesticides harm pollinators directly",
            "action": "Try integrated pest management instead",
            "impact": "+5-8 points"
        })
    
    return recs


def get_grade(score: float) -> str:
    """Convert numeric score to letter grade."""
    if score >= 90:
        return "A+"
    elif score >= 80:
        return "A"
    elif score >= 70:
        return "B"
    elif score >= 60:
        return "C"
    elif score >= 50:
        return "D"
    else:
        return "F"


def get_confidence(completeness: float) -> str:
    """Determine confidence level based on data completeness."""
    if completeness >= 70:
        return "high"
    elif completeness >= 40:
        return "medium"
    else:
        return "low"


# =============================================================================
# MAIN SCORING FUNCTION
# =============================================================================

def score_property(data: PropertyData) -> ScoreBreakdown:
    """
    Calculate complete property score with breakdown.
    
    Returns ScoreBreakdown with all components and recommendations.
    """
    
    breakdown = ScoreBreakdown()
    
    # Calculate each component
    floral = score_floral_resources(data)
    nesting = score_nesting_habitat(data)
    connectivity = score_connectivity(data)
    management = score_management(data)
    impervious = calculate_impervious_penalty(data)
    
    # Populate breakdown
    breakdown.floral_score = floral["total"]
    breakdown.floral_diversity = floral["diversity"]
    breakdown.floral_coverage = floral["coverage"]
    breakdown.floral_spring = floral["spring"]
    breakdown.floral_summer = floral["summer"]
    breakdown.floral_fall = floral["fall"]
    breakdown.floral_milkweed_bonus = floral["milkweed_bonus"]
    
    breakdown.nesting_score = nesting["total"]
    breakdown.nesting_ground = nesting["ground"]
    breakdown.nesting_cavity = nesting["cavity"]
    breakdown.nesting_undisturbed = nesting["undisturbed"]
    
    breakdown.connectivity_score = connectivity["total"]
    breakdown.management_score = management["total"]
    breakdown.impervious_penalty = impervious
    
    # Calculate totals
    breakdown.raw_score = (
        breakdown.floral_score +
        breakdown.nesting_score +
        breakdown.connectivity_score +
        breakdown.management_score
    )
    
    breakdown.final_score = max(0, min(100, breakdown.raw_score + impervious))
    breakdown.grade = get_grade(breakdown.final_score)
    
    # Metadata
    breakdown.data_completeness = calculate_data_completeness(data)
    breakdown.confidence = get_confidence(breakdown.data_completeness)
    breakdown.recommendations = generate_recommendations(data, breakdown)
    
    return breakdown


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Evidence-Based Pollinator Habitat Scoring v2")
    print("=" * 60)
    
    # Test case 1: Empty yard
    print("\n📍 Test 1: Empty Yard (no data)")
    empty = PropertyData(lat=40.666, lng=-111.897)
    result = score_property(empty)
    print(f"   Score: {result.final_score}/100 ({result.grade})")
    print(f"   Confidence: {result.confidence} ({result.data_completeness:.0f}% complete)")
    
    # Test case 2: Basic yard with some effort
    print("\n📍 Test 2: Basic Garden")
    basic = PropertyData(
        lat=40.666, lng=-111.897,
        plants=[
            PlantInventory("Lavender", 3, [Season.SUMMER], is_native=False),
            PlantInventory("Black-eyed Susan", 5, [Season.SUMMER], is_native=False),
        ],
        estimated_flower_coverage_pct=10,
        uses_pesticides=False,
    )
    result = score_property(basic)
    print(f"   Score: {result.final_score}/100 ({result.grade})")
    print(f"   Floral: {result.floral_score}/35")
    print(f"   Nesting: {result.nesting_score}/30")
    print(f"   Top rec: {result.recommendations[0]['title'] if result.recommendations else 'None'}")
    
    # Test case 3: Good pollinator garden
    print("\n📍 Test 3: Good Pollinator Garden")
    good = PropertyData(
        lat=40.666, lng=-111.897,
        plants=[
            PlantInventory("Showy Milkweed", 3, [Season.SUMMER], is_native=True, is_milkweed=True),
            PlantInventory("Rabbitbrush", 2, [Season.FALL], is_native=True),
            PlantInventory("Goldenrod", 4, [Season.FALL], is_native=True),
            PlantInventory("Penstemon", 5, [Season.SPRING, Season.SUMMER], is_native=True),
            PlantInventory("Blanket Flower", 6, [Season.SUMMER], is_native=True),
        ],
        estimated_flower_coverage_pct=25,
        has_bare_ground=True,
        bare_ground_sqft=20,
        has_dead_wood=True,
        leaves_stems_over_winter=True,
        uses_pesticides=False,
        mowing_frequency="monthly",
        neighbors_in_program=2,
        impervious_surface_pct=25,
    )
    result = score_property(good)
    print(f"   Score: {result.final_score}/100 ({result.grade})")
    print(f"   Floral: {result.floral_score}/35 (diversity: {result.floral_diversity}, fall: {result.floral_fall})")
    print(f"   Nesting: {result.nesting_score}/30")
    print(f"   Connectivity: {result.connectivity_score}/20")
    print(f"   Management: {result.management_score}/15")
    print(f"   Impervious penalty: {result.impervious_penalty}")
    print(f"   Confidence: {result.confidence}")
    
    # Test case 4: High impervious
    print("\n📍 Test 4: High Impervious Surface (60%)")
    high_imp = PropertyData(
        lat=40.666, lng=-111.897,
        plants=[
            PlantInventory("Milkweed", 1, [Season.SUMMER], is_native=True, is_milkweed=True),
        ],
        impervious_surface_pct=60,
    )
    result = score_property(high_imp)
    print(f"   Score: {result.final_score}/100 ({result.grade})")
    print(f"   Impervious penalty: {result.impervious_penalty}")
