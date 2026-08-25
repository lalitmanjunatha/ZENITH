"""SIH Problem Statement Analyzer - Analyzes and extracts structured information from SIH problem statements.

Accepts input via:
- Paste text directly
- Upload document (PDF, DOCX, TXT)
- Import text from various sources

Extracts:
- Problem statement analysis
- Root cause analysis
- Target users and stakeholders
- Existing workflow and limitations
- Required solution specifications
- Expected outcomes and success metrics
- Constraints (technical, regulatory, etc.)
- Technical requirements (hardware, software, AI/ML)
- Data requirements and sources
- Security and privacy requirements
- Accessibility requirements
- Scalability requirements
- Infrastructure requirements
- Possible measurable impact
- Hidden requirements and assumptions
- Risk identification
- Possible solution directions

Output is structured and editable, and the analysis is saved into the project's permanent memory.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def extract_hindi_english_mixed_text(text: str) -> str:
    """Extract and clean text that may be in Hindi/English mixed format."""
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove special characters but preserve Devanagari and English
    text = re.sub(r'[^\w\s\u0900-\u097F\.]', ' ', text)
    return text.strip()


def analyze_problem_statement(text: str) -> Dict[str, Any]:
    """
    Analyze a SIH problem statement and extract structured information.
    
    Args:
        text: The problem statement text to analyze
        
    Returns:
        Dict containing extracted information with analysis
    """
    # Clean and prepare text
    cleaned_text = extract_hindi_english_mixed_text(text)
    
    # Initialize analysis result
    analysis = {
        "raw_text": text,
        "cleaned_text": cleaned_text,
        "timestamp": datetime.now().isoformat(),
        "extracted": {},
        "analysis": {},
        "saved": False
    }
    
    # --- Problem Extraction ---
    # Look for problem-related phrases
    problem_keywords = ["problem", "issue", "challenge", "challenges", "issue", "pain point"]
    problem_found = any(kw in cleaned_text.lower() for kw in problem_keywords)
    
    analysis["extracted"]["problem_identified"] = problem_found
    
    if problem_found:
        # Try to locate the problem sentence
        sentences = cleaned_text.split('.')
        for sentence in sentences:
            if any(kw in sentence.lower() for kw in problem_keywords):
                analysis["extracted"]["problem_statement"] = sentence.strip()
                break
        else:
            analysis["extracted"]["problem_statement"] = cleaned_text[:200] + "..." if len(cleaned_text) > 200 else cleaned_text
    else:
        analysis["extracted"]["problem_statement"] = cleaned_text[:200] + "..." if len(cleaned_text) > 200 else cleaned_text
    
    # --- Root Cause Analysis ---
    root_cause_patterns = [
        r'(because|due to|caused by|reason is)',
        r'(leading to|resulting in|causes)',
        r'(stem from|arise from|originate from)'
    ]
    root_causes = []
    for pattern in root_cause_patterns:
        matches = re.findall(pattern, cleaned_text, re.IGNORECASE)
        root_causes.extend(matches)
    
    analysis["extracted"]["root_causes"] = root_causes[:5]  # Limit to 5
    
    # --- Target Users ---
    user_indicators = [
        r'(?:for|to|targeting|aimed at)\s+([\w\s]{0,40}?(?:students|patients|farmers|teachers|users|citizens|children|elderly))',
        r'(beneficiaries?|users|customers|stakeholders)',
    ]
    target_users = []
    for pattern in user_indicators:
        matches = re.findall(pattern, cleaned_text, re.IGNORECASE)
        target_users.extend(m.strip() if isinstance(m, str) else " ".join(x.strip() for x in m) for m in matches)

    analysis["extracted"]["target_users"] = list(dict.fromkeys(u.lower() for u in target_users))[:5]
    
    # --- Stakeholders ---
    stakeholder_keywords = ["stakeholder", "department", "organization", "partner", "collaborator"]
    stakeholders = [kw for kw in stakeholder_keywords if kw in cleaned_text.lower()]
    analysis["extracted"]["stakeholders"] = stakeholders
    
    # --- Existing Workflow ---
    workflow_patterns = [r'(?:currently|existing|presently|formerly)\s+(\w+)', r'(?:we|they|the team)\s+(do|make|create|build)']
    workflow = []
    for pattern in workflow_patterns:
        matches = re.findall(pattern, cleaned_text, re.IGNORECASE)
        workflow.extend(m if isinstance(m, str) else " ".join(m) for m in matches)

    analysis["extracted"]["existing_workflow"] = list(dict.fromkeys(workflow))[:5]
    
    # --- Current Limitations ---
    limitation_keywords = [r'limitation', r'challenge', r'constraint', r'barrier', r'cannot', r'able to']
    limitations = []
    for pattern in limitation_keywords:
        matches = re.findall(pattern, cleaned_text, re.IGNORECASE)
        limitations.extend(matches)
    
    analysis["extracted"]["current_limitations"] = list(set(limitations))[:5]
    
    # --- Required Solution ---
    solution_req_patterns = [r'(?:should|must|need to|required to)\s+([\w\s,]{5,80})', r'(solution|approach|implementation)\s+should']
    required_solution = []
    for pattern in solution_req_patterns:
        matches = re.findall(pattern, cleaned_text, re.IGNORECASE)
        required_solution.extend(m.strip() if isinstance(m, str) else " ".join(x.strip() for x in m) for m in matches)

    analysis["extracted"]["required_solution"] = list(dict.fromkeys(required_solution))[:5]
    
    # --- Expected Outcome ---
    outcome_patterns = [r'(?:expected|goal|objective|aim|target)\s+to\s+([\w\s]{3,60})', r'(outcome|result|impact)\s+should\s+([\w\s]{3,60})']
    expected_outcome = []
    for pattern in outcome_patterns:
        matches = re.findall(pattern, cleaned_text, re.IGNORECASE)
        expected_outcome.extend(m.strip() if isinstance(m, str) else " ".join(x.strip() for x in m) for m in matches)

    analysis["extracted"]["expected_outcome"] = list(dict.fromkeys(expected_outcome))[:5]
    
    # --- Constraints ---
    constraint_keywords = [r'constraint', r'limit', r'restriction', r'boundary', r'not allow']
    constraints = []
    for pattern in constraint_keywords:
        matches = re.findall(pattern, cleaned_text, re.IGNORECASE)
        constraints.extend(matches)
    
    analysis["extracted"]["constraints"] = list(set(constraints))[:5]
    
    # --- Technical Requirements ---
    tech_keywords = {
        "ai_ml": ["ai", "machine learning", "deep learning", "neural network", "algorithm"],
        "software": ["software", "app", "platform", "system", "interface"],
        "hardware": ["device", "sensor", "hardware", "embedded", "iot"],
        "data": ["data", "dataset", "training data", "input"],
        "api": ["api", "integration", "interface"],
    }
    tech_requirements = {}
    for category, keywords in tech_keywords.items():
        found = [kw for kw in keywords if kw in cleaned_text.lower()]
        tech_requirements[category] = found
    
    analysis["extracted"]["technical_requirements"] = tech_requirements
    
    # --- Data Requirements ---
    data_patterns = [r'(data|dataset)\s+(?:is\s+)?(?:required|needed|collected)', r'(train|test|validation)\s+set', r'\bdataset\b', r'\btraining data\b']
    data_requirements = []
    for pat in data_patterns:
        data_requirements.extend(re.findall(pat, cleaned_text, re.IGNORECASE))
    analysis["extracted"]["data_requirements"] = data_requirements[:5]
    
    # --- Security Requirements ---
    security_keywords = [r'(security|secure)', r'(privacy|data privacy)', r'(encryption|authentication)']
    security = [kw for kw in security_keywords if kw in cleaned_text.lower()]
    analysis["extracted"]["security_requirements"] = security
    
    # --- Accessibility Requirements ---
    accessibility_keywords = [r'(accessible|accessibility)', r'(disabled|differently abled)', r'(universal design)']
    accessibility = [kw for kw in accessibility_keywords if kw in cleaned_text.lower()]
    analysis["extracted"]["accessibility_requirements"] = accessibility
    
    # --- Scalability Requirements ---
    scalability_keywords = [r'scale', r'scalable', r'large scale', r'100000 user', r'1000 user', r'million']
    scalability = [kw for kw in scalability_keywords if kw in cleaned_text.lower()]
    analysis["extracted"]["scalability_requirements"] = scalability
    
    # --- Infrastructure Requirements ---
    infra_keywords = [r'infrastructure', r'cloud', r'on-premise', r'hosting', r'deployment']
    infrastructure = [kw for kw in infra_keywords if kw in cleaned_text.lower()]
    analysis["extracted"]["infrastructure_requirements"] = infrastructure
    
    # --- Possible Measurable Impact ---
    impact_keywords = [r'impact', r'measure', r'metric', r'KPI', r'result', r'effectiveness']
    impact = [kw for kw in impact_keywords if kw in cleaned_text.lower()]
    analysis["extracted"]["possible_measurable_impact"] = impact
    
    # --- Assumptions ---
    assumption_keywords = [r'assume', r'suppose', r'presume', r'implicitly|implicitly', r'might|could|probably']
    assumptions = []
    for pattern in [r'(?i)assume\s+(.+?)(?:\.|$)', r'(?i)suppose\s+(.+?)(?:\.|$)']:
        matches = re.findall(pattern, cleaned_text)
        assumptions.extend(matches)
    
    analysis["extracted"]["assumptions"] = assumptions[:5]
    
    # --- Risks ---
    risk_keywords = [r'risk', r'hazard', 'danger', 'threat', 'potential problem']
    risks = [kw for kw in risk_keywords if kw in cleaned_text.lower()]
    analysis["extracted"]["risks_identified"] = risks
    
    # --- Possible Solution Directions ---
    solution_patterns = [r'(solution|approach|method)\s+could', r'(?:we|the team)\s+can', r'possible\s+to']
    solution_directions = []
    for pat in solution_patterns:
        solution_directions.extend(re.findall(pat, cleaned_text, re.IGNORECASE))
    analysis["extracted"]["possible_solution_directions"] = [str(m) for m in solution_directions][:5]
    
    # --- Generate Analysis Summary ---
    analysis["analysis"] = {
        "problem_clarity": "high" if analysis["extracted"].get("problem_statement") else "low",
        "root_cause_completeness": "medium" if analysis["extracted"].get("root_causes") else "low",
        "user_identification": "high" if analysis["extracted"].get("target_users") else "low",
        "solution_clarity": "medium" if analysis["extracted"].get("required_solution") else "low",
        "overall_readiness": "medium",
    }
    
    return analysis


def save_problem_analysis_to_project(project_id: int, analysis: Dict[str, Any]) -> int:
    """
    Save the problem statement analysis to the project's permanent memory.
    
    Args:
        project_id: The SIH project ID
        analysis: The analysis dict from analyze_problem_statement()
        
    Returns:
        The evidence ID for the saved analysis
    """
    from Tools.sih_project_manager import SIHProjectManager
    manager = SIHProjectManager()

    # Validate project exists — never create orphan evidence
    if manager.select_project(project_id) is None:
        manager.close()
        raise ValueError(f"Project ID {project_id} not found — analysis NOT saved")

    evidence_title = f"Problem Analysis - {datetime.now().strftime('%Y%m%d_%H%M%S')}"
    evidence_description = f"Analysis of problem statement for project {project_id}"
    
    evidence_id = manager.add_evidence(
        project_id=project_id,
        title=evidence_title,
        e_type="problem_analysis",
        path="",  # Will be stored in description
        description=json.dumps(analysis, indent=2)
    )
    
    # Also save as a decision/record
    manager.add_decision(
        project_id=project_id,
        decision="Problem statement analyzed and saved",
        alternatives=[],
        reason="Initial analysis for SIH project setup",
        evidence=f"Evidence ID: {evidence_id}",
    )
    
    manager.close()
    return evidence_id


def command_center_analyze_problem(project_id: int, text: str) -> Dict[str, Any]:
    """
    Full problem statement analysis workflow for the SIH Command Center.
    
    Args:
        project_id: The SIH project ID
        text: The problem statement text
        
    Returns:
        Complete analysis result
    """
    # Perform the analysis
    analysis = analyze_problem_statement(text)
    
    # Save to project
    evidence_id = save_problem_analysis_to_project(project_id, analysis)
    
    # Mark as saved
    analysis["saved"] = True
    analysis["evidence_id"] = evidence_id
    
    return analysis