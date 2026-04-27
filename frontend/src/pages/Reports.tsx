const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function buildUrl(path: string) {
  const token = localStorage.getItem("finguard_token");
  return `${baseURL}${path}${path.includes("?") ? "&" : "?"}token_hint=${token ? "set" : "none"}`;
}

export default function Reports() {
  return (
    <div>
      <h2>Relatórios e ADR</h2>
      <p className="muted">Os links abaixo abrem os relatórios em uma nova aba. O token JWT é necessário — caso a aba peça login novamente, faça login e tente de novo.</p>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Relatório gerencial (HTML)</h3>
        <p>Visão geral com gráficos por categoria, produto, urgência e risco, lista de críticas e recomendações.</p>
        <a href={buildUrl("/api/reports/html")} target="_blank" rel="noreferrer"><button>Abrir relatório HTML</button></a>
        <a href={buildUrl("/api/reports/html?save=true")} target="_blank" rel="noreferrer" style={{ marginLeft: 8 }}>
          <button className="secondary">Salvar arquivo no servidor</button>
        </a>
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>ADR (Architectural Decision Record)</h3>
        <p>Documento navegável com contexto, alternativas, decisão, custos e recomendações de segurança.</p>
        <a href={buildUrl("/api/reports/adr")} target="_blank" rel="noreferrer"><button>Abrir ADR</button></a>
        <a href={buildUrl("/api/reports/adr?save=true")} target="_blank" rel="noreferrer" style={{ marginLeft: 8 }}>
          <button className="secondary">Salvar arquivo no servidor</button>
        </a>
      </div>
      <div className="card" style={{ marginTop: 16, background: "#fef3c7", borderLeft: "4px solid #f59e0b" }}>
        <strong>Observação:</strong> os endpoints HTML/ADR exigem JWT no cabeçalho Authorization. Para visualização em nova aba, prefira <em>Salvar no servidor</em> e acessar o arquivo gerado em <code>data/reports/</code> ou <code>docs/</code>.
      </div>
    </div>
  );
}
