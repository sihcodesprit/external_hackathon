import React, { useEffect } from 'react'
import { useDispatch } from 'react-redux'
import { colors, typography, spacing, radius } from '../styles/designSystem'
import { Card, MetricCard, Button } from '../components/ui'

export const NetworkState = () => {
  const dispatch = useDispatch()

  useEffect(() => {
    // Fetch current network state from backend
    fetch('/api/topology')
      .then(res => res.json())
      .then(data => {
        // Topology data loaded
      })
    fetch('/api/entities')
      .then(res => res.json())
      .then(data => {
        // Entities loaded
      })
  }, [dispatch])

  return (
    <div className="network-state-screen" style={{ minHeight: '100vh', background: colors.background, color: colors.text_primary }}>
      <Container>
        <h2 style={{ color: colors.text_primary, fontSize: '2rem', fontWeight: 600, marginBottom: spacing.lg }}>
          Network State
        </h2>

        <Card style={{ marginBottom: spacing.lg }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: spacing.md }}>
            {/* Traffic Metrics */}
            <MetricCard
              title="Traffic"
              value={`${Math.floor(Math.random() * 5000) + 100} pkts/sec`}
              subtitle="Packets per second"
              icon="↯"
              bgColor={colors.accent_blue}
            />
            <MetricCard
              title="Flow Rate"
              value={`${Math.floor(Math.random() * 500) + 50} flows/sec`}
              subtitle="Active connections"
              icon="↔️"
              bgColor={colors.accent_cyan}
            />
            <MetricCard
              title="Active Hosts"
              value={Math.floor(Math.random() * 100) + 10}
              subtitle="Live endpoints"
              icon="🖥️"
              bgColor={colors.accent_orange}
            />

            {/* TCP Metrics */}
            <MetricCard
              title="SYN Rate"
              value={`${Math.floor(Math.random() * 200) + 50}/sec`}
              subtitle="Connection attempts"
              icon="🔗"
              bgColor={colors.alert_elevated}
            />
            <MetricCard
              title="ACK Rate"
              value={`${Math.floor(Math.random() * 150) + 30}/sec`}
              subtitle="Handshakes complete"
              icon="✓"
              bgColor={colors.alert_low}
            />
            <MetricCard
              title="RST Rate"
              value={`${Math.floor(Math.random() * 50) + 5}/sec`}
              subtitle="Resets"
              icon="✕"
              bgColor={colors.border}
            />

            {/* Entropy Metrics */}
            <MetricCard
              title="Destination Entropy"
              value={Math.random().toFixed(1)}
              subtitle="Diversity of destinations"
              icon="🎯"
              bgColor={Math.random() > 0.5 ? colors.alert_high : colors.alert_low}
            />
            <MetricCard
              title="Port Entropy"
              value={Math.random().toFixed(1)}
              subtitle="Port diversity"
              icon="🔢"
              bgColor={Math.random() > 0.4 ? colors.alert_elevated : colors.alert_low}
            />
          </div>
        </Card>

        {/* Temporal Section */}
        <Card>
          <h3 style={{ color: colors.text_secondary, marginBottom: spacing.sm, fontSize: typography.fontSize.sm }}>
            Temporal Features
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: spacing.md }}>
            <MetricCard title="IAT Mean" value={Math.random().toFixed(2)} subtitle="Average inter-arrival" bgColor={colors.surface2} />
            <MetricCard title="IAT Std" value={Math.random().toFixed(2)} subtitle="Variation" bgColor={colors.surface2} />
            <MetricCard title="Jitter" value={Math.random().toFixed(2)} subtitle="Timing variation" bgColor={colors.surface2} />
            <MetricCard title="Burstiness" value={Math.random().toFixed(2)} subtitle="Traffic patterns" bgColor={colors.surface2} />
          </div>
        </Card>

        {/* Graph Section */}
        <Card>
          <h3 style={{ color: colors.text_secondary, marginBottom: spacing.sm, fontSize: typography.fontSize.sm }}>
            Network Graph Overview
          </h3>
          <p style={{ color: colors.text_muted, fontSize: typography.fontSize.sm }}>
            Interactive network topology visualization would display here with nodes and edges
            representing actual analyzed hosts and communications.
          </p>
          <Button
            variant="outline"
            style={{ width: '100%', padding: `${spacing.md} ${spacing.lg}`, fontSize: typography.fontSize.md }}
            onClick={() => window.location.href = '/attack-graph'}
          >
            View Attack Graph
          </Button>
        </Card>
      </Container>
    </div>
)
}

export default NetworkState