import logging
import time
from typing import TypedDict

from langgraph.graph import END, StateGraph

from .agents.report import consolidate
from .agents.risk import run_risk
from .agents.triage import run_triage
from .guardrails.input_guard import check_input
from .guardrails.output_guard import sanitize_payload

logger = logging.getLogger("orchestrator.graph")


class AnalysisState(TypedDict, total=False):
    complaint_id: str
    text: str
    product_hint: str | None
    blocked: bool
    block_reason: str | None
    triage: dict
    risk: dict
    final: dict


def _node_input_guard(state: AnalysisState) -> AnalysisState:
    t0 = time.time()
    result = check_input(state["text"])
    logger.info("[%s] input_guard allowed=%s in %.2fs", state.get("complaint_id"), result["allowed"], time.time() - t0)
    if not result["allowed"]:
        return {**state, "blocked": True, "block_reason": result["reason"]}
    return {**state, "blocked": False}


def _node_triage(state: AnalysisState) -> AnalysisState:
    t0 = time.time()
    triage = run_triage(state["text"], state.get("product_hint"))
    logger.info("[%s] triage done in %.2fs cat=%s urg=%s", state.get("complaint_id"), time.time() - t0, triage.get("category"), triage.get("urgency"))
    return {**state, "triage": triage}


def _node_risk(state: AnalysisState) -> AnalysisState:
    t0 = time.time()
    risk = run_risk(state["text"], state.get("triage", {}))
    logger.info("[%s] risk done in %.2fs level=%s", state.get("complaint_id"), time.time() - t0, risk.get("risk_level"))
    return {**state, "risk": risk}


def _node_report(state: AnalysisState) -> AnalysisState:
    final = consolidate(state.get("triage", {}), state.get("risk", {}))
    return {**state, "final": final}


def _node_output_guard(state: AnalysisState) -> AnalysisState:
    final = sanitize_payload(state.get("final", {}))
    return {**state, "final": final}


def _route_after_input(state: AnalysisState) -> str:
    return "blocked" if state.get("blocked") else "pass"


def build_graph():
    g = StateGraph(AnalysisState)
    g.add_node("input_guard", _node_input_guard)
    g.add_node("triage", _node_triage)
    g.add_node("risk", _node_risk)
    g.add_node("report", _node_report)
    g.add_node("output_guard", _node_output_guard)

    g.set_entry_point("input_guard")
    g.add_conditional_edges("input_guard", _route_after_input, {"pass": "triage", "blocked": END})
    g.add_edge("triage", "risk")
    g.add_edge("risk", "report")
    g.add_edge("report", "output_guard")
    g.add_edge("output_guard", END)
    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
