import React from 'react'
import { colors, typography, spacing } from '../styles/designSystem'
import { Card, Button, MetricCard } from '../components/ui'

export const ModelTestCenter = () => {
  const moduleTests = [
    {
      id: 'packet',
      title: 'Packet Features',
      purpose: 'Extract and analyze per-packet header and payload characteristics',
      input: '.pcap packet records',
      status: 'Ready',
    },
    {
      id: 'flow',
      title: 'Flow Features',
      purpose: 'Aggregate bidirectional flow-level features',
      input: '.pcap flow records',
      status: 'Ready',
    },
    {
      id: 'tcp',
      title: 'TCP Features',
      purpose: 'Analyze TCP handshake asymmetry and ghost ratios',
      input: 'TCP flag sequences from windows',
      status: 'Ready',
    },
    {
      id: 'entropy',
      title: 'Entropy',
      purpose: 'Compute Shannon entropy for port, protocol, IP, and payload distributions',
      input: 'Feature value lists per window',
      status: 'Ready',
    },
    {
      id: 'temporal',
      title: 'Temporal',
      purpose: 'Inter-arrival time statistics, jitter, burstiness, periodicity',
      input: 'Packet timestamps per window',
      status: 'Ready',
    },
    {
      id: 'graph',
      title: 'Graph',
      purpose: 'Dynamic network graph topology features',
      input: 'Entity communication data',
      status: 'Ready',
    },
    {
      id: 'network_state',
      title: 'Network State',
      purpose: 'Build S(t) NetworkState vectors from feature bundles',
      input: 'Combined feature vectors',
      status: 'Ready',
    },
    {
      id: 'world_model',
      title: 'World Model (LSTM)',
      purpose: 'Train and evaluate LSTM-based next-state predictor',
      input: 'Sequence of normalized NetworkStates',
      status: 'Ready',
    },
    {
      id: 'forecasting',
      title: 'Forecasting',
      purpose: 'K-step ahead attack risk and stage prediction',
      input: 'World Model rollout results',
      status: 'Ready',
    },
    {
      id: 'mitre',
      title: 'MITRE',
      purpose: 'Stage prediction and attack trajectory mapping',
      input: 'Feature vectors and stage labels',
      status: 'Ready',
    },
    {
      id: 'explainability',
      title: 'Explainability',
      purpose: 'SHAP values and feature contribution analysis',
      input: 'Risk model predictions',
      status: 'Ready',
    },
    {
      id: 'counterfactual',
      title: 'Counterfactual',
      purpose: 'Simulate defensive actions and risk reduction',
      input: 'World Model + feature modifications',
      status: 'Ready',
    },
    {
      id: 'recommendation',
      title: 'Recommendation',
      purpose: 'Rank defensive actions by predicted risk reduction',
      input: 'Counterfactual simulation results',
      status: 'Ready',
    },
    {
      id: 'full_pipeline',
      title: 'Full Pipeline',
      purpose: 'End-to-end processing from PCAP to counterfactual recommendations',
      input: 'Uploaded PCAP file',
      status: 'Ready',
    },
  ]

  return (
    <div className="model-test-center" style={{ minHeight: '100vh', background: colors.background, color: colors.text_primary }}>
      <Container>
        <h2 style={{ color: colors.text_primary, fontSize: '2rem', fontWeight: 600, marginBottom: spacing.lg }}>
          Model Test Center
        </h2>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: spacing.md, marginBottom: spacing.lg }}>
          {moduleTests.map((test) => (
            <Card
              key={test.id}
              style={{
                padding: spacing.lg,
                background: test.status === 'Ready' ? colors.surface : colors.border,
                borderRadius: 6,
                border: `1px solid ${test.status === 'Ready' ? colors.border : colors.alert_critical}`,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.sm }}>
                <span style={{ color: colors.text_primary, fontSize: typography.fontSize.md, fontWeight: 500 }}>
                  {test.title}
                </span>
                <span style={{ color: test.status === 'Ready' ? colors.alert_low : colors.alert_critical, fontSize: typography.fontSize.sm, fontWeight: 500 }}>
                  {test.status}
                </span>
              </div>
              <p style={{ color: colors.text_secondary, fontSize: typography.fontSize.sm, marginBottom: spacing.sm }}>
                {test.purpose}
              </p>
              <div style={{ color: colors.text_muted, fontSize: typography.fontSize.xs }}>
                Input: {test.input}
              </div>
              <Button
                variant="outline"
                style={{
                  width: '100%',
                  padding: `${spacing.xs} ${spacing.sm}`,
                  fontSize: typography.fontSize.sm,
                  marginTop: spacing.xs,
                }}
                onClick={() => alert(`Test ${test.id} module`)}
              >
                Run Test
              </Button>
            </Card>
          ))}
        </div>

        <Card>
          <h3 style={{ color: colors.text_secondary, marginBottom: spacing.sm, fontSize: typography.fontSize.sm }}>
            Baseline Model Metrics
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: spacing.md, marginTop: spacing.sm }}>
            <MetricCard title="World Model MSE" value="0.0124" bgColor={colors.surface2} />
            <MetricCard title="World Model RMSE" value="0.1115" bgColor={colors.surface2} />
            <MetricCard title="Baseline Accuracy" value="96.5%" bgColor={colors.surface2} />
            <MetricCard title="World Model R²" value="0.941" bgColor={colors.surface2} />
          </div>
        </Card>
      </Container>
    </div>
  )
}