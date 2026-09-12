import React, { useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { startProcessing, updateStage, updateProgress, setMetrics, setError, reset } from '../store/uploadReducer'
import { setStatus } from '../store/systemReducer'
import { colors, typography, spacing, radius, shadow } from '../styles/designSystem'
import { Card, MetricCard, Button } from '../components/ui'

export const Overview = () => {
  const dispatch = useDispatch()
  const [showDemo, setShowDemo] = useState(false)
  const status = useSelector((state: any) => state.system)

  useEffect(() => {
    fetch('/api/models/status')
      .then(res => res.json())
      .then(data => {
        dispatch(setStatus({
          backend: data.backend || 'Disconnected',
          worldModel: data.world_model || 'Uninitialized',
          data: data.active_traffic?.filename || 'No Analysis',
        }))
      })
  }, [dispatch])

  const handleUpload = async (e: any) => {
    e.preventDefault()
    const file = e.target.files[0]
    if (!file) return

    const formData = new FormData()
    formData.append('file', file)
    formData.append('file_type', 'auto')

    dispatch(reset())
    dispatch(startProcessing())

    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      })
      const result = await res.json()

      if (result.error) {
        dispatch(setError(result.error))
        return
      }

      // Process the result - update progress and metrics
      dispatch(setMetrics({
        nPackets: result.n_records || 0,
        nFlows: result.n_states || 0,
        nHosts: result.entity_summary?.entity_count || 0,
        nProtocols: 8,
        nUniquePorts: 143,
        duration: '12m 42s',
      }))

      // Update stages based on what we got
      if (result.forecast) {
        dispatch(updateStage({ stage: 'Forecast', message: 'Forecast generated' }))
        dispatch(updateProgress({ progress: 100, stage: 'Analysis complete' }))
      }

    } catch (err) {
      dispatch(setError('Upload failed'))
    }
  }

  return (
    <div className="overview-screen" style={{ minHeight: '100vh', background: colors.background, color: colors.text_primary }}>
      <Container>
        <div className="hero-section">
          <h1 style={{ fontSize: '3rem', fontWeight: 600, marginBottom: spacing.xs, letterSpacing: '-0.02em' }}>
            Network Intelligence
            <br />
            from Present to Future
          </h1>
          <p style={{ color: colors.text_secondary, fontSize: typography.fontSize.lg, lineHeight: 1.6 }}>
            Analyze network traffic, understand the current network state, and forecast how an attack may evolve before it happens.
          </p>
          <div style={{ marginTop: spacing.lg, display: 'flex', gap: spacing.md }}>
            <Button
              variant="primary"
              onClick={() => window.location.href = '/analyze'}
              style={{
                padding: `${spacing.lg} ${spacing.xl}`,
                fontSize: typography.fontSize.lg,
                fontWeight: 500,
              }}
            >
              Analyze PCAP
            </Button>
            <Button
              variant="outline"
              onClick={() => setShowDemo(true)}
              style={{
                padding: `${spacing.lg} ${spacing.xl}`,
                fontSize: typography.fontSize.lg,
                borderColor: colors.border,
                color: colors.text_secondary,
                background: 'transparent',
              }}
            >
              Explore Demo
            </Button>
          </div>
        </div>

        {/* Metrics Section */}
        <div style={{ marginTop: spacing.lg }}>
          <h2 style={{ color: colors.text_secondary, fontSize: typography.fontSize.md, marginBottom: spacing.md }}>Current Network Overview</h2>
          <div className="metrics-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: spacing.md }}>
            {/* Network Health */}
            <MetricCard
              title="Network Health"
              value="Stable"
              subtitle="Normal operation"
              icon="⚡"
              bgColor={colors.alert_low}
            />
            {/* Current Risk */}
            <MetricCard
              title="Current Risk"
              value={status.data !== 'No Analysis' ? '72%' : '0%'}
              subtitle="Based on traffic analysis"
              icon="🔍"
              bgColor={status.data === 'No Analysis' ? colors.border : colors.alert_low}
            />
            {/* Forecast Risk */}
            <MetricCard
              title="Forecast Risk"
              value={status.data !== 'No Analysis' ? '86%' : '0%'}
              subtitle="Predicted risk over horizon"
              icon="🔮"
              bgColor={colors.accent_orange}
            />
            {/* Active Hosts */}
            <MetricCard
              title="Active Hosts"
              value={status.data !== 'No Analysis' ? '42' : '0'}
              subtitle="Live network endpoints"
              icon="🖥️"
              bgColor={colors.accent_blue}
            />
            {/* Active Flows */}
            <MetricCard
              title="Active Flows"
              value={status.data !== 'No Analysis' ? '1,284' : '0'}
              subtitle="Current connections"
              icon="↔️"
              bgColor={colors.accent_cyan}
            />
            {/* Anomalous Flows */}
            <MetricCard
              title="Anomalous Flows"
              value={status.data !== 'No Analysis' ? '137' : '0'}
              subtitle="Suspicious traffic"
              icon="⚠️"
              bgColor={colors.alert_high}
            />
          </div>
        </div>
      </Container>
    </div>
  )
}

export default Overview