import { useEffect, useState } from "react";
import { api, DashboardData } from "../api/client";
import CategoryChart from "../components/CategoryChart";

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<DashboardData>("/api/reports/dashboard")
      .then((r) => setData(r.data))
      .catch((e) => setError(e.response?.data?.detail || "Falha ao carregar dashboard"));
  }, []);

  if (error) return <div className="error">{error}</div>;
  if (!data) return <div className="muted">Carregando...</div>;

  return (
    <div>
      <h2>Dashboard</h2>
      <div style={{ display: "flex", gap: 16, marginBottom: 24 }}>
        <Kpi label="Total" value={data.total} />
        <Kpi label="Críticas" value={data.critical.length} />
        <Kpi label="Bloqueadas (guardrail)" value={data.blocked} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: 16 }}>
        <CategoryChart title="Por categoria" data={data.by_category} color="#3b82f6" />
        <CategoryChart title="Por produto" data={data.by_product} color="#10b981" />
        <CategoryChart title="Por urgência" data={data.by_urgency} color="#f59e0b" />
        <CategoryChart title="Por nível de risco" data={data.by_risk} color="#ef4444" />
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>Recomendações</h3>
        <ul>
          {data.recommendations.map((r, i) => <li key={i}>{r}</li>)}
        </ul>
      </div>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: number }) {
  return (
    <div className="card" style={{ flex: 1, textAlign: "center" }}>
      <div style={{ fontSize: 32, fontWeight: 700 }}>{value}</div>
      <div className="muted">{label}</div>
    </div>
  );
}
