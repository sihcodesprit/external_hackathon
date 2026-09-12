import React, { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { selectForecast } from '../store/reducer'
import { colors, typography, spacing } from '../styles/designSystem'
import { Card, Button } from '../components/ui'

export const Forecast = () => {
  const dispatch = useDispatch()

  useEffect(() => {
    fetch('/api/forecast')
      .then(res => res.json())
      .then(data => {
        // Forecast data loaded from backend
        // dispatch(setForecast(data))
      })
  }, [dispatch])

  const forecast = useSelector(state => state.forecast)

  return (
    <div className="forecast-screen" style={{ minHeight: '100vh', background: colors.background, color: colors.text_primary }}>
      <Container>
        <h2 style={{ color: colors.text_primary, fontSize: '2rem', fontWeight: 600, marginBottom: spacing.lg }}>
          Attack Forecast
        </h2>

        <Card style={{ padding: spacing.lg, marginBottom: spacing.lg }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: colors.text_primary, fontSize: typography.fontSize.lg, fontWeight: 500 }}>
              Current Risk: <strong style={{ color: colors.alert_high }}>{forecast.current?.risk?.toFixed(1) || '0'}%</strong>
            </span>
            <span style={{ color: colors.text_secondary, fontSize: typography.fontSize.sm }}>
              {forecast.current?.stage || 'Benign'}
            </span>
          </div>

          {/* Past - Now - Future timeline */}
          <div style={{ marginTop: spacing.lg, position: 'relative' }}>
            <div style={{
              position: 'absolute', top: 30, left: 40, right: 40,
              height: 2, background: colors.border, zIndex: 0
            }} />
            
            {/* Past markers */}
            <div style={{ position: 'absolute', left: 40, top: 10, width: 12, height: 12, borderRadius: '50%', background: colors.text_secondary, border: '3px solid ' + colors.background, zIndex: 1 }} />
            <div style={{ position: 'absolute', left: 80, top: 10, width: 12, height: 12, borderRadius: '50%', background: colors.text_secondary, border: '3px solid ' + colors.background, zIndex: 1 }} />
            <div style={{ position: 'absolute', left: 120, top: 10, width: 12, height: 12, borderRadius: '50%', background: colors.accent_blue, zIndex: 1 }} />
            <div style={{ position: 'absolute', left: 160, top: 10, width: 12, height: 12, borderRadius: '50%', background: colors.text_secondary, border: '3px solid ' + colors.background, zIndex: 1 }} />
            <div style={{ position: 'absolute', left: 200, top: 10, width: 12, height: 12, borderRadius: '50%', background: colors.accent_orange, zIndex: 1 }} />

            {/* Labels */}
            <span style={{ position: 'absolute', left: 30, top: -25, color: colors.text_secondary, fontSize: typography.fontSize.xs, left: '40px' }}>&nbsp;&nbsp;t-3</span>
            <span style={{ position: 'absolute', left: 70, top: -25, color: colors.text_secondary, fontSize: typography.fontSize.xs, left: '80px' }}>&nbsp;&nbsp;t-2</span>
            <span style={{ position: 'absolute', left: 110, top: -25, color: colors.text_primary, fontSize: typography.fontSize.xs, left: '120px' }}>&nbsp;&nbsp;t-1</span>
            <span style={{ position: 'absolute', left: 150, top: -25, color: colors.text_secondary, fontSize: typography.fontSize.xs, left: '160px' }}>&nbsp;&nbsp;t+0</span>
            <span style={{ position: 'absolute', left: 190, top: -25, color: colors.text_secondary, fontSize: typography.fontSize.xs, left: '200px' }}>&nbsp;&nbsp;t+1</span>
          </div>

          {/* Risk timeline chart */}
          <Card style={{ marginTop: spacing.lg, padding: spacing.lg }}>
            <h4 style={{ color: colors.text_secondary, marginBottom: spacing.sm, fontSize: typography.fontSize.sm }}>Risk Progression</h4>
            <div style={{ height: '300px', background: colors.chart_bg, borderRadius: radius.md, overflow: 'hidden', position: 'relative' }}>
              {/* Risk chart would go here - line chart showing observed vs predicted risk */}
            </div>
          </Card>

          {/* Stage prediction */}
          <div style={{ marginTop: spacing.lg, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: spacing.md }}>
            <div>
              <span style={{ color: colors.text_secondary, fontSize: typography.fontSize.sm }}>+1 step</span>
              <p style={{ color: colors.alert_primary, fontSize: typography.fontSize.md, fontWeight: 500 }}>
                {forecast.future?.[0]?.stage || 'Discovery'} Risk: {forecast.future?.[0]?.risk?.toFixed(1) || '0'}%
              </p>
            </div>
            <div>
              <span style={{ color: colors.text_secondary, fontSize: typography.fontSize.sm }}>+2 steps</span>
              <p style={{ color: colors.alert_secondary, fontSize: typography.fontSize.md, fontWeight: 500 }}>
                {forecast.future?.[1]?.stage || 'Initial Access'} Risk: {forecast.future?.[1]?.risk?.toFixed(1) || '0'}%
              </p>
            </div>
            <div>
              <span style={{ color: colors.text_secondary, fontSize: typography.fontSize.sm }}>+3 steps</span>
              <p style={{ color: colors.alert_warning, fontSize: typography.fontSize.md, fontWeight: 500 }}>
                {forecast.future?.[2]?.stage || 'Execution'} Risk: {forecast.future?.[2]?.risk?.toFixed(1) || '0'}%
              </p>
            </div>
          </div>
        </Card>

        {/* World Model Visualization */}
        <Card style={{ marginTop: spacing.lg }}>
          <h3 style={{ color: colors.text_secondary, marginBottom: spacing.sm, fontSize: typography.fontSize.sm }}>
            World Model: Observed → Predicted
          </h3>
          <div style={{
            background: colors.chart_bg,
            borderRadius: radius.md,
            padding: spacing.lg,
            marginTop: spacing.sm,
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: spacing.md,
          }}>
            <div>
              <span style={{ color: colors.text_secondary, fontSize: typography.fontSize.sm, display: 'block', marginBottom: spacing.xs }}>Observed S(t)</span>
              <p style={{ color: colors.accent_blue, fontFamily: 'monospace', fontSize: typography.fontSize.sm, marginBottom: spacing.xs }}>Flow: 82, SYN: 31, Entropy: 2.8</p>
            </div>
            <div>
              <span style={{ color: colors.text_secondary, fontSize: typography.fontSize.sm, display: 'block', marginBottom: spacing.xs }}>→ World Model</span>
              <p style={{ color: colors.accent_cyan, fontFamily: 'monospace', fontSize: typography.fontSize.sm, marginBottom: spacing.xs }}>Flow: 96, SYN: 48, Entropy: 3.7</p>
            </div>
            <div>
              <span style={{ color: colors.text_secondary, fontSize: typography.fontSize.sm, display: 'block', marginBottom: spacing.xs }}>Predicted S(t+1)</span>
              <p style={{ color: colors.alert_warning, fontFamily: 'monospace', fontSize: typography.fontSize.sm, marginBottom: spacing.xs }}>Flow: 112, SYN: 62, Entropy: 4.5</p>
            </div>
          </div>
        </Card>
      </Container>
    </div>
  )
}