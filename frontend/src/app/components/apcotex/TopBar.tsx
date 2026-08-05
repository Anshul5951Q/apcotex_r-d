import { useState } from "react";
import { useNavigate } from "react-router";
import { Search, Bell, ChevronDown, LogOut } from "lucide-react";
import { useAuth } from "../../contexts/AuthContext";

const BORDER = "#E5E7EB";
const BLUE = "#1F5FA8";
const RED = "#D93A2F";
const RED_TINT = "rgba(217,58,47,0.06)";
const RED_BORDER = "rgba(217,58,47,0.16)";

interface TopBarProps {
  userName: string;
}

export function TopBar({ userName }: TopBarProps) {
  const [search, setSearch] = useState("");
  const [showUserMenu, setShowUserMenu] = useState(false);
  const navigate = useNavigate();
  const { logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div
      style={{
        height: 56,
        background: "white",
        borderBottom: `1px solid ${BORDER}`,
        display: "flex",
        alignItems: "center",
        padding: "0 24px",
        gap: 16,
        flexShrink: 0,
      }}
    >
      {/* Search */}
      <div
        style={{ flex: 1, maxWidth: 400, position: "relative" }}
      >
        <Search
          size={15}
          style={{
            position: "absolute",
            left: 11,
            top: "50%",
            transform: "translateY(-50%)",
            color: "#9CA3AF",
            pointerEvents: "none",
          }}
        />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search projects, recipes, compounds…"
          style={{
            width: "100%",
            height: 34,
            paddingLeft: 34,
            paddingRight: 12,
            border: `1px solid ${BORDER}`,
            borderRadius: 6,
            fontSize: "0.8125rem",
            color: "#374151",
            background: "#F9FAFB",
            outline: "none",
            fontFamily: "inherit",
            transition:
              "border-color 0.15s, box-shadow 0.15s, background 0.15s",
          }}
          onFocus={(e) => {
            (e.target as HTMLInputElement).style.borderColor =
              BLUE;
            (e.target as HTMLInputElement).style.boxShadow =
              `0 0 0 2px rgba(31,95,168,0.12)`;
            (e.target as HTMLInputElement).style.background =
              "white";
          }}
          onBlur={(e) => {
            (e.target as HTMLInputElement).style.borderColor =
              BORDER;
            (e.target as HTMLInputElement).style.boxShadow =
              "none";
            (e.target as HTMLInputElement).style.background =
              "#F9FAFB";
          }}
        />
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginLeft: "auto",
        }}
      >
        {/* Quarter badge */}
        <span
          style={{
            fontSize: "0.75rem",
            color: "#6B7280",
            background: "#F9FAFB",
            padding: "3px 10px",
            borderRadius: 20,
            border: `1px solid ${BORDER}`,
            display: "inline-flex",
            alignItems: "center",
            gap: 7,
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: RED,
              flexShrink: 0,
            }}
          />
          Q2 2026
        </span>

        {/* Notifications */}
        <button
          style={{
            width: 34,
            height: 34,
            borderRadius: 6,
            border: `1px solid ${RED_BORDER}`,
            background: RED_TINT,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            position: "relative",
            transition: "all 0.15s ease",
          }}
          onMouseEnter={(e) => {
            const el = e.currentTarget;
            el.style.background = "rgba(217,58,47,0.10)";
            el.style.boxShadow =
              "0 2px 8px rgba(217,58,47,0.10)";
          }}
          onMouseLeave={(e) => {
            const el = e.currentTarget;
            el.style.background = RED_TINT;
            el.style.boxShadow = "none";
          }}
        >
          <Bell size={15} color={RED} />
          <span
            style={{
              position: "absolute",
              top: 6,
              right: 6,
              width: 8,
              height: 8,
              background: RED,
              borderRadius: "50%",
              border: "1.5px solid white",
              boxShadow: "0 0 0 1px rgba(217,58,47,0.12)",
            }}
          />
        </button>

        {/* User */}
        <div style={{ position: "relative" }}>
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "0 10px",
              height: 34,
              border: `1px solid ${BORDER}`,
              borderRadius: 6,
              background: "white",
              cursor: "pointer",
              transition: "border-color 0.15s, box-shadow 0.15s",
            }}
            onMouseEnter={(e) => {
              const el = e.currentTarget;
              el.style.borderColor = "#D1D5DB";
              el.style.boxShadow =
                "0 1px 3px rgba(31,95,168,0.06)";
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget;
              el.style.borderColor = BORDER;
              el.style.boxShadow = "none";
            }}
          >
            <div
              style={{
                width: 22,
                height: 22,
                borderRadius: "50%",
                background: BLUE,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow:
                  "inset 0 0 0 1px rgba(255,255,255,0.16)",
              }}
            >
              <span
                style={{
                  color: "white",
                  fontSize: "0.5625rem",
                  fontWeight: 700,
                }}
              >
                {userName.charAt(0).toUpperCase()}
              </span>
            </div>
            <span
              style={{
                fontSize: "0.8125rem",
                color: "#374151",
                fontWeight: 500,
              }}
            >
              {userName}
            </span>
            <ChevronDown size={13} color="#9CA3AF" />
          </button>

          {showUserMenu && (
            <>
              <div
                style={{
                  position: "fixed",
                  top: 0,
                  left: 0,
                  right: 0,
                  bottom: 0,
                  zIndex: 9,
                }}
                onClick={() => setShowUserMenu(false)}
              />
              <div
                style={{
                  position: "absolute",
                  top: "calc(100% + 8px)",
                  right: 0,
                  width: 180,
                  background: "white",
                  border: `1px solid ${BORDER}`,
                  borderRadius: 6,
                  boxShadow:
                    "0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04)",
                  zIndex: 10,
                }}
              >
                <button
                  onClick={handleLogout}
                  style={{
                    width: "100%",
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "10px 14px",
                    border: "none",
                    background: "transparent",
                    cursor: "pointer",
                    fontSize: "0.8125rem",
                    color: "#374151",
                    fontFamily: "inherit",
                    transition: "background 0.15s",
                  }}
                  onMouseEnter={(e) => {
                    (e.target as HTMLButtonElement).style.background =
                      "#F9FAFB";
                  }}
                  onMouseLeave={(e) => {
                    (e.target as HTMLButtonElement).style.background =
                      "transparent";
                  }}
                >
                  <LogOut size={14} />
                  Sign Out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}