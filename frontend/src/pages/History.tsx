import React from 'react'
import { colors, typography, spacing } from '../styles/designSystem'
import { Card, Button } from '../components/ui'

export const History = () => {
  return (
    <div className="history-screen" style={{ minHeight: '100vh', background: colors.background, color: colors.text_primary }}>
      <Container>
        <h2 style={{ color: colors.text_primary, fontSize: '2rem', fontWeight: 600, marginBottom: spacing.lg }}>
          Analysis History
        </h2>

        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.md }}>
            <span style={{ color: colors.text_secondary, fontSize: typography.fontSize.sm }}>
              No analyses yet
            </span>
            <Button variant="primary" style={{ padding: `${spacing.sm} ${spacing.md}`, fontSize: typography.fontSize.sm }}>
              Run First Analysis
            </Button>
          </div>

          <div style={{ maxHeight: '300px', overflow: 'auto' }}>
            <p style={{ color: colors.text_muted, fontSize: typography.fontSize.sm }}>
              Upload a PCAP to generate analysis results that appear here.
            </p>
          </div>
        </Card>

        <Card style={{ marginTop: spacing.lg }}>
          <h3 style={{ color: colors.text_secondary, marginBottom: spacing.sm, fontSize: typography.fontSize.sm }}>
            Recent Analyses
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit', gap: spacing.md, marginTop: spacing.sm }>
            <div style={{ background: colors.surface2, padding: spacing.md, borderRadius: 6, height: '80px' }}>
              <span style={{ color: colors.text_muted, fontSize: typography.fontSize.sm }}>No analyses</span>
            </div>
            <div style={{ background: colors.surface2, padding: spacing.md, borderRadius: 6, height: '80px' }}>
              <span style={{ color: colors.text_muted, fontSize: typography.fontSize.sm }}>No analyses</span>
            </div>
            <div style={{ background: colors.surface2, padding: spacing.md, borderRadius: 6, height: '80px' }}>
              <span style={{ color: colors.text_muted, fontSize: typography.fontSize.sm }}>No analyses</span>
            </div>
          </div>
        </Card>
      </Container>
    </div>
  )
}