"""SIH Tools - Unified LiveKit function_tool wrappers for all SIH subsystems.

Routes natural commands like "analyze this PS", "kill this idea", "score my
project", "start judge mode", "audit project" into the correct SIH subsystem.
"""

import logging

from livekit.agents import function_tool

logger = logging.getLogger(__name__)


# ================= PROBLEM STATEMENT ANALYZER =================

@function_tool()
async def analyze_problem_statement(project_id: int, problem_statement_text: str) -> str:
    """Analyze an SIH problem statement and extract structured requirements
    (problem, users, constraints, tech requirements, risks, hidden assumptions).
    Result is saved permanently into the project brain.

    Args:
        project_id: The SIH project ID
        problem_statement_text: Full text of the problem statement
    """
    try:
        from Tools.problem_statement_analyzer import command_center_analyze_problem
        res = command_center_analyze_problem(project_id, problem_statement_text)
        ex = res.get("extracted", {})
        out = (
            f"📋 PROBLEM STATEMENT ANALYSIS (saved as evidence #{res.get('evidence_id')})\n"
            f"════════════════════\n"
            f"❓ Problem: {str(ex.get('problem_statement', 'n/a'))[:200]}\n\n"
            f"🎯 Target users: {', '.join(ex.get('target_users', [])) or 'not detected'}\n"
            f"🏛️ Stakeholders: {', '.join(ex.get('stakeholders', [])) or 'not detected'}\n"
            f"⚠️ Constraints: {', '.join(ex.get('constraints', [])) or 'not detected'}\n"
            f"🧩 Assumptions: {len(ex.get('assumptions', []))} | Risks flagged: {len(ex.get('risks_identified', []))}\n"
            f"\n💡 Next: run generate_ideas against this problem."
        )
        return out
    except Exception as e:
        return f"❌ Analysis failed: {e}"


# ================= IDEA GENERATOR + KILLER =================

@function_tool()
async def generate_ideas(project_id: int, count: int = 4) -> str:
    """Generate multiple solution ideas for the project's problem statement,
    with feasibility/complexity/impact analysis. Saved to project memory.

    Args:
        project_id: The SIH project ID
        count: Number of ideas to generate (default 4)
    """
    try:
        from Tools.sih_project_manager import SIHProjectManager
        mgr = SIHProjectManager()
        proj = mgr.select_project(project_id)
        mgr.close()
        if not proj:
            return f"❌ Project ID {project_id} not found."
        ps = proj.get("problem_statement") or ""
        if not ps.strip():
            return "❌ No problem statement recorded. Run analyze_problem_statement first."

        from Tools.idea_generator import generate_ideas as _gen
        ideas = _gen(project_id, ps, count=max(1, min(count, 8)))
        out = f"💡 Generated {len(ideas)} ideas:\n\n"
        for i in ideas:
            out += (
                f"{i['id']}. {i['name']}\n"
                f"   Feasibility: {i['feasibility']} | Complexity: {i['complexity']} | Effort: {i['estimated_development_effort']}\n"
                f"   Impact: {i['expected_impact'][:80]}\n"
            )
        out += "\n➡ Use kill_idea(n) to stress-test any of these before selecting."
        return out
    except Exception as e:
        return f"❌ Idea generation failed: {e}"


@function_tool()
async def kill_idea(project_id: int, idea_number: int) -> str:
    """IDEA KILLER MODE: attack a proposed idea and expose its weaknesses.
    Never gives generic praise — finds duplicate functionality, weak assumptions,
    scalability/deployment/offline/multilingual gaps.

    Args:
        project_id: The SIH project ID
        idea_number: The idea number (1-based) to attack
    """
    try:
        from Tools.idea_generator import idea_killer_mode
        k = idea_killer_mode(project_id, idea_number)
        if "error" in k:
            return f"❌ {k['error']}"
        out = (
            f"🔪 IDEA KILLER REPORT — {k.get('idea_name', '?')}\n"
            f"════════════════════\n"
            f"🚨 Critical weaknesses ({len(k['critical_weaknesses'])}):\n"
        )
        for w in k["critical_weaknesses"][:8]:
            out += f"   {w}\n"
        out += f"\n🛠️ Recommended improvements ({len(k['recommendations'])}):\n"
        for r in k["recommendations"][:6]:
            out += f"   • {r}\n"
        return out
    except Exception as e:
        return f"❌ Idea killer failed: {e}"


@function_tool()
async def compare_ideas(project_id: int, idea_numbers: str) -> str:
    """Compare multiple ideas side-by-side and recommend the strongest.

    Args:
        project_id: The SIH project ID
        idea_numbers: Comma-separated idea numbers, e.g. "1,3"
    """
    try:
        indices = [int(x.strip()) for x in idea_numbers.split(",") if x.strip().isdigit()]
        from Tools.idea_generator import compare_ideas as _cmp
        c = _cmp(project_id, indices)
        if not c["comparison"]:
            return "❌ No valid ideas found for comparison. Generate ideas first."
        out = "⚖️ IDEA COMPARISON\n════════════════════\n"
        for comp in c["comparison"]:
            out += (
                f"#{comp['idea_index']} {comp['idea_name'][:50]}\n"
                f"   Feasibility: {comp['feasibility']} | Complexity: {comp['complexity']}\n"
            )
        out += f"\n🏆 RECOMMENDATION: {c['recommendation']}"
        return out
    except Exception as e:
        return f"❌ Comparison failed: {e}"


# ================= SCORING ENGINE =================

@function_tool()
async def score_project(project_id: int) -> str:
    """Score the SIH project across novelty, feasibility, impact, scalability etc.
    This is an internal readiness estimate, NOT an official SIH score.

    Args:
        project_id: The SIH project ID
    """
    try:
        from Tools.sih_scoring_engine import generate_scorecard
        sc = generate_scorecard(project_id)
        if "error" in sc:
            return f"❌ {sc['error']}"
        out = (
            f"📊 PROJECT SCORECARD\n════════════════════\n"
            f"Overall: {sc['score']}/10 ({sc['score_description']})\n"
            f"Confidence: {round(sc.get('confidence', 0) * 100)}%\n\n"
            f"Category breakdown:\n"
        )
        for cat, s in sc.get("category_breakdown", {}).items():
            bar = "█" * round(s) + "░" * max(0, 10 - round(s))
            out += f"   {bar} {s}/10  {cat.replace('_', ' ')}\n"
        strengths = sc.get("top_strengths", [])
        weaknesses = sc.get("top_weaknesses", [])
        actions = sc.get("top_3_actions", [])
        if strengths:
            out += "\n💪 Top strengths:\n" + "".join(f"   + {s}\n" for s in strengths[:5])
        if weaknesses:
            out += "\n🩹 Top weaknesses:\n" + "".join(f"   - {w}\n" for w in weaknesses[:5])
        if actions:
            out += "\n⚡ Top 3 improvement actions:\n" + "".join(
                f"   {i+1}. {a}\n" for i, a in enumerate(actions))
        out += "\n⚠️ " + sc["summary"].get("disclaimer", "")
        return out
    except Exception as e:
        return f"❌ Scoring failed: {e}"


# ================= RESEARCH ASSISTANT =================

@function_tool()
async def research_topic(project_id: int, topic: str) -> str:
    """Research a technology/topic and save findings with source tracking.

    Args:
        project_id: The SIH project ID
        topic: Technology or topic to research (e.g., "TensorFlow Lite")
    """
    try:
        from Tools.research_assistant import research_technology_landscape
        f = research_technology_landscape(topic, project_id=project_id)
        return (
            f"🔬 Research workspace entry created for '{topic}'\n"
            f"Quality marker: {f.get('research_quality', 'unverified').upper()} — "
            f"verify via web search before citing.\n"
            f"Saved to project evidence locker."
        )
    except Exception as e:
        return f"❌ Research failed: {e}"


@function_tool()
async def find_existing_solutions(project_id: int, solution_description: str) -> str:
    """Search for existing solutions/products similar to your proposed solution.
    The AI never claims uniqueness without evidence.

    Args:
        project_id: The SIH project ID
        solution_description: Description of YOUR proposed solution to check against
    """
    try:
        from Tools.research_assistant import find_existing_solutions as _find
        _find(solution_description, project_id=project_id)
        return (
            f"🕵️ EXISTING SOLUTION HUNT\n════════════════════\n"
            f"Searched against: {solution_description[:150]}\n"
            f"Status: UNVERIFIED — run live web search to confirm competitors exist.\n"
            f"Gap analysis saved. Next: save found sources via add_research(...)."
        )
    except Exception as e:
        return f"❌ Solution hunt failed: {e}"


@function_tool()
async def find_datasets(project_id: int, topic: str) -> str:
    """Find datasets relevant to a topic and save them to project memory.

    Args:
        project_id: The SIH project ID
        topic: Dataset subject (e.g., "crop disease images")
    """
    try:
        from Tools.research_assistant import find_datasets as _ds
        r = _ds(topic, project_id=project_id)
        ds = r.get("datasets", [])
        out = f"🗃️ Dataset search for '{topic}': {len(ds)} candidate(s) saved.\n"
        for d in ds:
            out += f"   • {d['name']} — verify license & availability before use.\n"
        return out
    except Exception as e:
        return f"❌ Dataset search failed: {e}"


# ================= ARCHITECTURE + MVP =================

@function_tool()
async def generate_architecture(project_id: int, solution_description: str) -> str:
    """Generate complete system architecture (frontend/backend/db/AI/security/data flow),
    stored as structured data so individual components can be edited later.

    Args:
        project_id: The SIH project ID
        solution_description: Short description of the chosen solution
    """
    try:
        from Tools.architecture_generator import generate_architecture as _ga
        arch = _ga(project_id, solution_description)
        ai = arch.get("ai_ml", {})
        hw = arch.get("hardware", {})
        return (
            f"🏗️ ARCHITECTURE GENERATED (type: {arch['architecture_type']})\n"
            f"════════════════════\n"
            f"Frontend: {arch['frontend']['type']}\n"
            f"Backend: {arch['backend']['type']}\n"
            f"Database: {arch['database']['type']}\n"
            f"Auth: {arch['authentication']['method']}\n"
            f"AI/ML: {ai.get('type', 'N/A')}\n"
            f"Hardware: {hw.get('devices', 'N/A')}\n"
            f"Deployment: {arch['deployment'].get('platform', 'TBD')}\n"
            f"\nSaved to project evidence. Ask me to edit any component."
        )
    except Exception as e:
        return f"❌ Architecture generation failed: {e}"


@function_tool()
async def plan_mvp(project_id: int) -> str:
    """Classify all features into MUST HAVE / SHOULD HAVE / NICE TO HAVE /
    DEMO IMPACT / FUTURE SCOPE with effort, dependencies and risk per feature.

    Args:
        project_id: The SIH project ID
    """
    try:
        from Tools.architecture_generator import mvp_planner
        mvp = mvp_planner(project_id)
        if "error" in mvp:
            return f"❌ {mvp['error']}"
        feats = mvp["classified_features"]
        icons = {"MUST HAVE": "🔴", "SHOULD HAVE": "🟠", "NICE TO HAVE": "🟡",
                 "DEMO IMPACT": "🎬", "FUTURE SCOPE": "🔮"}
        out = "📋 MVP PLAN\n════════════════════\n"
        order = ["MUST HAVE", "SHOULD HAVE", "DEMO IMPACT", "NICE TO HAVE", "FUTURE SCOPE"]
        for prio in order:
            group = [f for f in feats if f["priority"] == prio]
            if not group:
                continue
            out += f"\n{icons.get(prio, '•')} {prio} ({len(group)}):\n"
            for f in group[:6]:
                out += (
                    f"   • {f['title'][:60]} | effort: {f['estimated_effort']} | "
                    f"status: {f['status']} | risk: {f['risk']}\n"
                )
        must = sum(1 for f in feats if f["priority"] == "MUST HAVE")
        out += (
            f"\n⚠️ Hackathon rule: build the {must} MUST HAVE feature(s) first; "
            f"FUTURE SCOPE items must not consume hackathon time."
        )
        return out
    except Exception as e:
        return f"❌ MVP planning failed: {e}"


# ================= HACKATHON MODE =================

@function_tool()
async def start_hackathon_mode(project_id: int) -> str:
    """Activate HACKATHON MODE: shows blockers, demo readiness, testing status,
    scope-creep warnings, and computes the single NEXT BEST ACTION from real data.

    Args:
        project_id: The SIH project ID
    """
    try:
        from Tools.hackathon_mode import activate_hackathon_mode
        h = activate_hackathon_mode(project_id)
        if "error" in h:
            return f"❌ {h['error']}"
        nba = h["next_best_action"]
        out = (
            f"🔥 HACKATHON MODE — {h['project_name']}\n════════════════════\n"
            f"🎬 Demo readiness: {h['demo_readiness']['score']}% ({h['demo_readiness']['status']}) "
            f"— {h['demo_readiness']['details']}\n"
            f"🧪 Testing: {h['testing_status']['coverage']}% coverage ({h['testing_status']['status']})\n"
            f"🚧 Blockers: {len(h['blockers'])} | 🐞 Critical bugs/risks: {len(h['critical_bugs'])} | "
            f"🔴 Unfinished core features: {len(h['unfinished_core_features'])}\n"
        )
        if h["features_to_remove"]:
            out += f"✂️ Consider removing: {', '.join(h['features_to_remove'][:3])}\n"
        out += f"\n{h['scope_creep_warning']}\n"
        out += (
            f"\n⚡ NEXT BEST ACTION:\n   → {nba['action']}\n   {nba['details']}\n"
            f"   (priority: {nba['priority']}, impact: {nba['estimated_impact']})\n"
        )
        recs = h.get("ai_recommendations", [])
        if recs:
            out += "\n🤖 AI recommendations:\n" + "".join(f"   • {r}\n" for r in recs[:5])
        return out
    except Exception as e:
        return f"❌ Hackathon mode failed: {e}"


# ================= JUDGE MODE + MOCK JURY + AUDIT =================

@function_tool()
async def start_judge_mode(project_id: int) -> str:
    """Start strict SIH JUDGE MODE practice. The judge asks one question at a
    time about your real project; after each answer you get scored on technical
    accuracy, clarity, completeness, confidence, evidence and consistency.

    Args:
        project_id: The SIH project ID
    """
    try:
        from Tools.judge_mode import start_judge_mode as _start
        j = _start(project_id)
        if "error" in j:
            return f"❌ {j['error']}"
        q = j.get("question") or "No questions available."
        return (
            f"⚖️ JUDGE MODE ACTIVATED\n════════════════════\n"
            f"👨‍⚖️ Question 1 of {j['session']['total_questions']}:\n\n   ❓ {q}\n\n"
            f"Answer it. You'll be scored and given the next question.\n"
            f"(The next question is never revealed in advance.)"
        )
    except Exception as e:
        return f"❌ Judge mode failed: {e}"


@function_tool()
async def answer_judge_question(project_id: int, question: str, answer: str) -> str:
    """Submit your answer to a judge-mode question. Returns score breakdown,
    weaknesses, correct answer direction, and the NEXT question.

    Args:
        project_id: The SIH project ID
        question: The judge's question being answered
        answer: Your answer
    """
    try:
        from Tools.judge_mode import score_answer_and_next
        r = score_answer_and_next(project_id, question, answer)
        if "error" in r:
            return f"❌ {r['error']}"
        sb = r["score_breakdown"]
        out = (
            f"📊 ANSWER SCORED: {r['overall_score']}/10\n════════════════════\n"
            + "".join(f"   {k.replace('_', ' ').title()}: {v}/10\n" for k, v in sb.items())
            + f"\n🩹 Weaknesses: {'; '.join(r['weaknesses'])}\n"
            f"🧭 Correct direction: {r['correct_answer_direction'][:250]}\n"
            f"💡 {r['improvement_note']}\n"
        )
        if r.get("next_question"):
            out += f"\n👨‍⚖️ NEXT QUESTION:\n   ❓ {r['next_question']}\n"
        else:
            out += "\n🏁 Session complete. Run start_mock_jury for the full panel."
        return out
    except Exception as e:
        return f"❌ Scoring failed: {e}"


@function_tool()
async def start_mock_jury(project_id: int) -> str:
    """Run a MULTI-JUDGE MOCK JURY panel: Technical, AI/ML, Product, Security,
    Government/Impact, Investor, End User and Hostile judges each assess your
    REAL project data and produce a final readiness report.

    Args:
        project_id: The SIH project ID
    """
    try:
        from Tools.judge_mode import start_mock_jury as _jury
        jury = _jury(project_id)
        if "error" in jury:
            return f"❌ {jury['error']}"
        fr = jury["final_report"]
        out = (
            f"👥 MULTI-JUDGE MOCK JURY\n════════════════════\n"
            f"🎯 Overall readiness: {fr['overall_readiness_score']}% → {fr['readiness_verdict']}\n\n"
            f"Per-judge highlights:\n"
        )
        for j in jury["judges_panel"]:
            a = j["assessment"]
            strengths = len(a["strengths"])
            weaks = len(a["weaknesses"])
            first_weak = a["weaknesses"][0][:70] if weaks else "none visible"
            out += f"   • {j['judge']}: {strengths}💪 / {weaks}🩹 — top issue: {first_weak}\n"
        out += (
            f"\n💪 Top strengths: {'; '.join(fr['strengths'][:4]) or 'none'}\n"
            f"🩹 Top weaknesses: {'; '.join(fr['weaknesses'][:4]) or 'none'}\n"
        )
        if fr["suspicious_unverified_claims"]:
            out += f"🚩 Flagged claims: {'; '.join(fr['suspicious_unverified_claims'][:3])}\n"
        out += "\nReadiness factors:\n" + "".join(
            f"   {k.replace('_', ' ').title()}: {v}%\n" for k, v in fr["readiness_factors"].items())
        return out
    except Exception as e:
        return f"❌ Mock jury failed: {e}"


@function_tool()
async def run_final_audit(project_id: int) -> str:
    """FINAL SIH AUDIT: checks problem alignment, novelty, implementation,
    feasibility, scalability, impact, security, docs, testing, evidence, pitch,
    cost. Findings classified CRITICAL/HIGH/MEDIUM/LOW. Project is NEVER marked
    READY while critical requirements remain unresolved.

    Args:
        project_id: The SIH project ID
    """
    try:
        from Tools.judge_mode import final_sih_audit
        audit = final_sih_audit(project_id)
        if "error" in audit:
            return f"❌ {audit['error']}"
        s = audit["summary"]
        sev_icons = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}
        out = (
            f"🏁 FINAL SIH AUDIT — {audit['project_name']}\n════════════════════\n"
            f"VERDICT: {audit['verdict']} — {audit['verdict_reason']}\n"
            f"Totals: 🔴{s['critical']} 🟠{s['high']} 🟡{s['medium']} 🟢{s['low']}\n\n"
            f"Findings:\n"
        )
        for f in audit["findings"][:12]:
            icon = sev_icons.get(f["severity"], "•")
            out += (
                f"{icon} [{f['severity']}] {f['category']}: {f['finding'][:110]}\n"
                f"      → Fix: {f['required_action'][:100]}\n"
            )
        out += f"\nℹ️ {audit['honesty_note']}"
        return out
    except Exception as e:
        return f"❌ Final audit failed: {e}"
