import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, Complaint } from "../api/client";
import UrgencyBadge from "../components/UrgencyBadge";

export default function ComplaintDetail() {
  const { id } = useParams<{ id: string }>();
  const [c, setC] = useState<Complaint | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api.get<Complaint>(`/api/complaints/${id}`)
      .then((r) => setC(r.data))
      .catch((e) => setError(e.response?.data?.detail || "Falha ao carregar"));
  }, [id]);

  if (error) return <div className="error">{error}</div>;
  if (!c) return <div className="muted">Carregando...</div>;

  const a = c.analysis;
  return (
    <div>
      <h2>Reclamação {c.id.slice(0, 8)}</h2>
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="muted" style={{ marginBottom: 4 }}>
          Canal: {c.channel || "-"} · Status: {c.status} · Criada em {new Date(c.created_at).toLocaleString("pt-BR")}
        </div>
        <h4 style={{ marginBottom: 4 }}>Texto original</h4>
        <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{c.raw_text}</p>
      </div>

      {a?.blocked ? (
        <div className="card" style={{ borderLeft: "4px solid #dc2626" }}>
          <h3 style={{ marginTop: 0, color: "#991b1b" }}>Bloqueada pelo guardrail</h3>
          <p>{a.block_reason || "Conteúdo não pôde ser processado."}</p>
        </div>
      ) : a ? (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <div className="card">
            <h3 style={{ marginTop: 0 }}>Triagem</h3>
            <p><strong>Categoria:</strong> {a.category || "-"}</p>
            <p><strong>Produto:</strong> {a.product || "-"}</p>
            <p><strong>Sentimento:</strong> {a.sentiment || "-"}</p>
            <p><strong>Urgência:</strong> <UrgencyBadge value={a.urgency} /></p>
            <p><strong>Resumo:</strong></p>
            <p style={{ whiteSpace: "pre-wrap" }}>{a.summary || "-"}</p>
          </div>
          <div className="card">
            <h3 style={{ marginTop: 0 }}>Risco e conformidade</h3>
            <p><strong>Nível de risco:</strong> <UrgencyBadge value={a.risk_level} /></p>
            <p><strong>Justificativa:</strong></p>
            <p style={{ whiteSpace: "pre-wrap" }}>{a.risk_justification || "-"}</p>
          </div>
        </div>
      ) : (
        <div className="muted">Análise indisponível.</div>
      )}
    </div>
  );
}
