"""
Scoring Configuration
======================
Dynamic weights and versioning for model validation.
Change weights here to test different models.
"""

# Current active model version
ACTIVE_MODEL_VERSION = "2.0.0"

# Model versions with their weights
SCORING_MODELS = {
    "2.0.0": {
        "name": "Research-Validated v2",
        "description": "Based on ESTIMAP, InVEST, Berlin study",
        "created_at": "2025-12-21",
        
        # Component weights (must sum to 100)
        "weights": {
            "floral": 35,
            "nesting": 30,
            "connectivity": 20,
            "management": 15,
        },
        
        # Floral sub-weights
        "floral_config": {
            "diversity_max": 12,
            "coverage_max": 8,
            "spring_points": 2,
            "summer_points": 2,
            "fall_points": 6,  # 1.5-2x weight for September
            "milkweed_max": 5,
            
            # Diversity thresholds
            "diversity_tiers": [
                {"min_species": 10, "points": 12},
                {"min_species": 7, "points": 10},
                {"min_species": 5, "points": 8},
                {"min_species": 3, "points": 5},
                {"min_species": 1, "points": 2},
            ],
            
            # Coverage thresholds
            "coverage_tiers": [
                {"min_pct": 30, "points": 8},
                {"min_pct": 20, "points": 6},
                {"min_pct": 10, "points": 4},
                {"min_pct": 5, "points": 2},
            ],
        },
        
        # Nesting sub-weights
        "nesting_config": {
            "ground_max": 10,
            "cavity_max": 10,
            "undisturbed_max": 10,
            
            # Ground nesting sqft thresholds
            "ground_tiers": [
                {"min_sqft": 50, "points": 10},
                {"min_sqft": 25, "points": 7},
                {"min_sqft": 10, "points": 5},
                {"min_sqft": 1, "points": 3},
            ],
            
            # Cavity features
            "dead_wood_points": 4,
            "bee_hotel_points": 3,
            "brush_pile_points": 3,
            "hollow_stems_points": 2,
            
            # Undisturbed
            "leaves_winter_points": 5,
            "leaf_litter_points": 2,
            "mowing_points": {
                "never": 3,
                "monthly": 2,
                "biweekly": 1,
                "weekly": 0,
            },
        },
        
        # Connectivity config
        "connectivity_config": {
            "pioneer_bonus": 8,
            "early_adopter_bonus": 4,
            "neighbor_tiers": [
                {"min_neighbors": 5, "points": 10},
                {"min_neighbors": 3, "points": 7},
                {"min_neighbors": 2, "points": 5},
                {"min_neighbors": 1, "points": 3},
            ],
            "green_space_tiers": [
                {"level": "large", "points": 10},
                {"level": "medium", "points": 7},
                {"level": "small", "points": 4},
                {"level": "none", "points": 2},
            ],
        },
        
        # Management config
        "management_config": {
            "pesticide_free_max": 8,
            "native_pct_max": 7,
            
            "pesticide_points": {
                "never": 8,
                "rarely": 5,
                "sometimes": 2,
                "often": 0,
            },
            
            "native_tiers": [
                {"min_pct": 80, "points": 7},
                {"min_pct": 60, "points": 5},
                {"min_pct": 40, "points": 3},
                {"min_pct": 20, "points": 1},
            ],
        },
        
        # Impervious penalty
        "impervious_config": {
            "threshold_pct": 22,  # Berlin study R²=0.84
            "penalty_per_pct": 0.35,
            "max_penalty": 10,
        },
        
        # Grade thresholds
        "grade_thresholds": {
            "A+": 90, "A": 85, "A-": 80,
            "B+": 75, "B": 70, "B-": 65,
            "C+": 60, "C": 55, "C-": 50,
            "D": 40,
        },
        
        # Research citations
        "citations": [
            "ESTIMAP-Pollination model (Zulian et al., 2013) R²=0.80",
            "InVEST Pollination Model (Sharp et al., 2020) R²=0.65-0.80",
            "Berlin impervious study (Fortel et al., 2014) R²=0.84",
            "September deficit finding (Murray Corridor, 2025) 84.5%",
        ],
    },
    
    # Future model version example
    "2.1.0-beta": {
        "name": "Adjusted Fall Weight",
        "description": "Testing higher fall bloom weight",
        "created_at": "2025-12-21",
        "weights": {
            "floral": 40,  # Increased
            "nesting": 25,  # Decreased
            "connectivity": 20,
            "management": 15,
        },
        "floral_config": {
            "fall_points": 8,  # Even higher fall weight
            # ... inherit rest from 2.0.0
        },
    },
}


def get_active_model():
    """Get the currently active scoring model config."""
    return SCORING_MODELS.get(ACTIVE_MODEL_VERSION, SCORING_MODELS["2.0.0"])


def get_model(version):
    """Get a specific model version."""
    return SCORING_MODELS.get(version)


def get_model_version():
    """Get current model version string."""
    return ACTIVE_MODEL_VERSION


def list_models():
    """List all available models."""
    return [
        {
            "version": v,
            "name": m.get("name"),
            "description": m.get("description"),
            "active": v == ACTIVE_MODEL_VERSION,
        }
        for v, m in SCORING_MODELS.items()
    ]


def register_config_routes(app):
    """Register scoring config API routes."""
    from flask import jsonify
    
    @app.route('/api/scoring/models', methods=['GET'])
    def list_scoring_models():
        """List all scoring model versions."""
        return jsonify({
            "active_version": get_model_version(),
            "models": list_models()
        })
    
    @app.route('/api/scoring/models/<version>', methods=['GET'])
    def get_scoring_model(version):
        """Get details of a specific model version."""
        model = get_model(version)
        if not model:
            return jsonify({"error": "Model not found"}), 404
        
        return jsonify({
            "version": version,
            "config": model,
            "active": version == get_model_version()
        })
    
    @app.route('/api/scoring/methodology', methods=['GET'])
    def get_methodology():
        """Get current scoring methodology for transparency."""
        model = get_active_model()
        return jsonify({
            "version": get_model_version(),
            "name": model.get("name"),
            "description": model.get("description"),
            "weights": model.get("weights"),
            "citations": model.get("citations"),
            "impervious_threshold": model.get("impervious_config", {}).get("threshold_pct"),
            "fall_bloom_weight": f"{model.get('floral_config', {}).get('fall_points', 6)} points (1.5-2x standard)",
        })
