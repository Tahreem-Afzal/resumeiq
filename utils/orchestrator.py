"""
LangGraph orchestrator for the three analysis-time agents:

    START ─┬─> resume_optimizer_node ───────────────┬─> END
           └─> market_intel_node ─> gap_roadmap_node ┘

- resume_optimizer_node and market_intel_node run independently off the
  same inputs (no shared dependency), so they're wired as parallel
  branches from START.
- gap_roadmap_node depends on market_intel_node's output, so it's
  chained after it.

The Mock Interview Agent (utils/agents/mock_interview.py) is NOT part of
this graph — it's an inherently multi-turn, session-persisted
conversation (one question/answer per HTTP request), so it's driven
directly from Flask via run_interview_turn(), the same way
utils/chatbot.py's chat_with_resume() is used outside any graph.

Run this graph right after (or instead of) utils.analyzer.analyze_resume,
once you have resume_text (+ optionally job_description and the existing
analysis_report).
"""
from langgraph.graph import StateGraph, START, END

from utils.agent_state import AgentState
from utils.resume_optimizer import optimize_resume
from utils.market_intel import get_market_intel
from utils.roadmap import run_gap_and_roadmap


def _resume_optimizer_node(state: AgentState) -> dict:
    try:
        result = optimize_resume(state["resume_text"], state.get("job_description", ""))
        return {"optimized_resume": result}
    except Exception as e:
        return {"optimized_resume": {}, "errors": state.get("errors", []) + [f"resume_optimizer: {e}"]}


def _market_intel_node(state: AgentState) -> dict:
    try:
        result = get_market_intel(state["resume_text"], state.get("job_description", ""))
        return {"market_intel": result}
    except Exception as e:
        return {"market_intel": {}, "errors": state.get("errors", []) + [f"market_intel: {e}"]}


def _gap_roadmap_node(state: AgentState) -> dict:
    market_intel = state.get("market_intel") or {}
    if not market_intel.get("in_demand_skills"):
        return {"skill_gap": {}, "roadmap": {}, "errors": state.get("errors", []) + ["gap_roadmap: no market_intel available"]}
    try:
        result = run_gap_and_roadmap(
            state["resume_text"],
            market_intel.get("matched_role", "Unknown role"),
            market_intel["in_demand_skills"],
        )
        return {"skill_gap": result["skill_gap"], "roadmap": result["roadmap"]}
    except Exception as e:
        return {"skill_gap": {}, "roadmap": {}, "errors": state.get("errors", []) + [f"gap_roadmap: {e}"]}


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("resume_optimizer", _resume_optimizer_node)
    graph.add_node("market_intel", _market_intel_node)
    graph.add_node("gap_roadmap", _gap_roadmap_node)

    graph.add_edge(START, "resume_optimizer")
    graph.add_edge(START, "market_intel")
    graph.add_edge("market_intel", "gap_roadmap")
    graph.add_edge("resume_optimizer", END)
    graph.add_edge("gap_roadmap", END)

    return graph.compile()


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


def run_pipeline(resume_text: str, job_description: str = "", analysis_report: dict = None) -> dict:
    """
    Runs the full agent pipeline and returns the final state as a plain dict:
      {
        "optimized_resume": {...},
        "market_intel": {...},
        "skill_gap": {...},
        "roadmap": {...},
        "errors": [...]
      }
    """
    initial_state: AgentState = {
        "resume_text": resume_text,
        "job_description": job_description or "",
        "analysis_report": analysis_report or {},
        "errors": [],
    }
    graph = get_graph()
    final_state = graph.invoke(initial_state)
    return dict(final_state)