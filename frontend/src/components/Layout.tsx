import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/useAuth";

export default function Layout() {
  const { user, logout } = useAuth();
  const navStyle = ({ isActive }: { isActive: boolean }) => ({
    padding: "8px 12px",
    borderRadius: 6,
    color: isActive ? "white" : "#1f2937",
    background: isActive ? "#2563eb" : "transparent",
    fontWeight: 500 as const,
    fontSize: 14,
  });
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header style={{ borderBottom: "1px solid #e5e7eb", background: "white", padding: "12px 24px", display: "flex", alignItems: "center", gap: 24 }}>
        <Link to="/" style={{ fontWeight: 700, fontSize: 18, color: "#1f2937" }}>FinGuard</Link>
        <nav style={{ display: "flex", gap: 4, flex: 1 }}>
          <NavLink to="/" end style={navStyle}>Dashboard</NavLink>
          <NavLink to="/complaints" style={navStyle}>Reclamações</NavLink>
          <NavLink to="/complaints/new" style={navStyle}>Nova</NavLink>
          <NavLink to="/reports" style={navStyle}>Relatórios</NavLink>
        </nav>
        <div className="muted">{user?.email}</div>
        <button className="secondary" onClick={logout}>Sair</button>
      </header>
      <main style={{ padding: 24, maxWidth: 1200, margin: "0 auto", width: "100%" }}>
        <Outlet />
      </main>
    </div>
  );
}
