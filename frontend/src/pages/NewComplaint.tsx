import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Complaint } from "../api/client";

const CHANNELS = ["SAC", "Ouvidoria", "Banco Central", "Procon", "Redes Sociais"];

export default function NewComplaint() {
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [channel, setChannel] = useState("SAC");
  const [productHint, setProductHint] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { data } = await api.post<Complaint>("/api/complaints/", {
        text,
        channel,
        product_hint: productHint || null,
      });
      navigate(`/complaints/${data.id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Falha ao enviar reclamação");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h2>Nova reclamação</h2>
      <form onSubmit={onSubmit} className="card" style={{ maxWidth: 720 }}>
        <label style={{ fontSize: 13, fontWeight: 500 }}>Canal</label>
        <select value={channel} onChange={(e) => setChannel(e.target.value)}>
          {CHANNELS.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <label style={{ fontSize: 13, fontWeight: 500, display: "block", marginTop: 12 }}>Produto (opcional)</label>
        <input value={productHint} onChange={(e) => setProductHint(e.target.value)} placeholder="Ex.: Cartão de Crédito" />
        <label style={{ fontSize: 13, fontWeight: 500, display: "block", marginTop: 12 }}>Texto da reclamação</label>
        <textarea
          rows={8}
          value={text}
          onChange={(e) => setText(e.target.value)}
          required
          placeholder="Descreva a situação relatada pelo cliente..."
        />
        {error && <div className="error">{error}</div>}
        <p className="muted" style={{ marginTop: 12 }}>A análise pode levar de 5 a 15 segundos enquanto os agentes processam.</p>
        <button type="submit" disabled={loading} style={{ marginTop: 12 }}>
          {loading ? "Analisando..." : "Enviar e analisar"}
        </button>
      </form>
    </div>
  );
}
