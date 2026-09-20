import { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { palette, stageColor, motion, radius } from "../styles/theme";
import type { LabStatusResponse, LiveInterface, LiveStatusResponse } from "../types";

interface Props {
  bare?: boolean;
}

type AttackType = "recon" | "bruteforce" | "dos" | "exfiltration";

const ATTACK_OPTIONS: Array<{
  id: AttackType;
  title: string;
  icon: string;
  stage: string;
  badgeColor: string;
  summary: string;
  details: string;
}> = [
  {
    id: "recon",
    title: "Port Scan & Discovery",
    icon: "🔍",
    stage: "Reconnaissance",
    badgeColor: "#38bdf8",
    summary: "High-fanout TCP connect probes across ports 21–27017.",
    details: "Induces port entropy spikes, rapid closed port RSTs, and TCP SYN asymmetry for stage detection.",
  },
  {
    id: "bruteforce",
    title: "Credential Brute Force",
    icon: "🔑",
    stage: "Initial Access",
    badgeColor: "#fbbf24",
    summary: "Multi-threaded dictionary auth stuffing against /login.",
    details: "Surges HTTP 401 error rate and repetitive payload bursts on the authentication service.",
  },
  {
    id: "dos",
    title: "DoS & Traffic Flood",
    icon: "💥",
    stage: "Impact",
    badgeColor: "#ef4444",
    summary: "High-velocity TCP connection and HTTP volumetric burst.",
    details: "Drives packet velocity surges, TCP handshake stress, and state-transition velocity degradation.",
  },
  {
    id: "exfiltration",
    title: "Data Harvesting & Exfiltration",
    icon: "📦",
    stage: "Exfiltration",
    badgeColor: "#c084fc",
    summary: "Automated queries against sensitive mock documents APIs.",
    details: "Simulates confidential document harvesting, shifting outbound byte ratios and data staging patterns.",
  },
];

export default function AttackLab({ bare }: Props) {
  const [labStatus, setLabStatus] = useState<LabStatusResponse | null>(null);
  const [liveStatus, setLiveStatus] = useState<LiveStatusResponse | null>(null);
  const [interfaces, setInterfaces] = useState<LiveInterface[]>([]);
  const [selectedIface, setSelectedIface] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Attack Configuration State
  const [selectedAttack, setSelectedAttack] = useState<AttackType>("recon");
  const [targetIp, setTargetIp] = useState<string>("10.0.0.2");
  const [targetPort, setTargetPort] = useState<number>(8080);
  const [attackDuration, setAttackDuration] = useState<number>(15);
  const [attackIntensity, setAttackIntensity] = useState<"low" | "medium" | "high">("medium");

  // Local Attack Progress Timer
  const [timeRemaining, setTimeRemaining] = useState<number>(0);

  const terminalRef = useRef<HTMLDivElement>(null);

  // Poll status from backend
  useEffect(() => {
    let mounted = true;

    const fetchStatus = async () => {
      try {
        const [labRes, liveRes] = await Promise.all([
          api.labStatus().catch(() => null),
          api.liveStatus().catch(() => null),
        ]);
        if (mounted) {
          if (labRes) {
            setLabStatus(labRes);
            if (!selectedIface && labRes.topology) {
              setSelectedIface(labRes.topology.suggested_interface || "lab-veth0");
            }
            if (targetIp === "10.0.0.2" && !labRes.topology.has_veth) {
              setTargetIp("127.0.0.1");
            }
          }
          if (liveRes) setLiveStatus(liveRes);
        }
      } catch (err) {
        console.error("Error polling lab status:", err);
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 1500);

    // Fetch interfaces once
    api.liveInterfaces().then((ifaces) => {
      if (mounted) setInterfaces(ifaces);
    }).catch(() => {});

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [selectedIface, targetIp]);

  // Auto-scroll terminal on new logs
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [labStatus?.logs]);

  // Progress countdown timer during active attack
  const isAttackRunning = Boolean(labStatus?.active_attack?.running);

  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (isAttackRunning) {
      setTimeRemaining((prev) => (prev > 0 ? prev : attackDuration));
      timer = setInterval(() => {
        setTimeRemaining((t) => (t > 1 ? t - 1 : 0));
      }, 1000);
    } else {
      setTimeRemaining(0);
    }
    return () => clearInterval(timer);
  }, [isAttackRunning, attackDuration]);

  // ── Actions ──

  const handleToggleTarget = async () => {
    setLoading(true);
    setActionError(null);
    try {
      if (labStatus?.topology.target_running) {
        await api.labTargetStop();
      } else {
        await api.labTargetStart({ port: targetPort, host: "0.0.0.0" });
      }
      const updated = await api.labStatus();
      setLabStatus(updated);
    } catch (err: any) {
      setActionError(err.message || "Failed to toggle target server");
    } finally {
      setLoading(false);
    }
  };

  const handleToggleCapture = async () => {
    setLoading(true);
    setActionError(null);
    try {
      if (liveStatus?.active) {
        await api.liveStop();
      } else {
        const iface = selectedIface || labStatus?.topology.suggested_interface || "lab-veth0";
        await api.liveStart({ interface: iface, window_size: 15, step_size: 3, forecast_horizon: 5 });
      }
      const [labRes, liveRes] = await Promise.all([api.labStatus(), api.liveStatus()]);
      setLabStatus(labRes);
      setLiveStatus(liveRes);
    } catch (err: any) {
      setActionError(err.message || "Failed to toggle live capture");
    } finally {
      setLoading(false);
    }
  };

  // Launch SINGLE selected attack (strict lockout: ignores click if attack running)
  const handleLaunchAttack = async (typeToLaunch?: AttackType) => {
    if (isAttackRunning || loading) {
      // Ignored: pressing button while in an attack does nothing
      return;
    }

    const type = typeToLaunch || selectedAttack;
    setLoading(true);
    setActionError(null);
    setTimeRemaining(attackDuration);

    try {
      await api.labAttackStart({
        attack: type,
        target_ip: targetIp || labStatus?.topology.target_ip || "127.0.0.1",
        duration: attackDuration,
        intensity: attackIntensity,
      });
      const updated = await api.labStatus();
      setLabStatus(updated);
    } catch (err: any) {
      setActionError(err.message || `Failed to launch ${type} attack`);
    } finally {
      setLoading(false);
    }
  };

  const handleStopAttack = async () => {
    setLoading(true);
    setActionError(null);
    try {
      await api.labAttackStop();
      const updated = await api.labStatus();
      setLabStatus(updated);
      setTimeRemaining(0);
    } catch (err: any) {
      setActionError(err.message || "Failed to stop attack");
    } finally {
      setLoading(false);
    }
  };

  // Clear inputs and reset telemetry
  const handleClearAll = async () => {
    setLoading(true);
    setActionError(null);
    try {
      await api.labClear();
      const updated = await api.labStatus();
      setLabStatus(updated);
      // Reset input fields to clean defaults
      setAttackDuration(15);
      setAttackIntensity("medium");
      setSelectedAttack("recon");
      if (labStatus?.topology.has_veth) {
        setTargetIp("10.0.0.2");
      } else {
        setTargetIp("127.0.0.1");
      }
      setTargetPort(8080);
    } catch (err: any) {
      setActionError(err.message || "Failed to reset");
    } finally {
      setLoading(false);
    }
  };

  const topo = labStatus?.topology;
  const activeAttack = labStatus?.active_attack;
  const targetStats = (topo?.target_stats as any) || {};

  return (
    <div style={{ padding: bare ? 0 : 20, display: "flex", flexDirection: "column", gap: 16 }}>
      {/* ── TOP HEADER / WORKFLOW BAR ── */}
      <div
        style={{
          background: `linear-gradient(135deg, ${palette.bgElevated} 0%, #0d1628 100%)`,
          border: `1px solid ${palette.border}`,
          borderRadius: radius.md,
          padding: "16px 20px",
          boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  fontSize: 10.5,
                  fontWeight: 700,
                  color: palette.accent,
                  textTransform: "uppercase",
                  background: palette.accentSoft,
                  padding: "2px 8px",
                  borderRadius: radius.pill,
                  border: `1px solid ${palette.accentBorder}`,
                }}
              >
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: isAttackRunning ? palette.danger : liveStatus?.active ? palette.good : palette.warn,
                    display: "inline-block",
                  }}
                />
                Attack Lab Console
              </span>
              <span style={{ fontSize: 11, color: palette.textMuted }}>· Step-by-Step Intrusion Verification</span>
            </div>
            <h2 style={{ fontSize: 18, fontWeight: 700, color: palette.text, marginTop: 4 }}>
              Interactive Attack Simulation &amp; Live Detection Hub
            </h2>
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={handleClearAll}
              disabled={isAttackRunning || loading}
              style={{
                padding: "6px 12px",
                background: "rgba(255, 255, 255, 0.05)",
                color: palette.textDim,
                border: `1px solid ${palette.borderSoft}`,
                borderRadius: radius.sm,
                fontSize: 11.5,
                fontWeight: 600,
                cursor: isAttackRunning ? "not-allowed" : "pointer",
                opacity: isAttackRunning ? 0.4 : 1,
              }}
            >
              ⟲ Clear Inputs &amp; Logs
            </button>
          </div>
        </div>

        {/* 3-STEP PIPELINE CONTROLLER */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1.1fr 1.4fr",
            gap: 12,
            background: "rgba(5, 8, 16, 0.6)",
            padding: 12,
            borderRadius: radius.sm,
            border: `1px solid ${palette.borderSoft}`,
          }}
        >
          {/* STEP 1: Web Server */}
          <div
            style={{
              padding: 10,
              background: topo?.target_running ? "rgba(52, 211, 153, 0.08)" : palette.bg,
              border: `1px solid ${topo?.target_running ? "rgba(52, 211, 153, 0.3)" : palette.borderSoft}`,
              borderRadius: radius.sm,
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              gap: 8,
            }}
          >
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 10, fontWeight: 700, color: palette.textMuted }}>STEP 1 · TARGET APP</span>
                <span style={{ fontSize: 10, color: topo?.target_running ? palette.good : palette.danger, fontWeight: 600 }}>
                  {topo?.target_running ? "● Online" : "○ Offline"}
                </span>
              </div>
              <div style={{ fontSize: 12.5, fontWeight: 600, color: palette.text, marginTop: 2 }}>
                Mock Web Server (:8080)
              </div>
            </div>

            <div style={{ display: "flex", gap: 6 }}>
              <button
                onClick={handleToggleTarget}
                disabled={isAttackRunning || loading}
                style={{
                  flex: 1,
                  padding: "6px 8px",
                  borderRadius: radius.sm,
                  border: "none",
                  background: topo?.target_running ? "rgba(239, 68, 68, 0.2)" : palette.good,
                  color: topo?.target_running ? palette.danger : "#000",
                  fontWeight: 600,
                  fontSize: 11.5,
                  cursor: isAttackRunning ? "not-allowed" : "pointer",
                }}
              >
                {topo?.target_running ? "Stop Server" : "1. Start Server"}
              </button>
              {topo?.target_running && (
                <a
                  href={`http://${targetIp || "127.0.0.1"}:${targetPort || 8080}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    padding: "6px 8px",
                    background: "rgba(59, 130, 246, 0.15)",
                    color: "#60a5fa",
                    border: "1px solid rgba(59, 130, 246, 0.3)",
                    borderRadius: radius.sm,
                    fontSize: 11,
                    textDecoration: "none",
                    fontWeight: 600,
                    display: "flex",
                    alignItems: "center",
                  }}
                >
                  ↗ Portal
                </a>
              )}
            </div>
          </div>

          {/* STEP 2: Live TShark Sensor */}
          <div
            style={{
              padding: 10,
              background: liveStatus?.active ? "rgba(34, 211, 238, 0.08)" : palette.bg,
              border: `1px solid ${liveStatus?.active ? "rgba(34, 211, 238, 0.3)" : palette.borderSoft}`,
              borderRadius: radius.sm,
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              gap: 8,
            }}
          >
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 10, fontWeight: 700, color: palette.textMuted }}>STEP 2 · TSHARK SENSOR</span>
                <span style={{ fontSize: 10, color: liveStatus?.active ? palette.accent : palette.warn, fontWeight: 600 }}>
                  {liveStatus?.active ? `● ${liveStatus.packets || 0} pkts` : "○ Inactive"}
                </span>
              </div>
              <div style={{ fontSize: 12.5, fontWeight: 600, color: palette.accent, marginTop: 2 }}>
                Interface: {selectedIface || "lab-veth0"}
              </div>
            </div>

            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <button
                onClick={handleToggleCapture}
                disabled={isAttackRunning || loading}
                style={{
                  flex: 1,
                  padding: "6px 8px",
                  borderRadius: radius.sm,
                  border: "none",
                  background: liveStatus?.active ? "rgba(251, 191, 36, 0.2)" : palette.accent,
                  color: liveStatus?.active ? palette.warn : "#000",
                  fontWeight: 600,
                  fontSize: 11.5,
                  cursor: isAttackRunning ? "not-allowed" : "pointer",
                }}
              >
                {liveStatus?.active ? "Stop Capture" : "2. Begin Listening"}
              </button>
            </div>
          </div>

          {/* STEP 3: Attack Trigger & Status */}
          <div
            style={{
              padding: 10,
              background: isAttackRunning ? "rgba(239, 68, 68, 0.12)" : palette.bg,
              border: `1px solid ${isAttackRunning ? palette.danger : palette.borderSoft}`,
              borderRadius: radius.sm,
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              gap: 8,
            }}
          >
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 10, fontWeight: 700, color: palette.textMuted }}>STEP 3 · RUN ATTACK</span>
                {isAttackRunning && (
                  <span style={{ fontSize: 10, color: palette.danger, fontWeight: 700, animation: "pulse 1s infinite" }}>
                    ⚡ RUNNING ({timeRemaining}s left)
                  </span>
                )}
              </div>
              <div style={{ fontSize: 12.5, fontWeight: 600, color: isAttackRunning ? palette.danger : palette.text, marginTop: 2 }}>
                {isAttackRunning
                  ? `Active: ${activeAttack?.type?.toUpperCase()} (${activeAttack?.packets_sent || 0} pkts)`
                  : `Selected: ${selectedAttack.toUpperCase()}`}
              </div>
            </div>

            <div style={{ display: "flex", gap: 6 }}>
              {isAttackRunning ? (
                <button
                  onClick={handleStopAttack}
                  disabled={loading}
                  style={{
                    flex: 1,
                    padding: "6px 12px",
                    borderRadius: radius.sm,
                    border: "none",
                    background: palette.critical,
                    color: "#fff",
                    fontWeight: 700,
                    fontSize: 12,
                    cursor: "pointer",
                  }}
                >
                  ■ Stop Active Attack
                </button>
              ) : (
                <button
                  onClick={() => handleLaunchAttack(selectedAttack)}
                  disabled={isAttackRunning || loading}
                  style={{
                    flex: 1,
                    padding: "6px 12px",
                    borderRadius: radius.sm,
                    border: "none",
                    background: palette.warn,
                    color: "#000",
                    fontWeight: 700,
                    fontSize: 12,
                    cursor: "pointer",
                  }}
                >
                  3. Run {selectedAttack.toUpperCase()} Attack ➔
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {actionError && (
        <div
          style={{
            padding: "10px 14px",
            background: "rgba(239, 68, 68, 0.15)",
            border: `1px solid ${palette.danger}`,
            borderRadius: radius.sm,
            color: "#fca5a5",
            fontSize: 12,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span>{actionError}</span>
          <button
            onClick={() => setActionError(null)}
            style={{ background: "none", border: "none", color: "#fca5a5", cursor: "pointer", fontSize: 14 }}
          >
            ✕
          </button>
        </div>
      )}

      {/* ── ATTACK SELECTOR CARDS (ONE AT A TIME TRIGGER) ── */}
      <div
        style={{
          background: palette.bgElevated,
          border: `1px solid ${palette.border}`,
          borderRadius: radius.md,
          padding: 16,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <div>
            <h3 style={{ fontSize: 14, fontWeight: 600, color: palette.text }}>Choose One Attack to Simulate</h3>
            <p style={{ fontSize: 11, color: palette.textMuted }}>
              Select an individual vector below. Buttons are strictly locked out while an attack is running.
            </p>
          </div>

          {/* Config Parameters */}
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: palette.textDim }}>
              <span>Target IP:</span>
              <input
                type="text"
                value={targetIp}
                onChange={(e) => setTargetIp(e.target.value)}
                disabled={isAttackRunning}
                style={{
                  width: 90,
                  background: palette.bg,
                  color: palette.text,
                  border: `1px solid ${palette.borderSoft}`,
                  borderRadius: radius.sm,
                  padding: "3px 6px",
                  fontSize: 11,
                  fontFamily: palette.mono,
                }}
              />
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: palette.textDim }}>
              <span>Duration:</span>
              <select
                value={attackDuration}
                onChange={(e) => setAttackDuration(Number(e.target.value))}
                disabled={isAttackRunning}
                style={{
                  background: palette.bg,
                  color: palette.text,
                  border: `1px solid ${palette.borderSoft}`,
                  borderRadius: radius.sm,
                  padding: "3px 6px",
                  fontSize: 11,
                }}
              >
                <option value={10}>10s</option>
                <option value={15}>15s (Default)</option>
                <option value={30}>30s</option>
              </select>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: palette.textDim }}>
              <span>Intensity:</span>
              <select
                value={attackIntensity}
                onChange={(e) => setAttackIntensity(e.target.value as any)}
                disabled={isAttackRunning}
                style={{
                  background: palette.bg,
                  color: palette.text,
                  border: `1px solid ${palette.borderSoft}`,
                  borderRadius: radius.sm,
                  padding: "3px 6px",
                  fontSize: 11,
                }}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </div>
          </div>
        </div>

        {/* Cards Grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
          {ATTACK_OPTIONS.map((opt) => {
            const isSelected = selectedAttack === opt.id;
            const isThisRunning = activeAttack?.type === opt.id;

            return (
              <div
                key={opt.id}
                onClick={() => {
                  if (!isAttackRunning) setSelectedAttack(opt.id);
                }}
                style={{
                  background: isThisRunning
                    ? "rgba(239, 68, 68, 0.12)"
                    : isSelected
                    ? "rgba(34, 211, 238, 0.08)"
                    : palette.bg,
                  border: `1px solid ${
                    isThisRunning
                      ? palette.danger
                      : isSelected
                      ? palette.accent
                      : palette.borderSoft
                  }`,
                  borderRadius: radius.sm,
                  padding: 14,
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                  cursor: isAttackRunning ? "not-allowed" : "pointer",
                  transition: `all ${motion.fast}`,
                }}
              >
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                    <span
                      style={{
                        fontSize: 9.5,
                        fontWeight: 700,
                        color: opt.badgeColor,
                        textTransform: "uppercase",
                        letterSpacing: 0.4,
                      }}
                    >
                      {opt.stage}
                    </span>
                    <span style={{ fontSize: 16 }}>{opt.icon}</span>
                  </div>

                  <h4 style={{ fontSize: 13, fontWeight: 600, color: palette.text, marginBottom: 4 }}>
                    {opt.title}
                  </h4>
                  <p style={{ fontSize: 11, color: palette.textDim, lineHeight: 1.35, marginBottom: 6 }}>
                    {opt.summary}
                  </p>
                  <p style={{ fontSize: 10, color: palette.textMuted, lineHeight: 1.3, marginBottom: 12 }}>
                    {opt.details}
                  </p>
                </div>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (isAttackRunning) return; // Strict lockout
                    setSelectedAttack(opt.id);
                    handleLaunchAttack(opt.id);
                  }}
                  disabled={isAttackRunning || loading}
                  style={{
                    width: "100%",
                    padding: "8px 10px",
                    borderRadius: radius.sm,
                    border: `1px solid ${isThisRunning ? palette.danger : opt.badgeColor}40`,
                    background: isThisRunning
                      ? palette.critical
                      : isSelected
                      ? `${opt.badgeColor}25`
                      : "rgba(255, 255, 255, 0.04)",
                    color: isThisRunning ? "#fff" : isSelected ? opt.badgeColor : palette.textDim,
                    fontSize: 11.5,
                    fontWeight: 700,
                    cursor: isAttackRunning ? "not-allowed" : "pointer",
                    opacity: isAttackRunning && !isThisRunning ? 0.35 : 1,
                    transition: `background ${motion.fast}`,
                  }}
                >
                  {isThisRunning ? "⚡ Attacking..." : `Launch ${opt.title.split(" ")[0]}`}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── LIVE DIAGNOSTICS & TERMINAL CONSOLE ── */}
      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 16 }}>
        {/* Terminal Output */}
        <div
          style={{
            background: "#050810",
            border: `1px solid ${palette.border}`,
            borderRadius: radius.md,
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div
            style={{
              padding: "8px 14px",
              background: palette.bgRaised,
              borderBottom: `1px solid ${palette.borderSoft}`,
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#ef4444", display: "inline-block" }} />
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#f59e0b", display: "inline-block" }} />
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#10b981", display: "inline-block" }} />
              <span style={{ fontSize: 11, fontWeight: 600, color: palette.textDim, marginLeft: 6, fontFamily: palette.mono }}>
                Execution Terminal Stream
              </span>
            </div>

            <div style={{ fontSize: 10.5, color: palette.textMuted, fontFamily: palette.mono }}>
              {isAttackRunning ? `Attack Active: ${activeAttack?.type} (${activeAttack?.packets_sent || 0} pkts)` : "Idle"}
            </div>
          </div>

          <div
            ref={terminalRef}
            style={{
              padding: 12,
              height: 200,
              overflowY: "auto",
              fontFamily: palette.mono,
              fontSize: 11,
              lineHeight: 1.5,
              color: "#a5f3fc",
              background: "#03060c",
            }}
          >
            {labStatus?.logs && labStatus.logs.length > 0 ? (
              labStatus.logs.map((log, idx) => (
                <div key={idx} style={{ wordBreak: "break-all" }}>
                  {log.includes("[!]") ? (
                    <span style={{ color: palette.good }}>{log}</span>
                  ) : log.includes("ERROR") || log.includes("Error") || log.includes("failed") ? (
                    <span style={{ color: palette.danger }}>{log}</span>
                  ) : log.includes("LAUNCHING") || log.includes("Starting") ? (
                    <span style={{ color: palette.warn, fontWeight: 700 }}>{log}</span>
                  ) : (
                    <span>{log}</span>
                  )}
                </div>
              ))
            ) : (
              <div style={{ color: palette.textMuted }}>[Console Ready] Waiting for attack trigger or live events...</div>
            )}
          </div>
        </div>

        {/* Real-time World Model Telemetry HUD */}
        <div
          style={{
            background: palette.bgElevated,
            border: `1px solid ${palette.border}`,
            borderRadius: radius.md,
            padding: 16,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <h3 style={{ fontSize: 13.5, fontWeight: 600, color: palette.text }}>Live World Model Detection</h3>
              <span
                style={{
                  fontSize: 10.5,
                  padding: "2px 8px",
                  borderRadius: radius.pill,
                  background: liveStatus?.active ? "rgba(52, 211, 153, 0.15)" : "transparent",
                  color: liveStatus?.active ? palette.good : palette.textMuted,
                  border: `1px solid ${liveStatus?.active ? "rgba(52, 211, 153, 0.3)" : "transparent"}`,
                }}
              >
                {liveStatus?.active ? "● Sensor Active" : "Sensor Inactive"}
              </span>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, marginBottom: 12 }}>
              <div
                style={{
                  background: palette.bg,
                  padding: 8,
                  borderRadius: radius.sm,
                  border: `1px solid ${palette.borderSoft}`,
                  textAlign: "center",
                }}
              >
                <div style={{ fontSize: 9.5, color: palette.textMuted }}>CURRENT RISK</div>
                <div
                  style={{
                    fontSize: 18,
                    fontWeight: 700,
                    color:
                      (liveStatus?.risk?.current_risk || 0) > 0.6
                        ? palette.critical
                        : (liveStatus?.risk?.current_risk || 0) > 0.3
                        ? palette.warn
                        : palette.good,
                  }}
                >
                  {liveStatus?.risk?.current_risk ? `${Math.round(liveStatus.risk.current_risk * 100)}%` : "0%"}
                </div>
              </div>

              <div
                style={{
                  background: palette.bg,
                  padding: 8,
                  borderRadius: radius.sm,
                  border: `1px solid ${palette.borderSoft}`,
                  textAlign: "center",
                }}
              >
                <div style={{ fontSize: 9.5, color: palette.textMuted }}>STAGE PREDICTION</div>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: stageColor(liveStatus?.stage?.current_stage || "Benign"),
                    marginTop: 4,
                  }}
                >
                  {liveStatus?.stage?.current_stage || "Benign"}
                </div>
              </div>

              <div
                style={{
                  background: palette.bg,
                  padding: 8,
                  borderRadius: radius.sm,
                  border: `1px solid ${palette.borderSoft}`,
                  textAlign: "center",
                }}
              >
                <div style={{ fontSize: 9.5, color: palette.textMuted }}>PACKETS / 401s</div>
                <div style={{ fontSize: 15, fontWeight: 700, color: palette.accent, marginTop: 2 }}>
                  {liveStatus?.packets || 0} / {targetStats.login_failures || 0}
                </div>
              </div>
            </div>

            <p style={{ fontSize: 11, color: palette.textDim, lineHeight: 1.4 }}>
              As the single attack executes, the LSTM World Model analyzes packet windows and computes forward
              probabilistic transitions.
            </p>
          </div>

          <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
            <Link
              to="/analysis?tab=forecast"
              style={{
                flex: 1,
                textAlign: "center",
                padding: "8px",
                background: palette.accentSoft,
                color: palette.accent,
                border: `1px solid ${palette.accentBorder}`,
                borderRadius: radius.sm,
                fontSize: 11.5,
                fontWeight: 600,
                textDecoration: "none",
              }}
            >
              Forecast Timeline ➔
            </Link>
            <Link
              to="/analysis?tab=attack-graph"
              style={{
                flex: 1,
                textAlign: "center",
                padding: "8px",
                background: palette.accent2Soft,
                color: palette.accent2,
                border: `1px solid rgba(139, 92, 246, 0.3)`,
                borderRadius: radius.sm,
                fontSize: 11.5,
                fontWeight: 600,
                textDecoration: "none",
              }}
            >
              Attack Graph ➔
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
