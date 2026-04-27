import { createContext, ReactNode, useEffect, useState } from "react";
import { api } from "../api/client";

interface UserClaims {
  sub: string;
  email: string;
  name?: string;
  role: string;
  exp: number;
}

interface AuthCtx {
  user: UserClaims | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthCtx>({
  user: null,
  loading: true,
  login: async () => {},
  logout: () => {},
});

function decodeJwt(token: string): UserClaims | null {
  try {
    const payload = token.split(".")[1];
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json);
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserClaims | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("finguard_token");
    if (token) {
      const claims = decodeJwt(token);
      if (claims && claims.exp * 1000 > Date.now()) setUser(claims);
      else localStorage.removeItem("finguard_token");
    }
    setLoading(false);
  }, []);

  async function login(email: string, password: string) {
    const { data } = await api.post("/api/auth/login", { email, password });
    localStorage.setItem("finguard_token", data.access_token);
    const claims = decodeJwt(data.access_token);
    setUser(claims);
  }

  function logout() {
    localStorage.removeItem("finguard_token");
    setUser(null);
  }

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}
