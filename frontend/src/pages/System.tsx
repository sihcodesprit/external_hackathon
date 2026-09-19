import { useState } from "react";
import { palette } from "../styles/theme";
import { api } from "../services/api";
import { useFetch } from "../hooks/useFetch";
import type { ModelStatus, SystemInfo, SystemDependencies } from "../types";
import { Card, Grid, KeyValue, Pill, Tag, Dot, Row } from "../components/ui/primitives";
import { Button } from "../components/ui/Button";
import { ErrorState, PageLoader } from "../components/ui/displays";
import { fmtInt, fmtBytes, fmtDuration, fmtDateTime } from "../utils/format";

export default function System() {
  const { data: info, loading: infoLoading, error: infoError } = useFetch(() => api.systemInfo(), []);
  const { data: models, loading: modelsLoading, error: modelsError, refresh } = useFetch(() => api.modelsStatus(), []);
  const { data: deps, loading: depsLoading } = useFetch(() => api.systemDependencies(), []);
  const [retraining, setRetraining] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const retrain = async () => {
    setRetraining(true);
    try {
      const res = await api.retrain();
      setMsg(`retrain OK — ${res.message ?? ""}`);
      refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setRetraining(false);
    }
  };

  return (
    <div>
      <h1 style={{ fontSize: 20, fontWeight: 700, color: palette.text, marginBottom: 6 }}>System Diagnostics</h1>
      <p style={{ fontSize: 12.5, color: palette.textMuted, marginBottom: 20 }}>
        Runtime environment, model registry, and installed artifacts.
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <Card title="Runtime" subtitle="Server environment">
          {infoLoading && <PageLoader label="Probing runtime…" />}
          {infoError && <ErrorState message={infoError} />}
          {info && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 }}>
              {[
                ["App", info.app],
                ["Version", info.version],
                ["Started", fmtDateTime(info.started_at)],
                ["Uptime", fmtDuration(info.uptime_seconds)],
                ["Python", info.python],
                ["PyTorch", info.torch],
                ["NumPy", info.numpy],
                ["World model", info.world_model_type],
                ["Platform", info.platform],
                ["Feature count", String(info.feature_count ?? 132)],
              ].map(([k, v]) => <KeyValue key={k} k={k} v={v as string} mono />)}
            </div>
          )}
        </Card>

        <Card title="Dependencies" subtitle="TShark live capture & runtime">
          {depsLoading && <PageLoader label="Probing dependencies…" />}
          {deps && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Dot color={deps.python.available ? palette.good : palette.danger} />
                  <span style={{ fontSize: 12, fontWeight: 600 }}>Python</span>
                </div>
                <KeyValue k="Version" v={deps.python.version} mono />
                <KeyValue k="Implementation" v={deps.python.implementation} />
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Dot color={deps.tshark.available ? palette.good : deps.tshark.capture_available ? palette.accent : palette.danger} />
                  <span style={{ fontSize: 12, fontWeight: 600 }}>TShark</span>
                </div>
                <KeyValue k="Available" v={deps.tshark.available ? "Yes" : "No"} />
                <KeyValue k="Capture Ready" v={deps.tshark.capture_available ? "Yes" : "No"} />
                {deps.tshark.path && <KeyValue k="Path" v={deps.tshark.path} mono />}
                {deps.tshark.version && <KeyValue k="Version" v={deps.tshark.version} mono />}
                {deps.tshark.reason && <KeyValue k="Note" v={deps.tshark.reason} />}
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Dot color={deps.live_capture.available ? palette.good : palette.danger} />
                  <span style={{ fontSize: 12, fontWeight: 600 }}>Live Capture</span>
                </div>
                <KeyValue k="Ready" v={deps.live_capture.available ? "Yes" : "No"} />
                <KeyValue k="Interfaces" v={String(deps.live_capture.interface_count)} />
                {deps.live_capture.interfaces.length > 0 && (
                  <div style={{ fontSize: 11, color: palette.textMuted }}>
                    {deps.live_capture.interfaces.slice(0, 3).join(", ")}
                    {deps.live_capture.interfaces.length > 3 && " …"}
                  </div>
                )}
              </div>
            </div>
          )}
        </Card>

        <Card
          subtitle="Registered checkpoints"
          headerRight={
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Pill tone="accent">{models?.registry_models?.length ?? "—"} registered</Pill>
              <Button size="sm" variant="ghost" onClick={refresh}>↻</Button>
            </div>
          }
        >
          {modelsLoading && <PageLoader label="Reading registry…" />}
          {modelsError && <ErrorState message={modelsError} />}
          {models && models.registry_models.length === 0 && (
            <div style={{ fontSize: 12.5, color: palette.textMuted }}>No models registered yet.</div>
          )}
          {models && models.registry_models.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {models.registry_models.map((m, i) => (
                <div key={i} style={{ padding: "10px 12px", borderRadius: 8, border: `1px solid ${palette.borderSoft}`, display: "flex", justifyContent: "space-between", gap: 10, alignItems: "center" }}>
                  <span style={{ fontSize: 12.5, color: palette.text }}>{String((m as Record<string, unknown>).name ?? "—")}</span>
                  <span className="mono" style={{ fontSize: 11, color: palette.textDim }}>v{String((m as Record<string, unknown>).version ?? "—")}</span>
                  <Tag color="#38bdf8">{String((m as Record<string, unknown>).dataset ?? "—")}</Tag>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Model artifacts" subtitle={`${models?.artifacts?.length ?? 0} files in data/models`}>
          {models && models.artifacts.length === 0 && (
            <div style={{ fontSize: 12.5, color: palette.textMuted }}>No artifact files found.</div>
          )}
          {models && models.artifacts.length > 0 && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 8 }}>
              {models.artifacts.map((a) => (
                <div key={a.name} style={{ padding: "9px 11px", borderRadius: 8, border: `1px solid ${palette.borderSoft}`, display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}>
                  <span className="mono" style={{ fontSize: 11.5, color: palette.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={a.name}>
                    {a.name}
                  </span>
                  <span className="mono" style={{ fontSize: 11, color: palette.textMuted, flexShrink: 0 }}>{fmtBytes(a.size_kb * 1024)}</span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Active dataset" subtitle="The capture currently loaded into the engine">
          {models?.active_traffic?.filename ? (
            <GridView
              filename={models.active_traffic.filename}
              source={models.active_traffic.source ?? "—"}
              member={models.active_traffic.member}
              occurrence={models.active_traffic.occurrence}
              n_states={models.active_traffic.n_states}
              n_records={models.active_traffic.n_records}
            />
          ) : (
            <div style={{ fontSize: 12.5, color: palette.textMuted }}>No capture loaded.</div>
          )}
        </Card>

        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <Button variant="outline" onClick={retrain} loading={retraining}>
            {retraining ? "Retraining…" : "Retrain model"}
          </Button>
          {msg && <span style={{ fontSize: 12, color: msg.startsWith("retrain OK") ? palette.good : palette.danger }}>{msg}</span>}
        </div>
      </div>
    </div>
  );
}

function GridView({ filename, source, member, occurrence, n_states, n_records }: {
  filename: string;
  source: string;
  member: string | null;
  occurrence: string | null;
  n_states: number;
  n_records: number;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <KeyValue k="File" v={`${occurrence ? `[${occurrence}] ` : ""}${filename}`} mono />
      <KeyValue k="Member" v={member ?? "—"} mono />
      <KeyValue k="Source" v={source} />
      <KeyValue k="Records / states" v={`${fmtInt(n_records)} / ${fmtInt(n_states)}`} mono />
    </div>
  );
}