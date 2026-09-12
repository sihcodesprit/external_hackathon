import type { ButtonHTMLAttributes, ReactNode } from "react";
import { palette, radius, motion } from "../../styles/theme";

type Variant = "primary" | "ghost" | "danger" | "outline";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  children: ReactNode;
}

const sizeMap: Record<Size, React.CSSProperties> = {
  sm: { padding: "5px 10px", fontSize: 12 },
  md: { padding: "8px 16px", fontSize: 13 },
  lg: { padding: "12px 22px", fontSize: 14 },
};

const variantMap: Record<Variant, React.CSSProperties> = {
  primary: {
    background: "linear-gradient(135deg, #164e63 0%, #0f766e 100%)",
    color: "#e7f7ff",
    border: "1px solid rgba(34,211,238,0.45)",
    boxShadow: "0 0 18px rgba(34,211,238,0.18)",
  },
  ghost: {
    background: "transparent",
    color: palette.textDim,
    border: "1px solid transparent",
  },
  outline: {
    background: "transparent",
    color: palette.text,
    border: `1px solid ${palette.border}`,
  },
  danger: {
    background: "#450a0a",
    color: "#fecaca",
    border: "1px solid rgba(239,68,68,0.4)",
  },
};

export function Button({ variant = "primary", size = "md", loading, disabled, children, style, ...rest }: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      style={{
        appearance: "none",
        border: 0,
        borderRadius: radius.md,
        fontWeight: 600,
        letterSpacing: 0.2,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 8,
        whiteSpace: "nowrap",
        transition: `opacity ${motion.fast}, filter ${motion.fast}`,
        ...sizeMap[size],
        ...variantMap[variant],
        ...style,
        opacity: disabled || loading ? 0.55 : 1,
      }}
    >
      {loading && <span className="loading-spinner" style={{ width: 13, height: 13, borderWidth: 2 }} />}
      {children}
    </button>
  );
}