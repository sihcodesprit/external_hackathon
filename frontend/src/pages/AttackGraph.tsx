import React from 'react'
import { colors, typography, spacing } from '../styles/designSystem'
import { Card, Button } from '../components/ui'

export const AttackGraph = () => {
  return (
    <div className="attack-graph-screen" style={{ minHeight: '100vh', background: colors.background, color: colors.text_primary }}>
      <Container>
        <h2 style={{ color: colors.text_primary, fontSize: '2rem', fontWeight: 600, marginBottom: spacing.lg }}>
          Predictive Attack Graph
        </h2>

        <Card style={{ padding: spacing.lg }}>
          <div style={{ height: '400px', background: colors.chart_bg, borderRadius: 8, marginBottom: spacing.lg }}>
            {/* Network attack graph visualization would go here */}
            <p style={{ color: colors.text_muted, fontSize: typography.fontSize.sm, textAlign: 'center', padding: '2rem' }}>
              Interactive attack graph would display here showing:
              <br />• Attacker flow from Reconnaissance → C2 → Exfiltration
              <br />• Node colors indicating risk levels
              <br />• Edge thickness showing communication intensity
              <br />• Clickable nodes for detailed host information
            </p>
          </div>

          {/* Attack chain breakdown */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: spacing.md }}>
            <div style={{ background: colors.surface2, padding: spacing.md, borderRadius: 6 }}>
              <span style={{ color: colors.text_secondary, fontWeight: 500 }}>Reconnaissance</span>
              <p style={{ color: colors.text_muted, fontSize: typography.fontSize.sm, marginTop: spacing.xs }}>18,492 connection attempts detected</p>
            </div>
            <div style={{ background: colors.surface2, padding: spacing.md, borderRadius: 6 }}>
              <span style={{ color: colors.text_secondary, fontWeight: 500 }}>Port Discovery</span>
              <p style={{ color: colors.text_muted, fontSize: typography.fontSize.sm, marginTop: spacing.xs }}>143 unique ports identified</p>
            </div>
            <div style={{ background: colors.surface2, padding: spacing.md, borderRadius: 6 }}>
              <span style={{ color: colors.text_secondary, fontWeight: 500 }}>Initial Access</span>
              <p style={{ color: colors.text_muted, fontSize: typography.fontSize.sm, marginTop: spacing.xs }}>9,231 brute force attempts</p>
            </div>
          </div>

          {/* Graph controls */}
          <div style={{ marginTop: spacing.lg, display: 'flex', gap: spacing.md, alignItems: 'center' }}>
            <Button
              variant="outline"
              style={{
                padding: `${spacing.sm} ${spacing.md}`,
                fontSize: typography.fontSize.sm,
                border: `1px solid ${colors.border}`,
                color: colors.text_secondary,
                background: 'transparent',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                borderRadius: radius.md,
              }}
              onClick={() => alert('Zoom in')}
            >
              Zoom In
            </Button>
            <Button
              variant="outline"
              style={{
                padding: `${spacing.sm} ${spacing.md}`,
                fontSize: typography.fontSize.sm,
                border: `1px solid ${colors.border}`,
                color: colors.text_secondary,
                background: 'transparent',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                borderRadius: radius.md,
              }}
              onClick={() => alert('Zoom out')}
            >
              Zoom Out
            </Button>
            <Button
              variant="outline"
              style={{
                padding: `${spacing.sm} ${spacing.md}`,
                fontSize: typography.fontSize.sm,
                border: `1px solid ${colors.border}`,
                color: colors.text_secondary,
                background: 'transparent',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                borderRadius: radius.md,
              }}
              onClick={() => alert('Pan')}
            >
              Pan
            </Button>
          </div>
        </Card>
      </Container>
    </div>
  )
}