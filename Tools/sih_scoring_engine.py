"""SIH Scoring Engine - Evaluates SIH projects across multiple criteria.

Provides scores, reasons, evidence, weaknesses, and recommended improvements
for each category. Generates overall weighted score, confidence level, top
strengths, top weaknesses, and top 3 actions to improve the score.

Weights are configurable and can be updated later.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from Tools.sih_project_manager import SIHProjectManager

logger = logging.getLogger(__name__)

# Default configurable weights for scoring categories
DEFAULT_WEIGHTS = {
    "novelty": 0.15,
    "technical_complexity": 0.15,
    "feasibility": 0.20,
    "practicability": 0.10,
    "scalability": 0.10,
    "sustainability": 0.05,
    "social_impact": 0.10,
    "ux": 0.05,
    "accessibility": 0.05,
    "security": 0.05,
    "cost_effectiveness": 0.03,
    "technical_implementation": 0.02,
    "deployment_readiness": 0.02,
    "future_scope": 0.03,
}

# Score range 1-10 with descriptions
SCORE_DESCRIPTIONS = {
    1: "Very Poor",
    2: "Poor",
    3: "Below Average",
    4: "Fair",
    5: "Average",
    6: "Good",
    7: "Very Good",
    8: "Excellent",
    9: "Outstanding",
    10: "Exceptional"
}


def set_weights(weights: Dict[str, float]) -> None:
    """Configure scoring weights. Weights should sum to approximately 1.0."""
    global DEFAULT_WEIGHTS
    # Validate weights sum
    total = sum(weights.values())
    if abs(total - 1.0) > 0.1:
        logger.warning(f"Weights sum to {total}, expected ~1.0. Adjusting...")
    DEFAULT_WEIGHTS = weights


def get_weights() -> Dict[str, float]:
    """Get current scoring weights."""
    return DEFAULT_WEIGHTS.copy()


def calculate_category_score(project_id: int, category: str, weights: Dict[str, float] = None) -> Dict[str, Any]:
    """
    Calculate a score for a specific category for a project.
    
    Args:
        project_id: The SIH project ID
        category: The scoring category
        weights: Optional custom weights (uses DEFAULT_WEIGHTS if None)
    
    Returns:
        Dict with score, reason, evidence, weakness, and recommended improvement
    """
    weights = weights or DEFAULT_WEIGHTS
    manager = SIHProjectManager()
    
    # Get project data
    project = manager.select_project(project_id)
    if not project:
        manager.close()
        return {"error": f"Project ID {project_id} not found"}
    
    # Extract project data for scoring
    ideas = manager.list_ideas(project_id)
    features = manager.list_features(project_id)
    risks = manager.list_risks(project_id)
    research = manager.list_research(project_id)
    evidence = manager.list_evidence(project_id)
    
    # Initialize score components
    score_components = {}
    reasons = {}
    evidence_list = []
    weaknesses = []
    improvements = []
    
    # --- Novelty (15%) ---
    if category == "novelty" or category is None:
        novelty_score = _score_novelty(project, ideas, research, evidence)
        score_components["novelty"] = novelty_score
        reasons["novelty"] = _reason_novelty(novelty_score)
        evidence_list.extend(_evidence_novelty(research, evidence))
        if novelty_score < 5:
            weaknesses.append("Low novelty - need to identify unique aspects")
            improvements.append("Conduct thorough innovation analysis and literature review")
    
    # --- Technical Complexity (15%) ---
    if category == "technical_complexity" or category is None:
        tech_score = _score_technical_complexity(project, features, risks)
        score_components["technical_complexity"] = tech_score
        reasons["technical_complexity"] = _reason_technical_complexity(tech_score)
        if tech_score < 5:
            weaknesses.append("High technical complexity - need feasibility study")
            improvements.append("Perform technical feasibility assessment with prototype")
    
    # --- Feasibility (20%) ---
    if category == "feasibility" or category is None:
        feat_score = _score_feasibility(project, ideas, features)
        score_components["feasibility"] = feat_score
        reasons["feasibility"] = _reason_feasibility(feat_score)
        if feat_score < 5:
            weaknesses.append("Feasibility concerns - need pilot validation")
            improvements.append("Build MVP and test with real users")
    
    # --- Practicability (10%) ---
    if category == "practicability" or category is None:
        prac_score = _score_practicability(project, ideas, features)
        score_components["practicability"] = prac_score
        reasons["practicability"] = _reason_practicability(prac_score)
    
    # --- Scalability (10%) ---
    if category == "scalability" or category is None:
        scal_score = _score_scalability(project, ideas, evidence)
        score_components["scalability"] = scal_score
        reasons["scalability"] = _reason_scalability(scal_score)
        if scal_score < 5:
            weaknesses.append("Scalability concerns - need architecture for growth")
            improvements.append("Design modular architecture with horizontal scaling")
    
    # --- Sustainability (5%) ---
    if category == "sustainability" or category is None:
        sust_score = _score_sustainability(project, evidence)
        score_components["sustainability"] = sust_score
        reasons["sustainability"] = _reason_sustainability(sust_score)
    
    # --- Social Impact (10%) ---
    if category == "social_impact" or category is None:
        impact_score = _score_social_impact(project, evidence)
        score_components["social_impact"] = impact_score
        reasons["social_impact"] = _reason_social_impact(impact_score)
    
    # --- UX (5%) ---
    if category == "ux" or category is None:
        ux_score = _score_ux(project, features)
        score_components["ux"] = ux_score
        reasons["ux"] = _reason_ux(ux_score)
    
    # --- Accessibility (5%) ---
    if category == "accessibility" or category is None:
        acc_score = _score_accessibility(project, evidence)
        score_components["accessibility"] = acc_score
        reasons["accessibility"] = _reason_accessibility(acc_score)
    
    # --- Security (5%) ---
    if category == "security" or category is None:
        sec_score = _score_security(project, evidence)
        score_components["security"] = sec_score
        reasons["security"] = _reason_security(sec_score)
    
    # --- Cost Effectiveness (3%) ---
    if category == "cost_effectiveness" or category is None:
        cost_score = _score_cost_effectiveness(project, evidence)
        score_components["cost_effectiveness"] = cost_score
        reasons["cost_effectiveness"] = _reason_cost_effectiveness(cost_score)
    
    # --- Technical Implementation (2%) ---
    if category == "technical_implementation" or category is None:
        tech_imp_score = _score_technical_implementation(project, features)
        score_components["technical_implementation"] = tech_imp_score
        reasons["technical_implementation"] = _reason_technical_implementation(tech_imp_score)
    
    # --- Deployment Readiness (2%) ---
    if category == "deployment_readiness" or category is None:
        deploy_score = _score_deployment_readiness(project, evidence)
        score_components["deployment_readiness"] = deploy_score
        reasons["deployment_readiness"] = _reason_deployment_readiness(deploy_score)
    
    # --- Future Scope (3%) ---
    if category == "future_scope" or category is None:
        future_score = _score_future_scope(project, ideas)
        score_components["future_scope"] = future_score
        reasons["future_scope"] = _reason_future_scope(future_score)
    
    # Calculate weighted total score
    total_score = sum(
        score_components.get(cat, 5) * weight 
        for cat, weight in weights.items()
    )
    
    # Round and determine description
    total_score = round(total_score, 2)
    score_desc = SCORE_DESCRIPTIONS.get(round(total_score), "Unknown")
    
    # Count weaknesses and improvements
    all_weaknesses = []
    all_improvements = []
    for comp_key in score_components:
        if comp_key in score_components and score_components[comp_key] < 5:
            # Add category-specific weakness
            cat_lower = comp_key.lower()
            if cat_lower in ["novelty", "technical_complexity", "feasibility", "scalability"]:
                weaknesses.append(f"{comp_key}: score {score_components[comp_key]}/10 indicates need for improvement")
    
    result = {
        "category": category or "overall",
        "score": total_score,
        "score_description": score_desc,
        "category_breakdown": score_components,
        "weights_used": weights,
        "reason": " | ".join([reasons.get(cat, "") for cat in weights.keys() if cat in score_components]),
        "evidence": evidence_list,
        "weaknesses": list(set(weaknesses)),
        "improvements": list(set(improvements)),
        "confidence": _calculate_confidence(project, ideas, research, evidence),
        "top_strengths": _get_top_strengths(score_components),
        "top_weaknesses": weaknesses,
        "top_3_actions": _get_top_3_actions(weaknesses, improvements),
    }
    
    manager.close()
    return result


def _score_novelty(project, ideas, research, evidence) -> float:
    """Score novelty (1-10)."""
    score = 5  # base
    # Check ideas for uniqueness
    if ideas:
        score += 1
    # Check research for existing solutions
    if research:
        score -= 1  # existing research may reduce novelty
    # Check evidence for innovation
    for ev in evidence:
        if ev.get("type") == "innovation":
            score += 1
    return min(max(score, 1), 10)


def _reason_novelty(score: float) -> str:
    if score >= 8:
        return "High novelty with unique approach"
    elif score >= 6:
        return "Moderate novelty, builds on existing ideas"
    elif score >= 4:
        return "Low novelty, similar to existing solutions"
    else:
        return "Very low novelty - significant innovation needed"


def _evidence_novelty(research, evidence) -> List[str]:
    results = []
    if research:
        results.append(f"{len(research)} research sources reviewed")
    for ev in evidence:
        if ev.get("type") == "innovation":
            results.append(f"Innovation evidence: {ev.get('description', '')[:100]}")
    return results


def _score_technical_complexity(project, features, risks) -> float:
    """Score technical complexity (1-10, where high score = low complexity)."""
    base = 5
    if features:
        base += 1
    if risks and len(risks) > 3:
        base -= 1
    return min(max(base, 1), 10)


def _reason_technical_complexity(score: float) -> str:
    if score >= 8:
        return "Low technical complexity, straightforward implementation"
    elif score >= 6:
        return "Moderate technical complexity, manageable with expertise"
    elif score >= 4:
        return "High technical complexity, requires specialized skills"
    else:
        return "Very high technical complexity - significant research needed"


def _score_feasibility(project, ideas, features) -> float:
    """Score feasibility (1-10, where high = highly feasible)."""
    base = 5
    if ideas:
        base += 1  # ideas indicate planning
    if features:
        base += 1  # features show planning
    # Reduce if many open risks are recorded for this project
    try:
        mgr = SIHProjectManager()
        risks = mgr.list_risks(project["id"])
        mgr.close()
        if len(risks) > 5:
            base -= 2
    except Exception:
        pass
    return min(max(base, 1), 10)


def _reason_feasibility(score: float) -> str:
    if score >= 8:
        return "High feasibility, realistic timeline and resources"
    elif score >= 6:
        return "Good feasibility with proper planning"
    elif score >= 4:
        return "Moderate feasibility, requires careful assessment"
    else:
        return "Low feasibility - significant reassessment needed"


def _score_practicability(project, ideas, features) -> float:
    """Score practicability (1-10)."""
    base = 5
    if ideas:
        base += 1
    return min(max(base, 1), 10)


def _reason_practicability(score: float) -> str:
    if score >= 8:
        return "High practicability, easily implementable"
    elif score >= 6:
        return "Good practicability with available resources"
    elif score >= 4:
        return "Moderate practicability, some constraints"
    else:
        return "Low practicability, significant barriers"


def _score_scalability(project, ideas, evidence) -> float:
    """Score scalability (1-10)."""
    base = 5
    for ev in evidence:
        if ev.get("type") == "architecture":
            base += 1
    return min(max(base, 1), 10)


def _reason_scalability(score: float) -> str:
    if score >= 8:
        return "Excellent scalability designed into architecture"
    elif score >= 6:
        return "Good scalability with minor modifications needed"
    elif score >= 4:
        return "Limited scalability, requires redesign for growth"
    else:
        return "Poor scalability, will need architectural overhaul"


def _score_sustainability(project, evidence) -> float:
    """Score sustainability (1-10)."""
    base = 5
    for ev in evidence:
        if ev.get("type") == "sustainability":
            base += 1
    return min(max(base, 1), 10)


def _reason_sustainability(score: float) -> str:
    if score >= 8:
        return "High sustainability, long-term viable"
    elif score >= 6:
        return "Good sustainability with some conditions"
    elif score >= 4:
        return "Moderate sustainability, requires ongoing support"
    else:
        return "Low sustainability, needs sustainability plan"


def _score_social_impact(project, evidence) -> float:
    """Score social impact (1-10)."""
    base = 5
    # Check problem statement for impact areas
    problem = project.get("problem_statement", "") if False else ""
    if problem:
        base += 1
    for ev in evidence:
        if ev.get("type") == "impact":
            base += 1
    return min(max(base, 1), 10)


def _reason_social_impact(score: float) -> str:
    if score >= 8:
        return "High social impact, benefits significant population"
    elif score >= 6:
        return "Good social impact, benefits target group"
    elif score >= 4:
        return "Moderate social impact, limited scope"
    else:
        return "Low social impact, needs clearer benefit analysis"


def _score_ux(project, features) -> float:
    """Score UX (1-10)."""
    base = 5
    if features:
        # Count features that mention UX
        ux_features = [f for f in features if "ux" in f.get("title", "").lower() or "interface" in f.get("title", "").lower()]
        base += len(ux_features)
    return min(max(base, 1), 10)


def _reason_ux(score: float) -> str:
    if score >= 8:
        return "Excellent UX, intuitive and user-friendly"
    elif score >= 6:
        return "Good UX, usable with minor improvements"
    elif score >= 4:
        return "Adequate UX, functional but needs refinement"
    else:
        return "Poor UX, significant usability issues"


def _score_accessibility(project, evidence) -> float:
    """Score accessibility (1-10)."""
    base = 5
    for ev in evidence:
        if ev.get("type") == "accessibility":
            base += 1
    return min(max(base, 1), 10)


def _reason_accessibility(score: float) -> str:
    if score >= 8:
        return "Excellent accessibility, meets all standards"
    elif score >= 6:
        return "Good accessibility, meets most requirements"
    elif score >= 4:
        return "Moderate accessibility, some gaps"
    else:
        return "Low accessibility, needs accessibility audit"


def _score_security(project, evidence) -> float:
    """Score security (1-10)."""
    base = 5
    for ev in evidence:
        if ev.get("type") == "security":
            base += 1
    return min(max(base, 1), 10)


def _reason_security(score: float) -> str:
    if score >= 8:
        return "Strong security, comprehensive measures"
    elif score >= 6:
        return "Adequate security, basic measures in place"
    elif score >= 4:
        return "Moderate security, some gaps to address"
    else:
        return "Weak security, needs immediate attention"


def _score_cost_effectiveness(project, evidence) -> float:
    """Score cost effectiveness (1-10, higher = more cost-effective)."""
    base = 5
    for ev in evidence:
        if ev.get("type") == "cost":
            base += 1
    return min(max(base, 1), 10)


def _reason_cost_effectiveness(score: float) -> str:
    if score >= 8:
        return "Excellent cost-effectiveness, low cost high impact"
    elif score >= 6:
        return "Good cost-effectiveness, reasonable cost for impact"
    elif score >= 4:
        return "Moderate cost-effectiveness, acceptable costs"
    else:
        return "Low cost-effectiveness, high cost for limited impact"


def _score_technical_implementation(project, features) -> float:
    """Score technical implementation (1-10)."""
    base = 5
    if features:
        base += 1
    return min(max(base, 1), 10)


def _reason_technical_implementation(score: float) -> str:
    if score >= 8:
        return "Strong technical implementation, well-documented"
    elif score >= 6:
        return "Good technical implementation, some gaps"
    elif score >= 4:
        return "Adequate implementation, needs improvement"
    else:
        return "Poor implementation, needs redesign"


def _score_deployment_readiness(project, evidence) -> float:
    """Score deployment readiness (1-10)."""
    base = 5
    for ev in evidence:
        if ev.get("type") == "deployment":
            base += 1
    return min(max(base, 1), 10)


def _reason_deployment_readiness(score: float) -> str:
    if score >= 8:
        return "Fully ready for deployment"
    elif score >= 6:
        return "Mostly ready, minor prerequisites"
    elif score >= 4:
        return "Partially ready, needs prerequisites addressed"
    else:
        return "Not ready, significant prerequisites needed"


def _score_future_scope(project, ideas) -> float:
    """Score future scope (1-10, higher = more future scope)."""
    base = 5
    if ideas:
        base += 1  # ideas indicate planned future work
    return min(max(base, 1), 10)


def _reason_future_scope(score: float) -> str:
    if score >= 8:
        return "Well-defined future scope, clear roadmap"
    elif score >= 6:
        return "Good future scope, some planned features"
    elif score >= 4:
        return "Limited future scope, focus on core"
    else:
        return "Very limited future scope, consider expansion"


def _calculate_confidence(project, ideas, research, evidence) -> float:
    """Calculate confidence level (0-1) based on data availability."""
    factors = 0
    total = 0
    
    if project:
        total += 1
    if ideas:
        total += 1
        factors += len(ideas)
    if research:
        total += 1
        factors += len(research)
    if evidence:
        total += 1
        factors += len(evidence)
    
    if total == 0:
        return 0.5  # default moderate confidence
    
    return min(factors / (total * 2), 1.0)


def _get_top_strengths(score_components: Dict[str, float]) -> List[str]:
    """Get top strengths from score components."""
    strengths = []
    for cat, score in score_components.items():
        if score >= 7:
            strengths.append(f"{cat}: {SCORE_DESCRIPTIONS.get(round(score), '')}")
    return strengths


def _get_top_3_actions(weaknesses: List[str], improvements: List[str]) -> List[str]:
    """Get top 3 actions from weaknesses and improvements."""
    all_actions = weaknesses + improvements
    # Remove duplicates and return top 3
    seen = set()
    unique = []
    for a in all_actions:
        if a not in seen:
            seen.add(a)
            unique.append(a)
    return unique[:3]


def generate_scorecard(project_id: int, weights: Dict[str, float] = None) -> Dict[str, Any]:
    """
    Generate a complete scorecard for a SIH project.
    
    Args:
        project_id: The SIH project ID
        weights: Optional custom weights
        
    Returns:
        Complete scorecard dict
    """
    result = calculate_category_score(project_id, None, weights)
    
    if "error" in result:
        return result

    # Add overall summary from real project data
    mgr = SIHProjectManager()
    try:
        stats = mgr.get_project_stats(project_id)
    finally:
        mgr.close()

    result["summary"] = {
        "overall_score": result["score"],
        "overall_description": result["score_description"],
        "num_ideas": stats.get("ideas", 0),
        "num_features": stats.get("features", 0),
        "num_risks": stats.get("risks", 0),
        "num_evidence": stats.get("evidence", 0),
        "weights": weights or DEFAULT_WEIGHTS,
        "disclaimer": (
            "This is an internal readiness estimate computed from recorded project data — "
            "NOT an official SIH score."
        ),
    }
    
    return result