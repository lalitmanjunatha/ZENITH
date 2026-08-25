"""SIH Hackathon Mode - Dedicated hackathon development assistant.

When activated:
- Show remaining tasks
- Show blockers
- Show critical bugs
- Show unfinished core features
- Show remaining milestones
- Show demo readiness
- Show testing status
- Recommend what to work on next
- Recommend features to remove
- Warn about scope creep
- Prioritize high-impact tasks

Add a "NEXT BEST ACTION" button.

The AI should determine the most important task based on actual project state.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from Tools.sih_project_manager import SIHProjectManager
from Tools.problem_statement_analyzer import analyze_problem_statement

logger = logging.getLogger(__name__)


def activate_hackathon_mode(project_id: int) -> Dict[str, Any]:
    """
    Activate Hackathon Mode for a project.

    Shows comprehensive status and determines the NEXT BEST ACTION.

    Args:
        project_id: The SIH project ID

    Returns:
        Dict with hackathon mode status and recommendations
    """
    from Tools.sih_project_manager import SIHProjectManager
    manager = SIHProjectManager()
    
    project = manager.select_project(project_id)
    if not project:
        manager.close()
        return {"error": f"Project ID {project_id} not found"}
    
    # Get all project data
    ideas = manager.list_ideas(project_id)
    features = manager.list_features(project_id)
    risks = manager.list_risks(project_id)
    evidence = manager.list_evidence(project_id)
    decisions = manager.list_decisions(project_id)
    
    # Calculate demo readiness
    demo_readiness = _calculate_demo_readiness(features, risks, evidence)
    
    # Calculate testing status
    testing_status = _calculate_testing_status(features, evidence)
    
    # Find blockers
    blockers = _find_blockers(risks, features)
    
    # Find critical bugs
    critical_bugs = _find_critical_bugs(risks)
    
    # Find unfinished core features
    unfinished_core = _find_unfinished_core_features(features)
    
    # Find remaining milestones
    milestones = _find_milestones(risks, decisions)
    
    # Determine next best action
    next_best_action = _determine_next_best_action(features, risks, evidence, demo_readiness)
    
    # Recommend features to remove
    features_to_remove = _recommend_features_to_remove(features, risks)
    
    # Warn about scope creep
    scope_creep_warning = _check_scope_creep(features, risks)
    
    result = {
        "hackathon_mode": True,
        "project_id": project_id,
        "project_name": project.get("project_name", "Unknown"),
        "demo_readiness": {
            "score": demo_readiness["score"],
            "status": demo_readiness["status"],
            "details": demo_readiness["details"],
        },
        "testing_status": {
            "status": testing_status["status"],
            "coverage": testing_status["coverage"],
            "details": testing_status["details"],
        },
        "blockers": blockers,
        "critical_bugs": critical_bugs,
        "unfinished_core_features": unfinished_core,
        "remaining_milestones": milestones,
        "next_best_action": next_best_action,
        "features_to_remove": features_to_remove,
        "scope_creep_warning": scope_creep_warning,
        "ai_recommendations": _generate_ai_recommendations(features, risks, evidence),
    }
    
    manager.close()
    return result


def _calculate_demo_readiness(features, risks, evidence) -> Dict[str, Any]:
    """Calculate demo readiness score."""
    total_features = len(features)
    if total_features == 0:
        return {"score": 0, "status": "critical", "details": "No features defined"}
    
    # Count features with "demo impact" priority or complete status
    demo_features = sum(1 for f in features if "demo" in f.get("title", "").lower() or f.get("status") == "complete")
    core_features = sum(1 for f in features if "must have" in f.get("priority", "").lower())
    
    # Calculate score (0-100)
    score = min(int((demo_features / total_features) * 100 + core_features * 20), 100)
    
    if score >= 80:
        status = "ready"
    elif score >= 60:
        status = "partial"
    else:
        status = "critical"
    
    details = f"{demo_features}/{total_features} demo-relevant features, {core_features} MUST HAVE features"
    
    return {"score": score, "status": status, "details": details}


def _calculate_testing_status(features, evidence) -> Dict[str, Any]:
    """Calculate testing status."""
    total_features = len(features)
    if total_features == 0:
        return {"status": "not_started", "coverage": 0, "details": "No features to test"}
    
    # Count features with test evidence
    tested_features = 0
    for f in features:
        title = f.get("title", "").lower()
        # Check if there's test evidence
        for ev in evidence:
            if "test" in ev.get("description", "").lower() or "pass" in ev.get("description", "").lower():
                tested_features += 1
                break
    
    coverage = int((tested_features / total_features) * 100) if total_features > 0 else 0
    
    if coverage >= 80:
        status = "complete"
    elif coverage >= 50:
        status = "partial"
    else:
        status = "not_started"
    
    return {
        "status": status,
        "coverage": coverage,
        "details": f"{tested_features}/{total_features} features have test evidence",
    }


def _find_blockers(risks, features) -> List[Dict[str, Any]]:
    """Find current blockers."""
    blockers = []
    
    for risk in risks:
        if risk.get("status") == "active":
            blockers.append({
                "id": risk.get("id"),
                "category": risk.get("category"),
                "description": risk.get("description"),
                "severity": risk.get("severity"),
                " mitigation": risk.get("mitigation"),
            })
    
    # Also check features with high risk or pending status
    for feature in features:
        if feature.get("status") == "pending" and feature.get("risk", "").lower() in ["high", "critical"]:
            blockers.append({
                "id": None,
                "category": "feature_status",
                "description": f"Feature '{feature.get('title')}' is pending with high risk",
                "severity": "high",
                "mitigation": "Re-evaluate feature necessity or mitigate risks",
            })
    
    return blockers


def _find_critical_bugs(risks) -> List[Dict[str, Any]]:
    """Find critical bugs."""
    critical_bugs = []
    
    for risk in risks:
        if risk.get("severity") == "critical":
            critical_bugs.append({
                "id": risk.get("id"),
                "category": risk.get("category"),
                "description": risk.get("description"),
                "mitigation": risk.get("mitigation"),
                "probability": risk.get("probability"),
            })
    
    return critical_bugs


def _find_unfinished_core_features(features) -> List[Dict[str, Any]]:
    """Find unfinished MUST HAVE features."""
    unfinished = []
    
    for feature in features:
        priority = feature.get("priority", "").lower()
        status = feature.get("status", "").lower()
        
        # Check if it's a MUST HAVE and unfinished
        is_must_have = any(kw in priority for kw in ["must", "core", "essential", "primary"])
        is_unfinished = status in ["pending", "in_progress", "not_started"]
        
        if is_must_have and is_unfinished:
            unfinished.append({
                "title": feature.get("title"),
                "priority": feature.get("priority"),
                "status": feature.get("status"),
                "risk": feature.get("risk"),
            })
    
    return unfinished


def _find_milestones(risks, decisions) -> List[Dict[str, Any]]:
    """Find remaining milestones."""
    milestones = []
    
    # From decisions
    for decision in decisions:
        if "milestone" in decision.get("decision", "").lower() or "phase" in decision.get("decision", "").lower():
            milestones.append({
                "id": decision.get("id"),
                "decision": decision.get("decision"),
                "date": decision.get("date"),
            })
    
    # From risks with timelines
    for risk in risks:
        if risk.get("probability") in ["high", "medium"] and not risk.get("status") == "completed":
            milestones.append({
                "id": risk.get("id"),
                "category": risk.get("category"),
                "description": risk.get("description"),
                "mitigation": risk.get("mitigation"),
            })
    
    return milestones


def _determine_next_best_action(features, risks, evidence, demo_readiness) -> Dict[str, Any]:
    """Determine the most important task based on actual project state."""
    # Priority order:
    # 1. Complete MUST HAVE features
    # 2. Fix critical blockers
    # 3. Implement demo-impact features
    # 4. Address high-risk items
    # 5. Add test coverage
    
    # Check for MUST HAVE features that are pending
    must_have_pending = []
    for feature in features:
        priority = feature.get("priority", "").lower()
        status = feature.get("status", "").lower()
        if any(kw in priority for kw in ["must", "core", "essential", "primary"]) and status in ["pending", "in_progress"]:
            must_have_pending.append(feature.get("title"))
    
    if must_have_pending:
        return {
            "action": "Complete pending MUST HAVE features",
            "details": f"Focus on: {', '.join(must_have_pending[:3])}",
            "priority": "high",
            "estimated_impact": "critical",
        }
    
    # Check for critical blockers
    critical_risks = [r for r in risks if r.get("severity") == "critical" and r.get("status") == "active"]
    if critical_risks:
        return {
            "action": "Resolve critical blockers",
            "details": f"Address {len(critical_risks)} critical risk(s)",
            "priority": "high",
            "estimated_impact": "critical",
        }
    
    # Check for demo-impact features
    demo_features = [f for f in features if "demo" in f.get("title", "").lower()]
    if demo_features:
        return {
            "action": "Implement demo-impact features",
            "details": f"Focus on: {', '.join([f.get('title') for f in demo_features[:3]])}",
            "priority": "high",
            "estimated_impact": "high",
        }
    
    # Check for high-risk items
    high_risks = [r for r in risks if r.get("severity") in ["high", "critical"] and r.get("status") == "active"]
    if high_risks:
        return {
            "action": "Address high-risk items",
            "details": f"Mitigate {len(high_risks)} high-risk item(s)",
            "priority": "medium",
            "estimated_impact": "medium",
        }
    
    # Default: add test coverage
    return {
        "action": "Add test coverage for core features",
        "details": "Improve testing confidence before demo",
        "priority": "medium",
        "estimated_impact": "medium",
    }


def _recommend_features_to_remove(features, risks) -> List[str]:
    """Recommend features that should be removed."""
    to_remove = []
    
    for feature in features:
        # Remove features with very high risk and low priority
        priority = feature.get("priority", "").lower()
        risk = feature.get("risk", "").lower()
        
        if "nice to have" in priority and ("high" in risk or "critical" in risk):
            to_remove.append(feature.get("title"))
    
    # Also remove features that duplicate others
    titles = [f.get("title", "").lower() for f in features]
    seen = set()
    duplicates = []
    for title in titles:
        if title in seen:
            duplicates.append(title)
        seen.add(title)
    
    return duplicates


def _check_scope_creep(features, risks) -> str:
    """Check for scope creep warnings."""
    feature_count = len(features)
    high_risk_count = sum(1 for r in risks if r.get("severity") in ["high", "critical"])
    
    if feature_count > 10 and high_risk_count > 3:
        return "⚠ WARNING: Scope creep detected - 10+ features with 3+ high/critical risks. " \
               "Consider prioritizing MUST HAVE features and deferring others."
    elif feature_count > 7:
        return "⚠ Moderate scope - consider prioritizing core features."
    return "✓ Scope well-managed"


def _generate_ai_recommendations(features, risks, evidence) -> List[str]:
    """Generate AI recommendations based on project state."""
    recommendations = []
    
    # Count feature priorities
    must_have = sum(1 for f in features if "must have" in f.get("priority", "").lower())
    should_have = sum(1 for f in features if "should have" in f.get("priority", "").lower())
    nice_to_have = sum(1 for f in features if "nice to have" in f.get("priority", "").lower())
    
    if must_have == 0:
        recommendations.append("Identify and prioritize MUST HAVE features for core functionality")
    
    if len(features) > 0 and must_have / len(features) < 0.4:
        recommendations.append("Focus on core functionality - too many optional features for hackathon timeline")
    
    # Check risks
    high_risks = sum(1 for r in risks if r.get("severity") in ["high", "critical"])
    if high_risks > 2:
        recommendations.append("Address high-priority risks before adding new features")
    
    # Check testing
    test_related = [e for e in evidence if "test" in e.get("type", "").lower()]
    if len(test_related) < len(features) * 0.5:
        recommendations.append("Increase test coverage before demo")
    
    return recommendations


def deactivate_hackathon_mode(project_id: int) -> Dict[str, Any]:
    """Deactivate Hackathon Mode and provide summary."""
    from Tools.sih_project_manager import SIHProjectManager
    manager = SIHProjectManager()
    
    project = manager.select_project(project_id)
    if not project:
        manager.close()
        return {"error": f"Project ID {project_id} not found"}
    
    # Get current status
    ideas = manager.list_ideas(project_id)
    features = manager.list_features(project_id)
    risks = manager.list_risks(project_id)
    
    summary = {
        "project_name": project.get("project_name", "Unknown"),
        "ideas_count": len(ideas),
        "features_count": len(features),
        "risks_count": len(risks),
        "hackathon_mode_activated": False,
        "summary": "Hackathon mode deactivated. Project data preserved.",
    }
    
    manager.close()
    return summary