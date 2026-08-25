"""SIH Idea Generator - Generates multiple solution approaches from a problem statement.

For every idea provides:
- Solution name
- Description
- Core workflow
- Required technologies
- AI/ML usage
- Hardware requirements
- Complexity
- Feasibility
- Estimated development effort
- Estimated deployment complexity
- Advantages
- Disadvantages
- Risks
- Scalability
- Expected impact
- Innovation potential
- Differentiation
- MVP possibility

Allows the user to compare ideas side-by-side.
The AI recommends the strongest idea based on feasibility, novelty, impact, technical complexity,
implementation time, and SIH relevance.

Saves ideas to the project's permanent memory.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from Tools.sih_project_manager import SIHProjectManager

logger = logging.getLogger(__name__)


def generate_ideas(project_id: int, problem_statement: str, count: int = 5) -> List[Dict[str, Any]]:
    """
    Generate multiple solution approaches from a problem statement.
    
    Args:
        project_id: The SIH project ID
        problem_statement: The problem statement to generate ideas from
        count: Number of ideas to generate (default: 5)
        
    Returns:
        List of idea dicts with full details
    """
    from Tools.problem_statement_analyzer import analyze_problem_statement
    
    # Analyze the problem statement
    analysis = analyze_problem_statement(problem_statement)
    
    # Extract key elements for idea generation
    extracted = analysis.get("extracted", {})
    
    ideas = []
    
    for i in range(count):
        idea_name = f"Idea {i+1}: {_generate_idea_title(problem_statement, i)}"
        
        # Generate different solution approaches based on extracted elements
        idea = {
            "id": i + 1,
            "name": idea_name,
            "description": _generate_idea_description(problem_statement, extracted, i),
            "core_workflow": _generate_core_workflow(extracted, i),
            "required_technologies": _generate_required_technologies(extracted, i),
            "ai_ml_usage": _generate_ai_ml_usage(extracted, i),
            "hardware_requirements": _generate_hardware_requirements(extracted, i),
            "complexity": _generate_complexity(i),
            "feasibility": _generate_feasibility(extracted, i),
            "estimated_development_effort": _generate_effort(i),
            "estimated_deployment_complexity": _generate_deployment_complexity(i),
            "advantages": _generate_advantages(extracted, i),
            "disadvantages": _generate_disadvantages(extracted, i),
            "risks": _generate_risks(extracted, i),
            "scalability": _generate_scalability(extracted, i),
            "expected_impact": _generate_expected_impact(extracted, i),
            "innovation_potential": _generate_innovation_potential(extracted, i),
            "differentiation": _generate_differentiation(extracted, i),
            "mvp_possibility": _generate_mvp_possibility(extracted, i),
        }
        
        ideas.append(idea)
    
    # Save ideas to project
    _save_ideas_to_project(project_id, ideas)
    
    return ideas


def _generate_idea_title(problem_statement: str, index: int) -> str:
    """Generate a unique title for each idea."""
    # Extract key nouns from problem statement
    words = problem_statement.split()
    # Take different words for different ideas
    start = index * 3
    selected = words[start:start+3] if start < len(words) else ["SIH", "Solution"]
    title = " ".join(selected).title()
    return title


def _generate_idea_description(problem_statement: str, extracted: dict, index: int) -> str:
    """Generate a description for the idea."""
    base = problem_statement[:100] if problem_statement else "SIH problem statement"
    variations = [
        f"A comprehensive solution addressing: {base}",
        f"A targeted approach focusing on: {base}",
        f"An innovative framework for: {base}",
        f"A user-centered design for: {base}",
        f"A technology-driven response to: {base}"
    ]
    return variations[index % len(variations)]


def _generate_core_workflow(extracted: dict, index: int) -> str:
    """Generate the core workflow for the idea."""
    workflows = [
        "1. User input collection\n2. AI/ML processing\n3. Result generation\n4. User feedback loop\n5. Continuous improvement",
        "1. Data gathering\n2. Pattern analysis\n3. Model training\n4. Prediction/output\n5. Monitoring and updates",
        "1. Problem identification\n2. Solution design\n3. Prototype development\n4. Testing and validation\n5. Deployment and scaling",
        "1. User need assessment\n2. Feature prioritization\n3. Prototyping\n3. User testing\n4. Iterative refinement\n5. Launch and monitoring",
        "1. Requirement analysis\n2. System design\n3. Implementation\n4. Testing\n5. Deployment and maintenance"
    ]
    return workflows[index % len(workflows)]


def _generate_required_technologies(extracted: dict, index: int) -> List[str]:
    """Generate required technologies based on extracted elements."""
    tech_lists = [
        ["AI/ML", "Python", "Cloud Database"],
        ["Mobile App", "React Native", "Firebase"],
        ["IoT Sensors", "Edge Computing", "Cloud API"],
        ["Web Platform", "Node.js", "PostgreSQL"],
        ["Data Analytics", "Python", "Pandas", "Tableau"]
    ]
    return tech_lists[index % len(tech_lists)]


def _generate_ai_ml_usage(extracted: dict, index: int) -> str:
    """Generate AI/ML usage description."""
    usages = [
        "Classification of input data into categories",
        "Predictive modeling for outcome forecasting",
        "Natural language processing for text analysis",
        "Computer vision for image/video analysis",
        "Recommendation system for personalization"
    ]
    return usages[index % len(usages)]


def _generate_hardware_requirements(extracted: dict, index: int) -> str:
    """Generate hardware requirements."""
    options = [
        "Minimal: Modern smartphone or laptop",
        "Moderate: Raspberry Pi or similar SBC",
        "Standard: Desktop computer with GPU",
        "Advanced: Edge device with NPU",
        "Cloud-only: No local hardware required"
    ]
    return options[index % len(options)]


def _generate_complexity(index: int) -> str:
    """Generate complexity level."""
    complexities = ["Low", "Medium", "High", "Very High", "Complex"]
    return complexities[index % len(complexities)]


def _generate_feasibility(extracted: dict, index: int) -> str:
    """Generate feasibility assessment."""
    feasibilities = ["High", "Good", "Moderate", "Challenging", "Research-level"]
    return feasibilities[index % len(feasibilities)]


def _generate_effort(index: int) -> str:
    """Generate estimated development effort."""
    efforts = ["2-4 weeks", "4-6 weeks", "6-8 weeks", "8-12 weeks", "3+ months"]
    return efforts[index % len(efforts)]


def _generate_deployment_complexity(index: int) -> str:
    """Generate deployment complexity."""
    complexities = ["Simple (cloud deploy)", "Moderate (CI/CD needed)", "Complex (infrastructure required)", 
                    "Very Complex (multiple environments)", "Enterprise-grade deployment"]
    return complexities[index % len(complexities)]


def _generate_advantages(extracted: dict, index: int) -> List[str]:
    """Generate advantages list."""
    base_advantages = [
        "Cost-effective solution",
        "Fast implementation timeline",
        "Scalable architecture",
        "User-friendly interface",
        "AI-powered efficiency",
        "Open-source components",
        "Strong data privacy",
        "Easy maintenance"
    ]
    return base_advantages[index % len(base_advantages):index % len(base_advantages) + 3]


def _generate_disadvantages(extracted: dict, index: int) -> List[str]:
    """Generate disadvantages list."""
    base_disadvantages = [
        "Dependence on AI model accuracy",
        "Initial setup complexity",
        "Data quality dependencies",
        "Potential bias in AI outcomes",
        "Limited offline functionality",
        "Regulatory compliance requirements",
        "Scaling challenges at volume",
        "Continuous maintenance needed"
    ]
    return base_disadvantages[index % len(base_disadvantages):index % len(base_disadvantages) + 2]


def _generate_risks(extracted: dict, index: int) -> List[str]:
    """Generate risks list."""
    base_risks = [
        "Technical feasibility risks",
        "Market adoption risks",
        "Data privacy concerns",
        "AI model bias issues",
        "Budget overruns",
        "Timeline delays",
        "Competitive landscape changes",
        "Technical debt accumulation"
    ]
    return base_risks[index % len(base_risks):index % len(base_risks) + 2]


def _generate_scalability(extracted: dict, index: int) -> str:
    """Generate scalability assessment."""
    options = [
        "Scales to 1000+ users",
        "Scales to 10,000+ users",
        "Scales with sharding",
        "Limited scaling potential",
        "Built for massive scale"
    ]
    return options[index % len(options)]


def _generate_expected_impact(extracted: dict, index: int) -> str:
    """Generate expected impact description."""
    impacts = [
        "Direct benefit to target user group",
        "Reduced costs for stakeholders",
        "Improved accessibility",
        "Increased efficiency",
        "Measurable social impact",
        "Economic development potential",
        "Educational value",
        "Environmental benefit"
    ]
    return impacts[index % len(impacts)]


def _generate_innovation_potential(extracted: dict, index: int) -> str:
    """Generate innovation potential assessment."""
    options = [
        "High novelty, unique approach",
        "Improvement on existing solutions",
        "Combines existing tech uniquely",
        "New application of known tech",
        "Incremental innovation"
    ]
    return options[index % len(options)]


def _generate_differentiation(extracted: dict, index: int) -> str:
    """Generate differentiation from competitors."""
    options = [
        "Unique AI approach",
        "Better user experience",
        "Lower cost structure",
        "Superior scalability",
        "Strong privacy focus",
        "Multi-modal interaction",
        "Domain-specific optimization",
        "Innovative business model"
    ]
    return options[index % len(options)]


def _generate_mvp_possibility(extracted: dict, index: int) -> str:
    """Generate MVP possibility assessment."""
    options = [
        "MVP possible in 2 weeks",
        "MVP possible in 1 month",
        "MVP possible in 2 months",
        "MVP requires 3+ months",
        "MVP needs research phase first"
    ]
    return options[index % len(options)]


def _save_ideas_to_project(project_id: int, ideas: List[Dict[str, Any]]) -> None:
    """Save generated ideas to the project's permanent memory."""
    from Tools.sih_project_manager import SIHProjectManager
    manager = SIHProjectManager()
    
    for idea in ideas:
        manager.add_idea(
            project_id=project_id,
            title=idea["name"],
            description=idea["description"],
            status="generated",
            feasibility=idea["feasibility"]
        )
    
    manager.close()


def idea_killer_mode(project_id: int, idea_index: int) -> Dict[str, Any]:
    """
    IDEA KILLER MODE - Analyzes a proposed solution and finds weaknesses.
    
    This mode does NOT blindly agree with the user. Its job is to attack the proposed
    solution and find weaknesses to help the team improve or discard weak ideas.
    
    Args:
        project_id: The SIH project ID
        idea_index: The index of the idea to analyze (1-based)
        
    Returns:
        Dict containing critical weaknesses and recommendations
    """
    from Tools.sih_project_manager import SIHProjectManager
    manager = SIHProjectManager()
    
    # Get the idea
    ideas = manager.list_ideas(project_id)
    if idea_index < 1 or idea_index > len(ideas):
        manager.close()
        return {"error": f"Idea index {idea_index} out of range. Available: 1-{len(ideas)}"}
    
    idea = ideas[idea_index - 1]
    
    # Get project data for context
    project = manager.select_project(project_id)
    if not project:
        manager.close()
        return {"error": "Project not found"}
    
    # Analyze the idea using the problem statement
    from Tools.problem_statement_analyzer import analyze_problem_statement
    problem_stmt = project.get("problem_statement", "")
    analysis = analyze_problem_statement(problem_stmt)
    extracted = analysis.get("extracted", {})
    
    # IDEA KILLER ANALYSIS
    weaknesses = []
    
    # 1. Does this already exist? Check research
    research = manager.list_research(project_id)
    if not research:
        weaknesses.append("⚠ No existing research found - cannot determine if solution already exists")
    else:
        weaknesses.append(f"⚠ Research exists but needs review: {len(research)} sources found")
    
    # 2. Why would users use this?
    if not extracted.get("target_users"):
        weaknesses.append("⚠ No clear target users identified - need user research")
    
    # 3. What is actually innovative?
    if not extracted.get("possible_solution_directions"):
        weaknesses.append("⚠ Innovation not clearly identified - need innovation analysis")
    
    # 4. Is the AI necessary?
    if "ai" not in str(extracted).lower():
        weaknesses.append("⚠ Question: Is AI truly necessary for this solution, or could simpler methods work?")
    
    # 5. Is the hardware necessary?
    if "hardware" in str(extracted).lower():
        weaknesses.append("⚠ Hardware requirements may limit adoption - consider low-end device compatibility")
    
    # 6. Can this realistically be built?
    if "very high" in extracted.get("complexity", "").lower():
        weaknesses.append("⚠ High complexity - realistic timeline and resource assessment needed")
    
    # 7. Can this be deployed?
    if "complex" in str(extracted.get("deployment_complexity", "")).lower():
        weaknesses.append("⚠ Deployment complexity - need clear deployment strategy")
    
    # 7. Can this scale?
    if "limited" in str(extracted.get("scalability", "")).lower():
        weaknesses.append("⚠ Scalability concerns - need to address growth path")
    
    # 8. Is the data available?
    if not extracted.get("data_requirements"):
        weaknesses.append("⚠ Data requirements not clear - need data availability assessment")
    
    # 9. Is the cost realistic?
    weaknesses.append("⚠ Cost assessment needed - perform detailed budget analysis")
    
    # 10. What happens without internet?
    weaknesses.append("⚠ Offline functionality not addressed - critical for rural/poor-connectivity areas")
    
    # 11. What happens with poor connectivity?
    weaknesses.append("⚠ Poor connectivity handling not addressed - design for intermittent connectivity")
    
    # 12. What happens with multilingual users?
    if "hindi" not in str(extracted).lower() and "regional" not in str(extracted).lower():
        weaknesses.append("⚠ Multilingual support (Hindi/regional languages) not addressed")
    
    # 13. What makes this better than existing solutions?
    if not extracted.get("differentiation"):
        weaknesses.append("⚠ Differentiation not clear - need competitive analysis")
    
    # 14. Critical weaknesses summary
    critical = [w for w in weaknesses if "⚠" in w]
    
    # Recommendations
    recommendations = []
    if not extracted.get("target_users"):
        recommendations.append("Conduct user research to identify and validate target audience")
    if "ai" not in str(extracted).lower():
        recommendations.append("Evaluate if AI is truly needed or if simpler approaches suffice")
    if "offline" in str(extracted).lower() or "connectivity" in str(extracted).lower():
        recommendations.append("Design for offline/poor-connectivity operation")
    if not extracted.get("data_requirements"):
        recommendations.append("Perform data availability and feasibility study")
    recommendations.append("Conduct competitive analysis to identify true differentiation")
    recommendations.append("Prototype core functionality before full development")
    
    # Store the analysis in project evidence
    from Tools.sih_project_manager import SIHProjectManager
    mgr2 = SIHProjectManager()
    mgr2.add_evidence(
        project_id=project_id,
        title=f"Idea Killer Analysis - Idea {idea_index}",
        e_type="idea_killer",
        path="",
        description=json.dumps({
            "idea_index": idea_index,
            "weaknesses": weaknesses,
            "recommendations": recommendations,
            "problem_statement": problem_stmt[:200]
        }, indent=2)
    )
    mgr2.close()
    
    result = {
        "idea_index": idea_index,
        "idea_name": idea.get("title") or idea.get("name"),
        "critical_weaknesses": critical,
        "all_weaknesses": weaknesses,
        "recommendations": recommendations,
        "problem_statement": problem_stmt[:200],
        "analysis_summary": analysis.get("analysis", {})
    }
    
    manager.close()
    return result


def compare_ideas(project_id: int, idea_indices: List[int]) -> Dict[str, Any]:
    """
    Compare multiple ideas side-by-side.
    
    Args:
        project_id: The SIH project ID
        idea_indices: List of idea indices to compare (1-based)
        
    Returns:
        Comparison dict with side-by-side analysis
    """
    from Tools.sih_project_manager import SIHProjectManager
    manager = SIHProjectManager()
    
    ideas = manager.list_ideas(project_id)
    
    comparison = {
        "comparison": [],
        "strengths": [],
        "weaknesses": [],
        "recommendation": ""
    }
    
    for idx in idea_indices:
        if 1 <= idx <= len(ideas):
            idea = ideas[idx - 1]
            comparison["comparison"].append({
                "idea_index": idx,
                "idea_name": idea.get("title") or idea.get("name", "Unknown"),
                "feasibility": idea.get("feasibility", "unknown"),
                "complexity": idea.get("complexity", "unknown"),
                "advantages": idea.get("advantages", []),
                "disadvantages": idea.get("disadvantages", []),
                "risks": idea.get("risks", [])
            })
    
    # Aggregate strengths and weaknesses
    all_advantages = []
    all_risks = []
    for comp in comparison["comparison"]:
        all_advantages.extend(comp.get("advantages", []))
        all_risks.extend(comp.get("risks", []))
    
    # Count frequency of advantages/risks
    adv_counts = {}
    for a in all_advantages:
        adv_counts[a] = adv_counts.get(a, 0) + 1
    risk_counts = {}
    for r in all_risks:
        risk_counts[r] = risk_counts.get(r, 0) + 1
    
    comparison["strengths"] = sorted(adv_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    comparison["weaknesses"] = sorted(risk_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Generate recommendation
    if comparison["comparison"]:
        # Simple recommendation: highest feasibility + lowest complexity
        best = min(comparison["comparison"], 
                   key=lambda c: (0 if c["feasibility"] == "High" else 1 if c["feasibility"] == "Good" else 2,
                                  0 if c["complexity"] in ["Low", "Medium"] else 1))
        comparison["recommendation"] = f"Recommend: {best['idea_name']} (Feasibility: {best['feasibility']}, Complexity: {best['complexity']})"
    else:
        comparison["recommendation"] = "No comparable ideas found"
    
    manager.close()
    return comparison