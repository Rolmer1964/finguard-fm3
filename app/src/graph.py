import logging
import time
import uuid
from typing import TypedDict

from langgraph.graph import END, StateGraph

from .agents.report import consolidate
from .agents.risk import run_risk
from .agents.triage import run_triage
from .guardrails.input_guard import POLITE_BLOCK_MESSAGE, check_input
from .guardrails.output_guard import sanitize_payload

logger = logging.getLogger("graph")


class AnalysisState(TypedDict, total=False):
    trace_id: str
    text: str
    product_hint: str | None
    blocked: bool
    block_reason: str | None
    triage: dict
    risk: dict
    final: dict
    timings_ms: dict


def _now_ms() -> int:
    return int(time.time() * 1000)


def _node_input_guard(state: AnalysisState) -> AnalysisState:
    t0 = _now_ms()
    tid = state.get("trace_id", "?")
    logger.info("[%s] NODE=input_guard IN text_len=%d", tid, len(state.get("text", "")))
    result = check_input(state["text"])
    dt = _now_ms() - t0
    logger.info("[%s] NODE=input_guard OUT in %dms allowed=%s", tid, dt, result["allowed"])
    timings = {**state.get("timings_ms", {}), "input_guard": dt}
    if not result["allowed"]:
        return {**state, "blocked": True, "block_reason": result["reason"], "timings_ms": timings}
    return {**state, "blocked": False, "timings_ms": timings}


def _node_triage(state: AnalysisState) -> AnalysisState:
    t0 = _now_ms()
    tid = state.get("trace_id", "?")
    logger.info("[%s] AGENT=triage IN text_len=%d product_hint=%s", tid, len(state.get("text", "")), state.get("product_hint"))
    triage = run_triage(state["text"], state.get("product_hint"))
    dt = _now_ms() - t0
    logger.info("[%s] AGENT=triage OUT in %dms category=%s product=%s urgency=%s", tid, dt, triage.get("category"), triage.get("product"), triage.get("urgency"))
    timings = {**state.get("timings_ms", {}), "triage": dt}
    return {**state, "triage": triage, "timings_ms": timings}


def _node_risk(state: AnalysisState) -> AnalysisState:
    t0 = _now_ms()
    tid = state.get("trace_id", "?")
    logger.info("[%s] AGENT=risk IN triage_keys=%s", tid, list(state.get("triage", {}).keys()))
    risk = run_risk(state["text"], state.get("triage", {}))
    dt = _now_ms() - t0
    logger.info("[%s] AGENT=risk OUT in %dms level=%s", tid, dt, risk.get("risk_level"))
    timings = {**state.get("timings_ms", {}), "risk": dt}
    return {**state, "risk": risk, "timings_ms": timings}


def _node_report(state: AnalysisState) -> AnalysisState:
    t0 = _now_ms()
    tid = state.get("trace_id", "?")
    logger.info("[%s] AGENT=report IN", tid)
    final = consolidate(state.get("triage", {}), state.get("risk", {}))
    dt = _now_ms() - t0
    logger.info("[%s] AGENT=report OUT in %dms", tid, dt)
    timings = {**state.get("timings_ms", {}), "report": dt}
    return {**state, "final": final, "timings_ms": timings}


def _node_output_guard(state: AnalysisState) -> AnalysisState:
    t0 = _now_ms()
    tid = state.get("trace_id", "?")
    logger.info("[%s] NODE=output_guard IN", tid)
    sanitized = sanitize_payload(state.get("final", {}))
    dt = _now_ms() - t0
    pii = sanitized.get("_pii_redacted") or []
    logger.info("[%s] NODE=output_guard OUT in %dms pii_redacted=%s", tid, dt, pii)
    timings = {**state.get("timings_ms", {}), "output_guard": dt}
    return {**state, "final": sanitized, "timings_ms": timings}


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


def analyze(text: str, product_hint: str | None = None) -> dict:
    """Executa o grafo completo (com guardrails) e devolve o payload final."""
    trace_id = uuid.uuid4().hex[:8]
    state: AnalysisState = {"trace_id": trace_id, "text": text, "product_hint": product_hint}
    logger.info("[%s] GRAPH START", trace_id)
    final_state = get_graph().invoke(state)
    logger.info("[%s] GRAPH END timings=%s", trace_id, final_state.get("timings_ms"))

    if final_state.get("blocked"):
        return {
            "trace_id": trace_id,
            "blocked": True,
            "block_reason": final_state.get("block_reason") or POLITE_BLOCK_MESSAGE,
            "timings_ms": final_state.get("timings_ms", {}),
        }

    return {
        "trace_id": trace_id,
        "blocked": False,
        **final_state.get("final", {}),
        "timings_ms": final_state.get("timings_ms", {}),
    }
