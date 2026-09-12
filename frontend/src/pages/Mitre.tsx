import React, { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { colors, typography, spacing } from '../styles/designSystem'
import { Card, Button, MetricCard } from '../components/ui'

export const Mitre = () => {
  const dispatch = useDispatch()

  useEffect(() => {
    fetch('/api/mitre')
      .then(res => res.json())
      .then(data => {
        // MITRE trajectory data loaded
      })
  }, [dispatch])

  return (
    <div className="mitre-screen" style={{ minHeight: '100vh', background: colors.background, color: colors.text_primary }}>
      <Container>
        <h2 style={{ color: colors.text_primary, fontSize: '2rem', fontWeight: 600, marginBottom: spacing.lg }}>
          MITRE ATT&CK Progression
        </h2>

        <Card style={{ padding: spacing.lg }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: spacing.md, marginBottom: spacing.lg }}>
            {/* Reconnaissance */}
            <MetricCard
              title="Reconnaissance"
              value="Discovery"
              subtitle="Multiple destination probes and service enumeration"
              icon="👀"
              bgColor={colors.accent_blue}
            />
            {/* Initial Access */}
            <MetricCard
              title="Initial Access"
              value="Valid Account"
              subtitle="External-facing application compromise"
              icon="🔓"
              bgColor={colors.accent_cyan}
            />
            {/* Execution */}
            <MetricCard
              title="Execution"
              value="Command Scripting"
              subtitle="User execution of malicious code"
              icon="⚡"
              bgColor={colors.accent_orange}
            />
            {/* Lateral Movement */}
            <MetricCard
              title="Lateral Movement"
              value="Remote Services"
              subtitle="RDP/SSH exploitation"
              icon="🔄"
              bgColor={colors.alert_elevated}
            />
            {/* Command & Control */}
            <MetricCard
              title="Command & Control"
              value="Application Layer"
              subtitle="Encrypted channel communication"
              icon="📡"
              bgColor={colors.alert_high}
            />
            {/* Exfiltration */}
            <MetricCard
              title="Exfiltration"
              value="Data Transfer"
              subtitle="Exfiltrating sensitive data"
              icon="📤"
              bgColor={colors.alert_critical}
            />
          </div>

          {/* Observed vs Predicted trajectory */}
          <div style={{ marginTop: spacing.lg }}>
            <h3 style={{ color: colors.text_secondary, marginBottom: spacing.sm, fontSize: typography.fontSize.sm }}>Attack Stage Timeline</h3>
            <div style={{ background: colors.chart_bg, borderRadius: 6, padding: spacing.md }}>
              {/* Timeline would show observed stages progressing through MITRE tactics */}
              <span style={{ color: colors.text_secondary, fontSize: typography.fontSize.sm, marginRight: spacing.md }}>Reconnaissance →</span>
              <span style={{ color: colors.accent_blue, fontSize: typography.fontSize.sm, marginRight: spacing.md }}>Initial Access →</span>
              <span style={{ color: colors.accent_orange, fontSize: typography.fontSize.sm, marginRight: spacing.md }}>Execution →</span>
              <span style={{ color: colors.alert_elevated, fontSize: typography.fontSize.sm, marginRight: spacing.md }}>Lateral Movement →</span>
              <span style={{ color: colors.alert_high, fontSize: typography.fontSize.sm}}>C2 →</span>
              <span style={{ color: colors.alert_critical, fontSize: typography.fontSize.sm}}>Exfiltration</span>
            </div>
          </div>

          {/* Confidence panel */}
          <Card style={{ marginTop: spacing.lg, padding: spacing.lg }}>
            <h3 style={{ color: colors.text_secondary, marginBottom: spacing.sm, fontSize: typography.fontSize.sm }}>Confidence</h3>
            <p style={{ color: colors.text_secondary, fontSize: typography.fontSize.lg, fontWeight: 500 }}>
              87% — Current stage prediction confidence
            </p>
            <p style={{ color: colors.text_muted, fontSize: typography.fontSize.sm, marginTop: spacing.xs }}>
              Based on feature analysis: high destination entropy, SYN rate increase, new host connections
            </p>
          </Card>
        </Card>
      </Container>
    </div>
  )
}