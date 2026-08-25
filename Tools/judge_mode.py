"""SIH Judge Mode - Simulates strict SIH-style judges and mock jury panels.

JUDGE MODE:
- AI becomes a strict SIH-style judge
- Asks questions about problem, innovation, architecture, AI/ML, dataset, etc.
- Scores each answer on technical accuracy, clarity, completeness, confidence, evidence
- Provides score, weakness, correct answer direction

MULTI-JUDGE MODE:
- Multiple judge personalities: Technical, AI/ML, Product, Security,
  Government/Impact, Investor, End User, Hostile
- Each judge has different priorities and questioning styles
- Final report with strengths, weaknesses, contradictions, readiness

FINAL SIH AUDIT:
- Complete project audit across all criteria
- Findings classified: CRITICAL / HIGH / MEDIUM / LOW
"""

import json
import logging
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

from Tools.sih_project_manager import SIHProjectManager

logger = logging.getLogger(__name__)

# ============ JUDGE PERSONALITIES ============

JUDGE_PERSONALITIES = {
    "technical": {
        "name": "Technical Judge",
        "focus": ["architecture", "code quality", "scalability", "performance", "technical debt"],
        "style": "Deep technical probing, asks for implementation details",
        "question_templates": [
            "Walk me through your system architecture. What happens when {scale} users hit your API simultaneously?",
            "How did you handle {failure_case} in your implementation?",
            "What are the performance bottlenecks in your current design and how would you fix them?",
            "Explain your database schema. Why this design over alternatives?",
            "How is your code tested? Show me your test coverage.",
        ],
    },
    "ai_ml": {
        "name": "AI/ML Judge",
        "focus": ["dataset", "model selection", "accuracy", "bias", "training methodology"],
        "style": "Questions data provenance, model metrics, ML ethics",
        "question_templates": [
            "Where did your training data come from? How was it validated?",
            "What are your model's precision and recall? On what test set?",
            "How do you handle bias in your {model_type} model?",
            "What happens when your model encounters out-of-distribution inputs?",
            "Why did you choose this model over simpler baselines? Did you benchmark against them?",
            "How do you monitor model drift in production?",
        ],
    },
    "product": {
        "name": "Product Judge",
        "focus": ["user needs", "UX", "adoption barriers", "value proposition"],
        "style": "User-centric questions, challenges assumptions about users",
        "question_templates": [
            "Who exactly is your target user? Have you talked to any real ones?",
            "What is the user's current alternative? Why would they switch?",
            "Walk me through the user journey. Where do users drop off?",
            "How did you validate that users actually want this feature?",
            "What is your adoption strategy for the first 100 users?",
        ],
    },
    "security": {
        "name": "Security Judge",
        "focus": ["authentication", "data protection", "vulnerabilities", "privacy"],
        "style": "Adversarial security questioning",
        "question_templates": [
            "How do you store passwords? Show me your hashing approach.",
            "What happens if an attacker gets your database dump?",
            "How do you prevent SQL injection and XSS in {component}?",
            "Where are your API keys stored? Are they ever exposed client-side?",
            "What PII do you collect and what is your retention policy?",
            "Have you done a security audit? What vulnerabilities did you find?",
        ],
    },
    "government_impact": {
        "name": "Government/Impact Judge",
        "focus": ["social impact", "government alignment", "sustainability", "accessibility"],
        "style": "Focus on real-world impact and policy alignment",
        "question_templates": [
            "How does your solution align with Digital India initiatives?",
            "What measurable impact will this have in 1 year? 5 years?",
            "How does this work in rural areas with poor connectivity?",
            "Which government department would adopt this and why?",
            "Is this accessible to users with disabilities and low digital literacy?",
            "How will this be sustained after the hackathon ends?",
        ],
    },
    "investor": {
        "name": "Investor Judge",
        "focus": ["business model", "costs", "market size", "competition"],
        "style": "Commercial viability questions",
        "question_templates": [
            "What does it cost to serve one user? At scale of 100,000 users?",
            "Who are your competitors and what is your moat?",
            "What is your revenue model if this goes commercial?",
            "What is the total addressable market for this problem?",
            "Why hasn't a startup already solved this?",
        ],
    },
    "end_user": {
        "name": "End User Representative",
        "focus": ["usability", "language", "device compatibility", "real-world fit"],
        "style": "Practical everyday-use concerns",
        "question_templates": [
            "I use a budget Android phone with 2GB RAM. Will your app work for me?",
            "I don't read English well. Can I use this in my language?",
            "What happens when I have no internet in my village?",
            "How many taps does it take to do the main task? Can my parents use it?",
        ],
    },
    "hostile": {
        "name": "Hostile Judge",
        "focus": ["weaknesses", "failures", "contradictions", "overclaims"],
        "style": "Aggressive stress-testing, looks for cracks",
        "question_templates": [
            "Your demo worked. What happens when it fails live, right now?",
            "Isn't this just {existing_solution} with a new UI? What's actually new?",
            "You claim {claim}. Prove it with evidence right now.",
            "If I removed the AI from this, would anything change? Is AI just buzzword here?",
            "Your team of {team_size} built this in how long? That timeline seems impossible. What shortcuts did you take?",
        ],
    },
}


def start_judge_mode(project_id: int) -> Dict[str, Any]:
    """
    Start a Judge Mode session. The AI acts as a strict SIH-style judge.

    Args:
        project_id: The SIH project ID

    Returns:
        First question and session state
    """
    manager = SIHProjectManager()
    project = manager.select_project(project_id)
    if not project:
        manager.close()
        return {"error": f"Project ID {project_id} not found"}

    # Generate question bank based on actual project data
    question_bank = _build_question_bank(project)

    session = {
        "project_id": project_id,
        "project_name": project.get("project_name"),
        "started_at": datetime.now().isoformat(),
        "questions_asked": [],
        "scores": [],
        "current_index": 0,
        "total_questions": len(question_bank),
    }

    first_q = question_bank[0] if question_bank else None
    if first_q:
        session["questions_asked"].append(first_q)
        session["current_index"] = 1

    # Save session start as evidence
    manager.add_evidence(
        project_id=project_id,
        title=f"Judge Session started {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        e_type="judge_session",
        path="",
        description=json.dumps({"mode": "judge_mode", "first_question": first_q}, indent=2),
    )
    manager.close()

    return {
        "status": "active",
        "session": session,
        "question": first_q,
        "note": "Answer the question. The judge will score your answer and ask the next one.",
    }


def score_answer_and_next(project_id: int, question: str, answer: str) -> Dict[str, Any]:
    """
    Score the team's answer to a judge question, then return the next question.

    Args:
        project_id: The SIH project ID
        question: The question that was asked
        answer: The team's answer

    Returns:
        Score breakdown + next question (never revealed ahead of time)
    """
    manager = SIHProjectManager()
    project = manager.select_project(project_id)
    if not project:
        manager.close()
        return {"error": f"Project ID {project_id} not found"}

    # Score the answer based on verifiable criteria
    scores = {
        "technical_accuracy": _score_technical_accuracy(answer, project),
        "clarity": _score_clarity(answer),
        "completeness": _score_completeness(answer, question),
        "confidence": _score_confidence(answer),
        "evidence": _score_evidence_citation(answer, project),
        "consistency": _score_consistency(answer, project),
    }

    overall = round(sum(scores.values()) / len(scores), 2)

    weaknesses = [k.replace("_", " ") for k, v in scores.items() if v < 5]

    # Build next question WITHOUT revealing it beforehand
    question_bank = _build_question_bank(project)
    asked = [q for q in [question]]
    remaining = [q for q in question_bank if q not in asked]
    next_question = random.choice(remaining) if remaining else None

    # Save Q&A + score to evidence
    manager.add_evidence(
        project_id=project_id,
        title=f"Judge Q&A scored at {overall}/10",
        e_type="judge_session",
        path="",
        description=json.dumps({"question": question, "answer": answer[:500], "scores": scores, "overall": overall}, indent=2),
    )
    manager.close()

    result = {
        "score_breakdown": scores,
        "overall_score": overall,
        "weaknesses": weaknesses or ["No major weaknesses detected in this answer"],
        "correct_answer_direction": _answer_direction(question, project),
        "improvement_note": "Strengthen answers with concrete evidence from your actual implementation." if overall < 7 else "Good answer. Keep citing specific evidence.",
    }

    if next_question:
        result["next_question"] = next_question
    else:
        result["session_complete"] = True
        result["final_note"] = "Question bank exhausted. Use start_mock_jury for multi-judge panel."

    return result


def start_mock_jury(project_id: int) -> Dict[str, Any]:
    """
    Start Multi-Judge Mock Jury with all 8 judge personalities.

    Each judge reviews the ACTUAL project data from their own perspective.

    Returns:
        Per-judge assessments and final combined report
    """
    manager = SIHProjectManager()
    project = manager.select_project(project_id)
    if not project:
        manager.close()
        return {"error": f"Project ID {project_id} not found"}

    ideas = manager.list_ideas(project_id)
    features = manager.list_features(project_id)
    risks = manager.list_risks(project_id)
    research = manager.list_research(project_id)
    evidence = manager.list_evidence(project_id)
    decisions = manager.list_decisions(project_id)
    team = project.get("team_members", [])

    jury_report = []
    for key, persona in JUDGE_PERSONALITIES.items():
        assessment = _assess_as_judge(
            persona, project, ideas, features, risks, research, evidence, decisions, team
        )
        jury_report.append({
            "judge": persona["name"],
            "focus_areas": persona["focus"],
            "sample_questions": persona["question_templates"][:3],
            "assessment": assessment,
        })

    # Final combined report
    all_strengths = []
    all_weaknesses = []
    unanswered = []
    suspicious_claims = []

    for j in jury_report:
        all_strengths.extend(j["assessment"]["strengths"])
        all_weaknesses.extend(j["assessment"]["weaknesses"])
        unanswered.extend(j["assessment"]["unanswered_questions"])

        # Flag claims without evidence
        for ev in evidence:
            if ev.get("type") == "claim" and not ev.get("description"):
                suspicious_claims.append(f"Claim '{ev.get('title')}' has no supporting description")

    # Readiness calculation from REAL data
    readiness_factors = {
        "features_defined": min(len(features) / 5, 1.0),
        "research_done": min(len(research) / 3, 1.0),
        "risks_managed": (len([r for r in risks if r.get("status") == "resolved"]) / len(risks)) if risks else 0.5,
        "evidence_collected": min(len(evidence) / 8, 1.0),
        "decisions_logged": min(len(decisions) / 4, 1.0),
    }
    readiness_score = round(sum(readiness_factors.values()) / len(readiness_factors) * 100)

    final_report = {
        "project_name": project.get("project_name"),
        "jury_date": datetime.now().isoformat(),
        "judges_panel": jury_report,
        "final_report": {
            "strengths": list(set(all_strengths))[:10],
            "weaknesses": list(set(all_weaknesses))[:10],
            "unanswered_questions": list(set(unanswered))[:10],
            "suspicious_unverified_claims": suspicious_claims or ["None flagged — but verify all claims have evidence before presenting"],
            "overall_readiness_score": readiness_score,
            "readiness_verdict": (
                "SIH READY" if readiness_score >= 80 else
                "MOSTLY READY — close gaps listed above" if readiness_score >= 60 else
                "NOT READY — critical work remains"
            ),
            "readiness_factors": {k: round(v * 100) for k, v in readiness_factors.items()},
        },
    }

    # Save jury report
    manager.add_evidence(
        project_id=project_id,
        title=f"Mock Jury Report {datetime.now().strftime('%Y-%m-%d')}",
        e_type="mock_jury",
        path="",
        description=json.dumps(final_report["final_report"], indent=2),
    )
    manager.close()

    return final_report


def final_sih_audit(project_id: int) -> Dict[str, Any]:
    """
    Complete Final SIH Audit across all criteria.

    Classifies findings: CRITICAL / HIGH / MEDIUM / LOW.
    Never marks project READY if critical requirements remain unresolved.

    Args:
        project_id: The SIH project ID

    Returns:
        Full audit report with classified findings
    """
    manager = SIHProjectManager()
    project = manager.select_project(project_id)
    if not project:
        manager.close()
        return {"error": f"Project ID {project_id} not found"}

    findings = []
    problem_stmt = project.get("problem_statement", "") or ""

    def add_finding(severity: str, category: str, finding: str, action: str):
        findings.append({
            "severity": severity,  # CRITICAL / HIGH / MEDIUM / LOW
            "category": category,
            "finding": finding,
            "required_action": action,
        })

    # --- Gather actual data ---
    ideas = manager.list_ideas(project_id)
    features = manager.list_features(project_id)
    risks = manager.list_risks(project_id)
    research = manager.list_research(project_id)
    evidence = manager.list_evidence(project_id)
    decisions = manager.list_decisions(project_id)
    team = project.get("team_members", [])
    stats = manager.get_project_stats(project_id)

    # --- Problem alignment ---
    if not problem_stmt.strip():
        add_finding("CRITICAL", "Problem Alignment", "No problem statement recorded for this project.",
                    "Add the official SIH problem statement via the Problem Statement Analyzer.")
    elif len(problem_stmt) < 50:
        add_finding("HIGH", "Problem Alignment", "Problem statement is too short to be the official SIH PS.",
                    "Paste the complete official problem statement.")

    # --- Novelty / Research ---
    if stats.get("research_items", 0) == 0:
        add_finding("CRITICAL", "Novelty", "Zero research conducted — uniqueness claims are unverifiable.",
                    "Run Existing Solution Hunter; save at least 3 sources with URLs.")
    elif stats.get("research_items", 0) < 3:
        add_finding("MEDIUM", "Novelty", f"Only {stats['research_items']} research source(s) saved.",
                    "Research more existing solutions, papers, and government platforms.")

    # --- Technical implementation ---
    must_have = [f for f in features if "must have" in (f.get("priority") or "").lower()]
    if not features:
        add_finding("CRITICAL", "Implementation", "No features defined — nothing implemented or planned.",
                    "Run MVP Planner to classify MUST HAVE features.")
    elif not must_have:
        add_finding("HIGH", "Implementation", "No MUST HAVE features identified.",
                    "Re-run MVP Planner; core functionality must be marked MUST HAVE.")
    pending_must_have = [f for f in must_have if (f.get("status") or "").lower() in ("pending", "not_started")]
    if pending_must_have:
        add_finding("HIGH", "Implementation",
                    f"{len(pending_must_have)} MUST HAVE feature(s) still pending: " +
                    ", ".join(f.get('title', '?') for f in pending_must_have[:3]),
                    "Complete core features before demo day.")

    # --- Feasibility ---
    active_critical_risks = [r for r in risks if r.get("severity") == "critical" and r.get("status") != "resolved"]
    if active_critical_risks:
        add_finding("CRITICAL", "Feasibility",
                    f"{len(active_critical_risks)} unresolved CRITICAL risk(s).",
                    "Mitigate or explicitly accept these risks with owner sign-off.")

    # --- Scalability ---
    has_architecture = any(ev.get("type") in ("architecture", "architecture_edit") for ev in evidence)
    if not has_architecture:
        add_finding("HIGH", "Scalability", "No documented architecture.",
                    "Generate and review system architecture.")

    # --- Impact ---
    if not problem_stmt or not any(kw in problem_stmt.lower() for kw in ("impact", "benefit", "user", "citizen", "farmer", "student")):
        add_finding("MEDIUM", "Impact", "Problem statement lacks explicit impact/beneficiary language.",
                    "Clarify who benefits and how impact will be measured.")

    # --- UX / Accessibility ---
    ux_features = [f for f in features if any(kw in f.get("title", "").lower() for kw in ("ux", "ui", "accessib", "language", "offline"))]
    if not ux_features:
        add_finding("MEDIUM", "UX/Accessibility", "No UX/accessibility/offline/language features tracked.",
                    "For India deployment: add offline mode, regional language support, low-end device support.")

    # --- Security ---
    sec_evidence = [ev for ev in evidence if "secur" in (ev.get("type") or "").lower() or "secur" in (ev.get("title") or "").lower()]
    if not sec_evidence:
        add_finding("MEDIUM", "Security", "No security audit evidence found.",
                    "Run security audit; document auth approach and data protection.")

    # --- Documentation ---
    doc_evidence = [ev for ev in evidence if "document" in (ev.get("title") or "").lower()]
    if not doc_evidence:
        add_finding("MEDIUM", "Documentation", "No documentation generated.",
                    "Generate documentation from actual implementation.")

    # --- Testing / Evidence ---
    test_evidence = [ev for ev in evidence if "test" in (ev.get("type") or "").lower()]
    if not test_evidence:
        add_finding("HIGH", "Testing", "No test results recorded — demo stability unproven.",
                    "Execute tests on core flows and record PASS/FAIL evidence.")
    elif stats.get("evidence", 0) < 5:
        add_finding("LOW", "Evidence", "Thin evidence trail for judging.",
                    "Attach screenshots, benchmarks, and demo recordings to Evidence Locker.")

    # --- Pitch / Presentation ---
    pitch_evidence = [ev for ev in evidence if "pitch" in (ev.get("type") or "").lower()]
    if not pitch_evidence:
        add_finding("LOW", "Presentation", "No pitch preparation recorded.",
                    "Use Pitch Builder then run Judge Mode practice rounds.")

    # --- Cost ---
    cost_evidence = [ev for ev in evidence if "cost" in (ev.get("type") or "").lower()]
    if not cost_evidence:
        add_finding("MEDIUM", "Cost", "No deployment cost analysis.",
                    "Calculate costs at 100/1K/10K/100K/1M users with clearly labelled estimates.")

    # --- Team ---
    if not team:
        add_finding("MEDIUM", "Team", "No team members registered.",
                    "Register team members with roles so tasks can be allocated.")

    # --- Verdict logic: NEVER ready if CRITICAL unresolved ---
    critical_count = sum(1 for f in findings if f["severity"] == "CRITICAL")
    high_count = sum(1 for f in findings if f["severity"] == "HIGH")
    medium_count = sum(1 for f in findings if f["severity"] == "MEDIUM")
    low_count = sum(1 for f in findings if f["severity"] == "LOW")

    if critical_count > 0:
        verdict = "NOT READY"
        verdict_reason = f"{critical_count} CRITICAL finding(s) must be resolved first."
    elif high_count > 2:
        verdict = "AT RISK"
        verdict_reason = f"No critical issues, but {high_count} HIGH findings need attention."
    elif high_count > 0:
        verdict = "NEARLY READY"
        verdict_reason = f"{high_count} HIGH finding(s) remain."
    else:
        verdict = "READY"
        verdict_reason = "No critical or high findings. Address medium/low items opportunistically."

    audit = {
        "project_id": project_id,
        "project_name": project.get("project_name"),
        "audit_date": datetime.now().isoformat(),
        "findings": sorted(findings, key=lambda f: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}[f["severity"]]),
        "summary": {
            "critical": critical_count,
            "high": high_count,
            "medium": medium_count,
            "low": low_count,
        },
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "honesty_note": (
            "Verdict is computed strictly from recorded project data. "
            "A READY verdict reflects absence of logged blockers, NOT guaranteed judge approval."
        ),
    }

    # Persist audit
    manager.add_evidence(
        project_id=project_id,
        title=f"Final SIH Audit — {verdict}",
        e_type="final_audit",
        path="",
        description=json.dumps(audit["summary"], indent=2),
    )
    manager.close()

    return audit


# ============ INTERNAL HELPERS ============

def _build_question_bank(project: Dict[str, Any]) -> List[str]:
    """Build judge questions grounded in ACTUAL project data."""
    questions = []
    ps = project.get("problem_statement") or ""
    name = project.get("project_name") or "this project"

    if ps:
        questions.append("State the core problem in one sentence, without reading from notes.")
        questions.append("Who exactly suffers from this problem today, and how do they currently cope?")
    else:
        questions.append("You haven't recorded a problem statement. What exact problem does your solution solve?")

    if project.get("ideas"):
        questions.append(f"You generated {len(project['ideas'])} idea(s). Why was '{project['ideas'][0].get('title', 'your chosen idea')}' selected over the others?")
    else:
        questions.append("What alternative solutions did you consider and reject? Why?")

    questions.append("Describe your system architecture end-to-end in under 90 seconds.")
    questions.append("What is the single biggest technical risk in your build right now, and what is your mitigation?")
    questions.append("Demonstrate or describe your strongest piece of evidence that the core flow works.")
    questions.append("What happens when your primary external dependency fails during the demo?")
    questions.append(f"If judges asked whether '{name}' already exists as a product, what would you cite as proof of your differentiation?")
    questions.append("What will this cost per user at 100,000 users? Label estimates clearly.")
    questions.append("What part of your demo could break live in front of judges, and what is your fallback plan?")
    questions.append("What is NOT included in your current build that you claim in your presentation?")

    return questions


def _score_technical_accuracy(answer: str, project: Dict[str, Any]) -> float:
    """Score technical accuracy heuristically — flags vague/hand-wavy answers."""
    if not answer or len(answer.strip()) < 20:
        return 3.0
    score = 5.0
    lower = answer.lower()
    # Concrete technical terms suggest accuracy
    tech_markers = ["database", "api", "model", "server", "latency", "throughput", "schema", "endpoint", "accuracy", "test"]
    found = sum(1 for m in tech_markers if m in lower)
    score += min(found * 0.5, 2.5)
    # Hand-waving reduces score
    vague_markers = ["basically", "kind of", "somehow", "i think", "probably", "not sure"]
    found_vague = sum(1 for m in vague_markers if m in lower)
    score -= found_vague * 1.0
    return max(min(score, 10), 1)


def _score_clarity(answer: str) -> float:
    """Score clarity by structure signals."""
    if not answer:
        return 2.0
    words = answer.split()
    if len(words) < 10:
        return 3.0
    score = 6.0
    if len(words) > 300:
        score -= 1  # rambling
    structured = any(s in answer for s in ("\n", "1.", "2.", "-", "•", "first", "second", "finally"))
    if structured:
        score += 2
    return max(min(score, 10), 1)


def _score_completeness(answer: str, question: str) -> float:
    """Score whether the answer actually addresses the question."""
    if not answer:
        return 2.0
    q_words = set(question.lower().split()) - {"the", "a", "an", "is", "are", "what", "how", "why", "your", "you"}
    a_words = set(answer.lower().split())
    overlap = len(q_words & a_words) / max(len(q_words), 1)
    base = 4.0 + overlap * 6
    return max(min(base, 10), 1)


def _score_confidence(answer: str) -> float:
    """Score confidence markers."""
    if not answer:
        return 2.0
    lower = answer.lower()
    hedging = sum(lower.count(h) for h in ("maybe", "perhaps", "i guess", "sort of", "we hope"))
    assertive = sum(lower.count(a) for a in ("we implemented", "we tested", "our data shows", "we measured"))
    score = 6.0 - hedging * 1.0 + assertive * 1.0
    return max(min(score, 10), 1)


def _score_evidence_citation(answer: str, project: Dict[str, Any]) -> float:
    """Score whether the answer cites real evidence from the project."""
    if not answer:
        return 2.0
    lower = answer.lower()
    evidence_markers = ["tested", "measured", "benchmark", "screenshot", "%", "percent", "ms", "seconds", "users"]
    found = sum(1 for m in evidence_markers if m in lower)
    return max(min(4.0 + found * 1.5, 10), 1)


def _score_consistency(answer: str, project: Dict[str, Any]) -> float:
    """Check consistency against known project facts (heuristic)."""
    if not answer:
        return 3.0
    # If project has no features but answer claims full implementation → inconsistent
    features = project.get("features") or []
    lower = answer.lower()
    claims_complete = any(p in lower for p in ("fully implemented", "complete product", "production ready"))
    if claims_complete and len(features) < 3:
        return 3.0  # overclaiming vs recorded reality
    return 6.5


def _answer_direction(question: str, project: Dict[str, Any]) -> str:
    """Give the direction of a good answer, grounded in project data."""
    ql = question.lower()
    if "problem" in ql or "who suffers" in ql:
        ps = project.get("problem_statement", "")
        return f"Anchor to your recorded problem statement: {ps[:150]}..." if ps else "First record your problem statement, then answer from it."
    if "architecture" in ql:
        return "Name frontend, backend, database, and the data flow between them — reference your generated architecture."
    if "risk" in ql:
        risks = project.get("risks") or []
        if risks:
            top = risks[0]
            return f"Cite your risk register: '{top.get('description', '')}' with mitigation '{top.get('mitigation', '')}'."
        return "Your risk register is empty — identify risks first."
    if "cost" in ql:
        return "Break down infra/AI/storage costs per user tier (100/1K/10K/100K/1M) and clearly label estimates vs actuals."
    if "differentiation" in ql or "exists" in ql:
        return "Cite specific researched competitors and name the precise gap you fill — never claim uniqueness without sources."
    if "fallback" in ql or "break" in ql:
        return "Identify the most fragile dependency and describe the graceful degradation plan."
    if "claim" in ql or "presentation" in ql:
        return "Audit every presentation claim against Evidence Locker entries; remove unsupported ones."
    return "Answer with specifics from your actual implementation; cite tests, metrics, or screenshots where possible."


def _assess_as_judge(persona, project, ideas, features, risks, research, evidence, decisions, team) -> Dict[str, Any]:
    """Assess the project from one judge persona's perspective using REAL data."""
    strengths = []
    weaknesses = []
    unanswered_questions = []

    focus_str = " ".join(persona["focus"]).lower()

    # Data-grounded strengths
    if "architecture" in focus_str and any("architecture" in (ev.get("type") or "") for ev in evidence):
        strengths.append("Documented architecture exists")
    if "dataset" in focus_str or "data" in focus_str:
        if research:
            strengths.append(f"{len(research)} research sources recorded with URLs")
        else:
            weaknesses.append("No research sources — data provenance unverifiable")
    if "usability" in focus_str or "user" in focus_str:
        if team:
            strengths.append(f"Team defined with {len(team)} member(s)")
        else:
            weaknesses.append("No registered team — accountability unclear")
    if "business" in focus_str or "cost" in focus_str:
        cost_ev = [e for e in evidence if "cost" in (e.get("type") or "")]
        if cost_ev:
            strengths.append("Cost analysis exists")
        else:
            weaknesses.append("No cost model — commercial viability unknown")

    # Universal data-grounded checks
    if not ideas:
        weaknesses.append("No recorded ideas — decision process invisible to judges")
    if not features:
        weaknesses.append("No features defined — nothing demonstrable on record")
    pending = [f for f in features if (f.get("status") or "").lower() in ("pending", "in_progress")]
    if pending:
        weaknesses.append(f"{len(pending)} feature(s) incomplete: " + ", ".join(f.get("title", "?") for f in pending[:3]))
    open_risks = [r for r in risks if r.get("status") != "resolved"]
    if open_risks:
        weaknesses.append(f"{len(open_risks)} unresolved risk(s) on register")

    # Persona-specific probe questions they'd still ask
    unanswered_questions = persona["question_templates"][:3]

    return {
        "strengths": strengths or ["Insufficient data to identify strengths — populate project records"],
        "weaknesses": weaknesses or ["No structural weaknesses visible in recorded data"],
        "unanswered_questions": unanswered_questions,
        "persona_note": persona["style"],
    }
