import datetime
import logging
import time
import uuid
from collections import deque
from typing import TypedDict

from langgraph.graph import END, StateGraph

from .agents.guardrail import BLOCKED_INPUT_MESSAGE, check_input, sanitize_output
from .agents.report import consolidate
from .agents.risk import run_risk
from .agents.triage import run_triage

logger = logging.getLogger("graph")

_traces: deque = deque()


class AnalysisState(TypedDict, total=False):
    trace_id: str
    text: str
    product_hint: str | None
    guardrail_input: dict
    triage: dict
    risk: dict
    final: dict
    timings_ms: dict


def _now_ms() -> int:
    return int(time.time() * 1000)


def sum_timings(tm: dict) -> int:
    return (
        (tm.get("guardrail_input") or 0)
        + (tm.get("triage") or 0)
        + (tm.get("risk") or 0)
        + (tm.get("report") or 0)
        + (tm.get("guardrail_output") or 0)
    )


# ── Nó 0: Guardrail de entrada ────────────────────────────────────────────────

def _node_guardrail_input(state: AnalysisState) -> AnalysisState:
    t0  = _now_ms()
    tid = state.get("trace_id", "?")
    logger.info("[%s] AGENT=guardrail_input IN text_len=%d", tid, len(state.get("text", "")))
    result = check_input(state["text"])
    dt = _now_ms() - t0
    logger.info(
        "[%s] AGENT=guardrail_input OUT in %dms blocked=%s reason=%s",
        tid, dt, result["blocked"], result.get("reason"),
    )
    timings = {**state.get("timings_ms", {}), "guardrail_input": dt}
    new_state: AnalysisState = {**state, "guardrail_input": result, "timings_ms": timings}
    if not result["blocked"]:
        new_state["text"] = result["sanitized_text"]
    return new_state


def _route_after_guardrail(state: AnalysisState) -> str:
    return "step_blocked" if state.get("guardrail_input", {}).get("blocked") else "step_triage"


def _node_blocked(state: AnalysisState) -> AnalysisState:
    """Resposta educada quando o guardrail de entrada bloqueia a requisição."""
    gi = state.get("guardrail_input", {})
    final: dict = {"blocked": True, "message": BLOCKED_INPUT_MESSAGE}
    if gi.get("block_reason"):
        final["block_reason"] = gi["block_reason"]
    return {**state, "final": final}


# ── Nó 1: Triagem ─────────────────────────────────────────────────────────────

def _node_triage(state: AnalysisState) -> AnalysisState:
    t0  = _now_ms()
    tid = state.get("trace_id", "?")
    logger.info(
        "[%s] AGENT=triage IN text_len=%d product_hint=%s",
        tid, len(state.get("text", "")), state.get("product_hint"),
    )
    triage = run_triage(state["text"], state.get("product_hint"))
    dt = _now_ms() - t0
    logger.info(
        "[%s] AGENT=triage OUT in %dms category=%s product=%s urgency=%s",
        tid, dt, triage.get("category"), triage.get("product"), triage.get("urgency"),
    )
    timings = {**state.get("timings_ms", {}), "triage": dt}
    return {**state, "triage": triage, "timings_ms": timings}


# ── Nó 2: Risco + RAG ─────────────────────────────────────────────────────────

def _node_risk(state: AnalysisState) -> AnalysisState:
    t0  = _now_ms()
    tid = state.get("trace_id", "?")
    logger.info("[%s] AGENT=risk IN triage_keys=%s", tid, list(state.get("triage", {}).keys()))
    risk = run_risk(state["text"], state.get("triage", {}))
    dt = _now_ms() - t0
    logger.info(
        "[%s] AGENT=risk OUT in %dms level=%s rag_chunks=%s",
        tid, dt, risk.get("risk_level"), risk.get("rag_chunks_used"),
    )
    timings = {**state.get("timings_ms", {}), "risk": dt}
    return {**state, "risk": risk, "timings_ms": timings}


# ── Nó 3: Relatório ───────────────────────────────────────────────────────────

def _node_report(state: AnalysisState) -> AnalysisState:
    t0  = _now_ms()
    tid = state.get("trace_id", "?")
    logger.info("[%s] AGENT=report IN", tid)
    final = consolidate(state.get("triage", {}), state.get("risk", {}))
    dt = _now_ms() - t0
    logger.info("[%s] AGENT=report OUT in %dms", tid, dt)
    timings = {**state.get("timings_ms", {}), "report": dt}
    return {**state, "final": final, "timings_ms": timings}


# ── Nó 4: Guardrail de saída ──────────────────────────────────────────────────

def _node_guardrail_output(state: AnalysisState) -> AnalysisState:
    t0  = _now_ms()
    tid = state.get("trace_id", "?")
    logger.info("[%s] AGENT=guardrail_output IN", tid)
    final = dict(state.get("final", {}))
    for field in ("texto_original", "summary", "risk_justification"):
        if final.get(field):
            final[field] = sanitize_output(final[field], field=field)
    dt = _now_ms() - t0
    logger.info("[%s] AGENT=guardrail_output OUT in %dms", tid, dt)
    timings = {**state.get("timings_ms", {}), "guardrail_output": dt}
    return {**state, "final": final, "timings_ms": timings}


# ── Montagem do grafo ─────────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(AnalysisState)

    g.add_node("step_guardrail_input",  _node_guardrail_input)
    g.add_node("step_blocked",          _node_blocked)
    g.add_node("step_triage",           _node_triage)
    g.add_node("step_risk",             _node_risk)
    g.add_node("step_report",           _node_report)
    g.add_node("step_guardrail_output", _node_guardrail_output)

    g.set_entry_point("step_guardrail_input")
    g.add_conditional_edges(
        "step_guardrail_input",
        _route_after_guardrail,
        {"step_blocked": "step_blocked", "step_triage": "step_triage"},
    )
    g.add_edge("step_blocked",          END)
    g.add_edge("step_triage",           "step_risk")
    g.add_edge("step_risk",             "step_report")
    g.add_edge("step_report",           "step_guardrail_output")
    g.add_edge("step_guardrail_output", END)

    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


# ── Trace store ───────────────────────────────────────────────────────────────

def _store_trace(trace_id: str, text: str, result: dict) -> None:
    tm = result.get("timings_ms", {})
    _traces.appendleft({
        "trace_id":     trace_id,
        "timestamp":    datetime.datetime.now().strftime("%H:%M:%S"),
        "text_preview": (text[:70] + "…") if len(text) > 70 else text,
        "blocked":      result.get("blocked", False),
        "category":     result.get("category"),
        "urgency":      result.get("urgency"),
        "risk_level":   result.get("risk_level"),
        "timings_ms":   tm,
        "total_ms": sum_timings(tm),
    })


def get_traces() -> list:
    return list(_traces)


def clear_traces() -> int:
    n = len(_traces)
    _traces.clear()
    return n


def inject_trace(entry: dict) -> None:
    """Insere entrada de trace diretamente no store (recomposição de log a partir de relatório)."""
    _traces.appendleft(entry)


# ── Ponto de entrada público ──────────────────────────────────────────────────

def analyze(text: str, product_hint: str | None = None, record_id: str | None = None) -> dict:
    """Executa o grafo completo e devolve payload final + estado intermediário + timings."""
    trace_id = record_id or uuid.uuid4().hex[:8]
    state: AnalysisState = {"trace_id": trace_id, "text": text, "product_hint": product_hint}
    logger.info("[%s] GRAPH START", trace_id)
    final_state = get_graph().invoke(state)
    logger.info("[%s] GRAPH END timings=%s", trace_id, final_state.get("timings_ms"))

    final_payload = final_state.get("final", {})
    result = {
        "trace_id": trace_id,
        "blocked":  final_payload.get("blocked", False),
        "triage":   final_state.get("triage", {}),
        "risk":     final_state.get("risk", {}),
        **final_payload,
        "timings_ms": final_state.get("timings_ms", {}),
    }
    _store_trace(trace_id, text, result)
    return result
