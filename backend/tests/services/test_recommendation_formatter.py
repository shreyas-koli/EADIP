import pytest
from app.recommendation.formatter import RecommendationFormatter

def test_recommendation_formatter_empty():
    formatter = RecommendationFormatter()
    assert formatter.format({}) == {}

def test_recommendation_formatter_valid():
    formatter = RecommendationFormatter()
    raw_data = {
        "summary": {
            "recommendation_count": 2,
            "high": 1,
            "medium": 1,
            "low": 0
        },
        "recommendations": [
            {
                "recommendation_type": "sensitive_column",
                "schema": "public",
                "table": "users",
                "column": "email",
                "priority": "HIGH",
                "impact": "HIGH",
                "effort": "LOW",
                "confidence": 1.0,
                "category": "Security",
                "description": "Sensitive column detected",
                "source_agents": ["security"]
            },
            {
                "recommendation_type": "unknown_future_rule",
                "schema": "public",
                "table": "orders",
                "column": None,
                "priority": "MEDIUM",
                "impact": "MEDIUM",
                "effort": "MEDIUM",
                "confidence": 0.85,
                "category": "Custom",
                "description": "A weird custom rule fired.",
                "source_agents": ["data_quality", "metadata"]
            }
        ],
        "priority": {
            "high": [], "medium": [], "low": []
        }
    }
    
    result = formatter.format(raw_data)
    
    # 1. Assert raw data remains intact
    assert "summary" in result
    assert "recommendations" in result
    assert "priority" in result
    
    # 2. Assert presentation structure is generated
    assert "presentation" in result
    presentation = result["presentation"]
    assert "overview" in presentation
    assert "priority_actions" in presentation
    
    # 3. Check overview
    overview = presentation["overview"]
    assert overview["total"] == 2
    assert overview["high"] == 1
    assert overview["medium"] == 1
    assert overview["low"] == 0
    
    # 4. Check priority actions parsing (Known Rule)
    actions = presentation["priority_actions"]
    assert len(actions) == 2
    
    action1 = actions[0]
    assert action1["title"] == "Sensitive Data Detected"
    assert "personally identifiable information" in action1["problem"]
    assert action1["priority"] == "HIGH"
    assert action1["confidence"] == 100.0
    assert action1["source"] == "Security Agent"
    assert action1["location"]["schema"] == "public"
    assert action1["location"]["table"] == "users"
    assert action1["location"]["column"] == "email"
    
    # 5. Check unknown rule fallback
    action2 = actions[1]
    assert action2["title"] == "Database Recommendation"
    assert action2["problem"] == "A weird custom rule fired." # Falls back to description
    assert action2["confidence"] == 85.0
    assert action2["source"] == "Data Quality Agent, Metadata Agent"
