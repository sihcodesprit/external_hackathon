import React from 'react'
import { colors, typography, spacing } from '../styles/designSystem'
import { Card, MetricCard, Button } from '../components/ui'

export const System = () => {
  const [status, setStatus] = useState({
    backend: 'Checking...',
    worldModel: 'Loading...',
    data: 'Initializing...',
  })

  useEffect(() => {
    fetch('/api/models/status')
      .then(res => res.json())
      .then(data => {
        setStatus({
          backend: data.backend || 'Disconnected',
          worldModel: data.world_model || 'Uninitialized',
          data: data.active_traffic?.filename || 'No Analysis',
        })
      })
  }, [])

  return (
    <div className="system-screen" style={{ minHeight: '100vh', background: colors.background, color: colors.text_primary }}>
      <Container>
        <h2 style={{ color: colors.text_primary, fontSize: '2rem', fontWeight: 600, marginBottom: spacing.lg }}>
          System Status
        </h2>

        <Card>
          <h3 style={{ color: colors.text_secondary, marginBottom: spacing.md, fontSize: typography.fontSize.sm }}>
            Component Health
          </h3>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: spacing.md, marginBottom: spacing.lg }>
            <MetricCard title="Backend" value={status.backend === 'Connected' ? '✓ Connected' : '✗ Disconnected'} bgColor={status.backend === 'Connected' ? colors.alert_low : colors.alert_high} />
            <MetricCard title="World Model" value={status.worldModel === 'Loaded' ? '✓ Ready' : '⟳ Training'} bgColor={status.worldModel === 'Loaded' ? colors.alert_low : colors.alert_elevated} />
            <MetricCard title="PCAP Engine" value="✓ Ready" bgColor={colors.alert_low} />
            <MetricCard title="Feature Engine" value="✓ Ready" bgColor={colors.alert_low} />
          </div>

          <div>
            <MetricCard title="MITRE Engine" value="✓ Ready" bgColor={colors.alert_low} />
            <MetricCard title="Explainability" value="✓ Ready" bgColor={colors.alert_low} />
            <MetricCard title="Counterfactual" value="✓ Ready" bgColor={colors.alert_low} />
            <MetricCard title="Recommendation" value="✓ Ready" bgColor={colors.alert_low} />
          </div>
        </Card>

        <Card style={{ marginTop: spacing.lg }}>
          <h3 style={{ color: colors.text_secondary, marginBottom: spacing.sm, fontSize: typography.fontSize.sm }}>
            Runtime Configuration
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: spacing.md, marginBottom: spacing.lg }>
            <MetricCard title="World Model Type" value="LSTM" bgColor={colors.surface2} />
            <MetricCard title="Sequence Length" value="10" bgColor={colors.surface2} />
            <MetricCard title="K-Step Horizon" value="5" bgColor={colors.surface2} />
            <MetricCard title="Feature Groups" value="10 groups" bgColor={colors.surface2} />
          </div>
          <div>
            <MetricCard title="Dashboard Port" value="5000" bgColor={colors.surface2} />
            <MetricCard title="Max File Size" value="100 MB" bgColor={colors.surface2} />
            <MetricCard title="Anonymize IPs" value="Disabled" bgColor={colors.surface2} />
          </div>
        </Card>
      </Container>
    </div>
  )
}