import { createContext, useContext, useState, ReactNode } from "react";

interface User {
  role: "admin" | "user" | null;
  name: string;
  title: string;
}

interface AuthContextType {
  isAuthenticated: boolean;
  user: User;
  login: (username: string, password: string) => boolean;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<User>({ role: null, name: "", title: "" });

  const login = (username: string, password: string) => {
    if (username === "admin" && password === "admin123") {
      setIsAuthenticated(true);
      setUser({ role: "admin", name: "Dr. Subhra Mohanty", title: "R&D head" });
      return true;
    } else if (username === "user" && password === "user123") {
      setIsAuthenticated(true);
      setUser({ role: "user", name: "user", title: "R&D Scientist" });
      return true;
    }
    return false;
  };

  const logout = () => {
    setIsAuthenticated(false);
    setUser({ role: null, name: "", title: "" });
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
