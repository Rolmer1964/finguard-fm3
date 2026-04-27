import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Complaint } from "../api/client";
import UrgencyBadge from "../components/UrgencyBadge";

export default function Complaints() {
  const [items, setItems] = useState<Complaint[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<Complaint[]>("/api/complaints/")
      .then((r) => setItems(r.data))
      .catch((e) => setError(e.response?.data?.detail || "Falha ao carregar reclamações"));
  }, []);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>Reclamações</h2>
        <Link to="/complaints/new"><button>+ Nova reclamação</button></Link>
      </div>
      {error && <div className="error">{error}</div>}
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>ID</th><th>Categoria</th><th>Produto</th><th>Urgência</th><th>Risco</th><th>Status</th><th>Data</th>
            </tr>
          </thead>
          <tbody>
            {items.map((c) => (
              <tr key={c.id}>
                <td><Link to={`/complaints/${c.id}`}>{c.id.slice(0, 8)}</Link></td>
                <td>{c.analysis?.category || "-"}</td>
                <td>{c.analysis?.product || c.product_hint || "-"}</td>
                <td><UrgencyBadge value={c.analysis?.urgency} /></td>
                <td><UrgencyBadge value={c.analysis?.risk_level} /></td>
                <td>{c.status}</td>
                <td>{new Date(c.created_at).toLocaleString("pt-BR")}</td>
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={7} className="muted">Nenhuma reclamação ainda.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
