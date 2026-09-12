import { useState, useCallback, type DragEvent } from "react";
import { palette } from "../../styles/theme";
import { useAnalysis } from "../../store/analysisContext";
import { api } from "../../services/api";
import type { TrafficMember, ZipInspect } from "../../types";
import { fmtBytes } from "../../utils/format";
import { Button } from "../ui/Button";

export function FileUploader() {
  const { startAnalysis, running } = useAnalysis();
  const [zipInfo, setZipInfo] = useState<ZipInspect | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const handleScanZip = useCallback(async (f: File) => {
    setScanning(true);
    try {
      const info = await api.inspectZip(f);
      setZipInfo(info);
      setFile(f);
      const first = info.traffic_members[0];
      if (first) setSelected(first.name);
    } catch {
      setZipInfo(null);
    } finally {
      setScanning(false);
    }
  }, []);

  const handleFile = useCallback(
    (f: File) => {
      if (f.name.toLowerCase().endsWith(".zip")) {
        handleScanZip(f);
      } else {
        setFile(f);
        setZipInfo(null);
        setSelected(null);
      }
    },
    [handleScanZip],
  );

  const onDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      const f = e.dataTransfer.files[0];
      if (f) handleFile(f);
    },
    [handleFile],
  );

  const onDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    setDragActive(true);
  }, []);

  const onDragLeave = useCallback(() => setDragActive(false), []);

  const start = useCallback(() => {
    if (!file) return;
    if (zipInfo && selected) {
      startAnalysis(file, selected);
    } else {
      startAnalysis(file);
    }
  }, [file, zipInfo, selected, startAnalysis]);

  const uploadLocal = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0];
      if (f) handleFile(f);
    },
    [handleFile],
  );

  return (
    <div
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      style={{
        border: `2px dashed ${dragActive ? palette.accent : palette.borderSoft}`,
        borderRadius: 14,
        padding: "38px 28px",
        textAlign: "center",
        background: dragActive ? palette.accentSoft : "rgba(16,24,42,0.25)",
        transition: `background 150ms, border-color 150ms`,
        cursor: running ? "default" : "pointer",
        opacity: running ? 0.55 : 1,
      }}
    >
      <div style={{ fontSize: 28, color: palette.textMuted, marginBottom: 8, opacity: dragActive ? 1 : 0.65 }}>
        ⇧
      </div>
      <div style={{ fontSize: 14, color: palette.text, fontWeight: 600, marginBottom: 4 }}>
        {zipInfo ? zipInfo.filename : file ? file.name : "Drop capture file here"}
      </div>
      <div style={{ fontSize: 12, color: palette.textDim, marginBottom: 14 }}>
        {file
          ? `Ready · ${fmtBytes(file.size)}`
          : "Supports .pcap, .pcapng, .csv, .jsonl — or .zip with multiple captures"}
      </div>
      <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
        <label>
          <input
            type="file"
            accept=".pcap,.pcapng,.csv,.jsonl,.zip"
            onChange={uploadLocal}
            style={{ display: "none" }}
            disabled={running}
          />
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              padding: "8px 18px",
              borderRadius: 10,
              fontSize: 13,
              fontWeight: 600,
              background: "linear-gradient(135deg, #164e63, #0f766e)",
              color: "#e7f7ff",
              border: "1px solid rgba(34,211,238,0.4)",
              boxShadow: "0 0 16px rgba(34,211,238,0.18)",
              cursor: running ? "default" : "pointer",
              opacity: running ? 0.6 : 1,
            }}
          >
            Browse files
          </span>
        </label>
        {file && !running && (
          <Button variant="ghost" onClick={() => { setFile(null); setZipInfo(null); setSelected(null); }}>
            Clear
          </Button>
        )}
      </div>
      {scanning && (
        <div style={{ marginTop: 16, display: "flex", alignItems: "center", justifyContent: "center", gap: 10 }}>
          <span className="loading-spinner" style={{ width: 14, height: 14 }} />
          <span style={{ fontSize: 12, color: palette.textDim }}>Scanning ZIP archive…</span>
        </div>
      )}
      {zipInfo && zipInfo.traffic_members.length > 1 && (
        <div
          style={{
            marginTop: 20,
            textAlign: "left",
            padding: "14px 16px",
            background: "rgba(16,24,42,0.45)",
            border: `1px solid ${palette.borderSoft}`,
            borderRadius: 10,
          }}
        >
          <div style={{ fontSize: 12, fontWeight: 600, color: palette.text, marginBottom: 10 }}>
            {zipInfo.traffic_members.length} captures found in archive — select one to analyze
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 220, overflowY: "auto" }}>
            {zipInfo.traffic_members.map((m: TrafficMember) => (
              <label
                key={m.name}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "8px 10px",
                  borderRadius: 7,
                  border: `1px solid ${selected === m.name ? palette.accentBorder : palette.borderSoft}`,
                  background: selected === m.name ? palette.accentSoft : "transparent",
                  cursor: "pointer",
                  fontSize: 12.5,
                }}
              >
                <input
                  type="radio"
                  name="pcap"
                  checked={selected === m.name}
                  onChange={() => setSelected(m.name)}
                  style={{ accentColor: palette.accent }}
                />
                <span style={{ flex: 1, color: palette.text, fontFamily: "ui-monospace, monospace" }}>
                  {m.name}
                </span>
                <span style={{ fontSize: 11, color: palette.textMuted }}>{fmtBytes(m.size_bytes)}</span>
              </label>
            ))}
          </div>
          {selected && (
            <div style={{ marginTop: 14 }}>
              <Button
                onClick={start}
                disabled={running || !selected}
                loading={scanning}
                variant="primary"
              >
                Analyze selected capture
              </Button>
            </div>
          )}
        </div>
      )}
      {file && !zipInfo && !running && (
        <div style={{ marginTop: 18 }}>
          <Button onClick={start}>Start analysis</Button>
        </div>
      )}
    </div>
  );
}