import React, { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { colors, typography, spacing } from '../styles/designSystem'
import { Card, MetricCard, Button } from '../components/ui'

export const Explainability = () => {
  const dispatch = useDispatch()
  const counterfactual = useSelector((state: any) => state.counterfactual)

  useEffect(() => {
    fetch('/api/forecast')
      .then(res => res.json())
      .then(data => {
        // Forecast data with explanations
      })
    fetch('/api/entities')
      .then(res => res.json())
      .then(data => {
        // Entity data for explanations
      })
  }, [dispatch])

  return (
    <div className="explainability-screen" style={{ minHeight: '100vh', background: colors.background, color: colors.text_primary }}>
      <Container>
        <h2 style={{ color: colors.text_primary, fontSize: '2rem', fontWeight: 600, marginBottom: spacing.lg }}>
          Explainability
        </h2>

        <Card style={{ padding: spacing.lg }}>
          <h3 style={{ color: colors.text_secondary, marginBottom: spacing.md, fontSize: typography.fontSize.sm }}>
            Why is the system predicting this?
          </h3>
          
          <div style={{ marginBottom: spacing.lg }}>
            <h4 style={{ color: colors.text_primary, fontSize: typography.fontSize.md, marginBottom: spacing.sm }}>
              Top Contributors
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: spacing.sm, background: colors.surface2, borderRadius: radius.sm }}>
                <span style={{ color: colors.text_primary, fontWeight: 500 }}>01. Destination Diversity</span>
                <span style={{ color: colors.accent_blue, fontWeight: 600 }}>+24%</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: spacing.sm, background: colors.surface2, borderRadius: radius.sm }}>
                <span style={{ color: colors.text_primary, fontWeight: 500 }}>02. SYN Rate Increase</span>
                <span style={{ color: colors.accent_blue, fontWeight: 600 }}>+19%</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: spacing.sm, background: colors.surface2, borderRadius: radius.sm }}>
                <span style={{ color: colors.text_primary, fontWeight: 500 }}>03. New Host Connections</span>
                <span style={{ color: colors.accent_blue, fontWeight: 600 }}>+16%</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: spacing.sm, background: colors.surface2, borderRadius: radius.sm }}>
                <span style={{ color: colors.text_primary, fontWeight: 500 }}>04. RST/SYN Imbalance</span>
                <span style={{ color: colors.accent_blue, fontWeight: 600 }}>+13%</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: spacing.sm, background: colors.surface2, borderRadius: radius.sm }}>
                <span style={{ color: colors.text_primary, fontWeight: 500 }}>05. Inter-arrival Burstiness</span>
                <span style={{ color: colors.accent_blue, fontWeight: 600 }}>+11%</span>
              </div>
            </div>
          </div>

          <div style={{ marginTop: spacing.lg, padding: spacing.md, background: colors.surface2, borderRadius: radius.md }}>
            <h4 style={{ color: colors.text_secondary, marginBottom: spacing.sm, fontSize: typography.fontSize.sm }}>
              Plain-language explanation
            </h4>
            <p style={{ color: colors.text_primary, fontSize: typography.fontSize.md, lineHeight: 1.6 }}>
              The forecast risk increased because the network began contacting more unique destinations, 
              SYN traffic increased sharply, and several new communication relationships appeared.
            </p>
            <p style={{ color: colors.text_muted, fontSize: typography.fontSize.sm, marginTop: spacing.xs }}>
              Explanation type: Feature magnitude fallback (SHAP unavailable)
            </p>
          </div>
        </Card>

        <Card style={{ marginTop: spacing.lg, padding: spacing.lg }}>
          <h3 style={{ color: colors.text_secondary, marginBottom: spacing.sm, fontSize: typography.fontSize.sm }}>
            Feature Contributions
          </h3>
          <div style={{ background: colors.chart_bg, borderRadius: radius.md, padding: spacing.lg, height: '200px' }}>
            {/* Feature contribution chart would go here */}
            <p style={{ color: colors.text_muted, fontSize: typography.fontSize.sm, textAlign: 'center', padding: '2rem' }}>
              SHAP feature contribution visualization
            </p>
          </div>
        </Card>
      </Container>
    </div>
  )
}