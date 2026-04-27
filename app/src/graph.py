import logging
import time
import uuid
from typing import TypedDict

from langgraph.graph import END, StateGraph

from .agents.report import consolidate
from .agents.risk import run_risk
from .agents.triage import run_triage

logger = logging.getLogger("graph")


class AnalysisState(TypedDict, total=False):
    trace_id: str
    text: str
    product_hint: str | None
    triage: dict
    risk: dict
    final: dict
    timings_ms: dict


def _now_ms() -> int:
    return int(time.time() * 1000)


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


def build_graph():
    g = StateGraph(AnalysisState)
    g.add_node("step_triage", _node_triage)
    g.add_node("step_risk", _node_risk)
    g.add_node("step_report", _node_report)
    g.set_entry_point("step_triage")
    g.add_edge("step_triage", "step_risk")
    g.add_edge("step_risk", "step_report")
    g.add_edge("step_report", END)
    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def analyze(text: str, product_hint: str | None = None) -> dict:
    """Executa o grafo completo e devolve o payload final + timings + trace_id."""
    trace_id = uuid.uuid4().hex[:8]
    state: AnalysisState = {"trace_id": trace_id, "text": text, "product_hint": product_hint}
    logger.info("[%s] GRAPH START", trace_id)
    final_state = get_graph().invoke(state)
    logger.info("[%s] GRAPH END timings=%s", trace_id, final_state.get("timings_ms"))
    return {
        "trace_id": trace_id,
        **final_state.get("final", {}),
        "timings_ms": final_state.get("timings_ms", {}),
    }
