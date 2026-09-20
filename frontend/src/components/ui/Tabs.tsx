import type { ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { palette, motion } from "../../styles/theme";

export interface TabItem {
  id: string;
  label: string;
  icon?: ReactNode;
}

export function useTab(
  values: string[],
  fallback: string,
  param = "tab",
): [string, (id: string) => void] {
  const [params, setParams] = useSearchParams();
  const raw = params.get(param);
  const active = raw && values.includes(raw) ? raw : fallback;
  const setTab = (id: string) => {
    const next = new URLSearchParams(params);
    next.set(param, id);
    setParams(next, { replace: true });
  };
  return [active, setTab];
}

export function TabBar({
  items,
  active,
  onSelect,
}: {
  items: TabItem[];
  active: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        gap: 6,
        flexWrap: "wrap",
        alignItems: "center",
        marginBottom: 18,
        paddingBottom: 10,
        borderBottom: `1px solid ${palette.borderSoft}`,
      }}
    >
      {items.map((it) => {
        const isActive = active === it.id;
        return (
          <button
            key={it.id}
            onClick={() => onSelect(it.id)}
            style={{
              appearance: "none",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: 7,
              padding: "6px 13px",
              borderRadius: 8,
              fontSize: 12.5,
              fontWeight: 600,
              color: isActive ? palette.accent : palette.textDim,
              background: isActive ? palette.accentSoft : "transparent",
              border: `1px solid ${isActive ? palette.accentBorder : palette.border}`,
              transition: `background ${motion.fast}, color ${motion.fast}, border-color ${motion.fast}`,
            }}
          >
            {it.icon && (
              <span style={{ fontSize: 13, opacity: isActive ? 1 : 0.7 }}>{it.icon}</span>
            )}
            {it.label}
          </button>
        );
      })}
    </div>
  );
}