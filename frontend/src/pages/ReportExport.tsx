import React from 'react'
import { colors, typography, spacing } from '../styles/designSystem'
import { Card, Button } from '../components/ui'

export const ReportExport = () => {
  return (
    <div className="report-export-screen" style={{ minHeight: '100vh', background: colors.background, color: colors.text_primary }}>
      <Container>
        <h2 style={{ color: colors.text_primary, fontSize: '2rem', fontWeight: 600, marginBottom: spacing.lg }}>
          Export Analysis Report
        </h2>

        <Card>
          <p style={{ color: colors.text_secondary, fontSize: typography.fontSize.sm, marginBottom: spacing.lg }}>
            Generate a professional analysis report containing all results from the current session.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: spacing.md, marginBottom: spacing.lg }>
            <Button
              variant="outline"
              style={{ width: '100%', padding: `${spacing.sm} ${spacing.md}`, fontSize: typography.fontSize.sm }}
              onClick={() => alert('Exporting analysis report...')}
            >
              Generate Report
            </Button>
            <Button
              variant="primary"
              style={{ width: '100%', padding: `${spacing.sm} ${spacing.md}`, fontSize: typography.fontSize.sm }}
              onClick={() => alert('Report generation started')}
            >
              Download PDF
            </Button>
          </div>

          <Card style={{ marginTop: spacing.lg, padding: spacing.lg }}>
            <h3 style={{ color: colors.text_secondary, marginBottom: spacing.sm, fontSize: typography.fontSize.sm }}>
              Report Sections
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: spacing.md, marginBottom: spacing.lg }>
              <label style={{ color: colors.text_primary, fontSize: typography.fontSize.sm }}>
                <input type="checkbox" checked default disabled /> 1. PCAP Information
              </label>
              <label style={{ color: colors.text_primary, fontSize: typography.fontSize.sm }}>
                <input type="checkbox" checked default disabled /> 2. Traffic Summary
              </label>
              <label style={{ color: colors.text_primary, fontSize: typography.fontSize.sm }}>
                <input type="checkbox" checked default disabled /> 3. Network State
              </label>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: spacing.md }>
              <label style={{ color: colors.text_primary, fontSize: typography.fontSize.sm }}>
                <input type="checkbox" checked default disabled /> 4. Detected Behavior
              </label>
              <label style={{ color: colors.text_primary, fontSize: typography.fontSize.sm }}>
                <input type="checkbox" checked default disabled /> 5. Forecast
              </label>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: spacing.md }>
              <label style={{ color: colors.text_primary, fontSize: typography.fontSize.sm }}>
                <input type="checkbox" checked default disabled /> 6. MITRE ATT&CK
              </label>
              <label style={{ color: colors.text_primary, fontSize: typography.fontSize.sm }}>
                <input type="checkbox" checked default disabled /> 7. Explainability
              </label>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: spacing.md }>
              <label style={{ color: colors.text_primary, fontSize: typography.fontSize.sm }}>
                <input type="checkbox" checked default disabled /> 8. Attack Graph
              </label>
              <label style={{ color: colors.text_primary, fontSize: typography.fontSize.sm }}>
                <input type="checkbox" checked default disabled /> 9. Counterfactual Results
              </label>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: spacing.md }>
              <label style={{ color: colors.text_primary, fontSize: typography.fontSize.sm }}>
                <input type="checkbox" checked default disabled /> 10. Recommended Defense
              </label>
              <label style={{ color: colors.text_primary, fontSize: typography.fontSize.sm }}>
                <input type="checkbox" checked default disabled /> 11. Model Metrics
              </label>
            </div>
          </Card>
        </Card>
      </Container>
    </div>
  )
}