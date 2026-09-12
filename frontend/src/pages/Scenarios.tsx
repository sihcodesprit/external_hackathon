import React from 'react'
import { colors, typography, spacing } from '../styles/designSystem'
import { Card, Button } from '../components/ui'

export const Scenarios = () => {
  const scenarios = [
    { id: 'benign', label: 'Benign Traffic', description: 'Normal network traffic without attack patterns', run: 'Run Analysis' },
    { id: 'recon', label: 'Reconnaissance', description: 'Port scanning and service enumeration', run: 'Run Analysis' },
    { id: 'port_scan', label: 'Port Scan', description: 'Single or multi-host port scanning', run: 'Run Analysis' },
    { id: 'brute_force', label: 'Brute Force', description: 'Credential guessing attacks', run: 'Run Analysis' },
    { id: 'dos', label: 'DoS', description: 'Denial of service traffic flood', run: 'Run Analysis' },
    { id: 'multi_stage', label: 'Multi-Stage Attack', description: 'Chained attack: Recon → Access → Execution → C2 → Exfil', run: 'Run Analysis' },
    { id: 'unseen', label: 'Unseen Attack', description: 'Attack pattern not in training set', run: 'Run Analysis', note: 'Synthetic data' },
    { id: 'custom', label: 'Custom PCAP', description: 'Upload your own PCAP for analysis', run: 'Run Analysis' },
  ]

  return (
    <div className="scenarios-screen" style={{ minHeight: '100vh', background: colors.background, color: colors.text_primary }}>
      <Container>
        <h2 style={{ color: colors.text_primary, fontSize: '2rem', fontWeight: 600, marginBottom: spacing.lg }}>
          Scenarios
        </h2>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit', gap: spacing.md, marginBottom: spacing.lg) }}>
          {scenarios.map((s) => (
            <Card
              key={s.id}
              style={{
                padding: spacing.lg,
                background: s.note ? colors.border : colors.surface,
                borderRadius: 6,
                                border: `1px solid ${s.note ? colors.alert_critical : colors.border}`,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.sm }}>
                <span style={{ color: colors.text_primary, fontSize: typography.fontSize.md, fontWeight: 500 }}>
                  {s.label}
                </span>
                <span style={{ color: colors.text_muted, fontSize: typography.fontSize.sm }}>
                  {s.run}
                </span>
              </div>
              <p style={{ color: colors.text_secondary, fontSize: typography.fontSize.sm, marginBottom: spacing.sm }}>
                {s.description}
              </p>
              {s.note && (
                <p style={{ color: colors.alert_critical, fontSize: typography.fontSize.sm, fontWeight: 500 }}>
                  {s.note}
                </p>
              )}
              <Button
                variant="outline"
                style={{ width: '100%', padding: `${spacing.xs} ${spacing.sm}`, fontSize: typography.fontSize.sm }}
                onClick={() => alert(`Run ${s.label} scenario`)}
              >
                Run Analysis
              </Button>
            </Card>
          ))}
        </div>
      </Container>
    </div>
  )
}