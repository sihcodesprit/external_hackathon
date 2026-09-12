import React, { useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { colors, typography, spacing } from '../styles/designSystem'
import { Card, MetricCard, Button } from '../components/ui'

export const CounterfactualLab = () => {
  const dispatch = useDispatch()
  const [showActions, setShowActions] = useState(false)
  const [selectedAction, setSelectedAction] useState<'no_action' | 'block_source' | 'isolate_host' | 'restrict_path' | 'terminate_flow' | 'block_dest_port'>('no_action')
  const counterfactual = useSelector(state => state.counterfactual)

  useEffect(() => {
    fetch('/api/counterfactual')
      .then(res => res.json())
      .then(data => {
        dispatch(setCounterfactualSimulation(data))
      })
  }, [dispatch])

  const handleAction = async (actionId: string) => {
    setSelectedAction(actionId)
    setShowActions(true)

    dispatch(startProcessing())
    dispatch(updateStage({ stage: `Simulating: ${actionId}`, message: 'Running counterfactual simulation...' }))

    try {
      const res = await fetch('/api/counterfactual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: actionId, k: 5 })
      })
      const result = await res.json()

      if (result.error) {
        dispatch(setError(result.error))
        return
      }

      dispatch(setSimulationResults({
        baselineRisk: result.baseline_current_risk,
        simulatedRisk: result.results[actionId]?.final_risk || 0,
        riskReduction: result.baseline_current_risk - (result.results[actionId]?.final_risk || 0),
        riskReductionPct: ((result.baseline_current_risk - (result.results[actionId]?.final_risk || 0)) * 100).toFixed(1),
        recommendedAction: result.recommendation?.recommended_action || 'No Action',
        recommendedLabel: result.recommendation?.recommended_label || 'No Action',
        affectedHosts: result.results[actionId]?.affected_hosts || 0,
        blockedConnections: result.results[actionId]?.blocked_connections || 0,
        actionResults: Object.entries(result.results).map(([id, r]) => ({
          action: id,
          risk: r.final_risk,
          peakRisk: r.peak_risk,
          label: r.label,
        }))
      }))

    } catch (err) {
      dispatch(setError('Counterfactual simulation failed'))
    }
  }

  return (
    <div className="counterfactual-screen" style={{ minHeight: '100vh', background: colors.background, color: colors.text_primary }}>
      <Container>
        <h2 style={{ color: colors.text_primary, fontSize: '2rem', fontWeight: 600, marginBottom: spacing.lg }}>
          Counterfactual Lab
        </h2>

        <Card style={{ marginBottom: spacing.lg }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.md }}>
            <span style={{ color: colors.text_primary, fontSize: typography.fontSize.lg, fontWeight: 500 }}>
              Simulate Defensive Actions
            </span>
            <span style={{ color: colors.text_muted, fontSize: typography.fontSize.sm }}>
              Test what-if scenarios before applying defenses
            </span>
          </div>

          {/* Action selection */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit', gap: spacing.md, marginBottom: spacing.lg) }}>
            <Button
              variant={selectedAction === 'no_action' ? 'primary' : 'outline'}
              style={{ width: '100%', padding: `${spacing.md} ${spacing.lg}`, fontSize: typography.fontSize.md }}
              onClick={() => handleAction('no_action')}
            >
              No Action
              <span style={{ float: 'right', color: colors.text_muted, fontSize: typography.fontSize.sm }}>
                Baseline: {(counterfactual.baselineRisk * 100).toFixed(0)}%
              </span>
            </Button>

            <Button
              variant={selectedAction === 'block_source' ? 'primary' : 'outline'}
              style={{ width: '100%', padding: `${spacing.md} ${spacing.lg}`, fontSize: typography.fontSize.md }}
              onClick={() => handleAction('block_source')}
            >
              Block Source
              <span style={{ float: 'right', color: colors.text_muted, fontSize: typography.fontSize.sm }}>
                {(counterfactual.actionResults.find(r => r.action === 'block_source')?.risk * 100).toFixed(0)}%
              </span>
            </Button>

            <Button
              variant={selectedAction === 'isolate_host' ? 'primary' : 'outline'}
              style={{ width: '100%', padding: `${spacing.md} ${spacing.lg}`, fontSize: typography.fontSize.md }}
              onClick={() => handleAction('isolate_host')}
            >
              Isolate Host
              <span style={{ float: 'right', color: colors.text_muted, fontSize: typography.fontSize.sm }}>
                {(counterfactual.actionResults.find(r => r.action === 'isolate_host')?.risk * 100).toFixed(0)}%
              </span>
            </Button>

            <Button
              variant={selectedAction === 'restrict_path' ? 'primary' : 'outline'}
              style={{ width: '100%', padding: `${spacing.md} ${spacing.lg}`, fontSize: typography.fontSize.md }}
              onClick={() => handleAction('restrict_path')}
            >
              Restrict Path
              <span style={{ float: 'right', color: colors.text_muted, fontSize: typography.fontSize.sm }}>
                {(counterfactual.actionResults.find(r => r.action === 'restrict_path')?.risk * 100).toFixed(0)}%
              </span>
            </Button>
          </div>

          {/* Current vs Simulated comparison */}
          {selectedAction !== 'no_action' && counterfactual.riskReduction > 0 && (
            <Card style={{ marginTop: spacing.lg, padding: spacing.lg, borderLeft: `4px solid ${colors.accent_blue}` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.md }}>
                <span>
                  <span style={{ color: colors.text_primary, fontSize: typography.fontSize.lg, fontWeight: 600 }}>Current World</span>
                  <p style={{ color: colors.alert_high, fontSize: typography.fontSize.xl, fontWeight: 700 }}>
                    {(counterfactual.baselineRisk * 100).toFixed(0)}%
                  </p>
                </span>
                <span>
                  <span style={{ color: colors.text_primary, fontSize: typography.fontSize.lg, fontWeight: 600 }}>Simulated World</span>
                  <p style={{ color: colors.alert_low, fontSize: typography.fontSize.xl, fontWeight: 700 }}>
                    {(counterfactual.simulatedRisk * 100).toFixed(0)}%
                  </p>
                </span>
              </div>
              <div style={{ display: 'flex', gap: spacing.lg, alignItems: 'center' }}>
                <span style={{ color: colors.text_secondary, fontSize: typography.fontSize.lg, fontWeight: 600 }}>
                  {counterfactual.riskReductionPct}% Risk Reduction
                </span>
                <span style={{ color: colors.text_muted, fontSize: typography.fontSize.sm }}>
                  ↓
                </span>
              </div>
              <p style={{ color: colors.text_secondary, fontSize: typography.fontSize.sm, marginTop: spacing.xs }}>
                {counterfactual.recommendedLabel} produces the largest predicted reduction in future attack risk
              </p>
              <p style={{ color: colors.text_muted, fontSize: typography.fontSize.sm, marginTop: spacing.xs }}>
                Affected Hosts: {counterfactual.affectedHosts} | Blocked Connections: {counterfactual.blockedConnections}
              </p>
            </Card>
          )}

          {/* Recommended Action */}
          {counterfactual.recommendedAction !== 'no_action' && (
            <div style={{ marginTop: spacing.lg, padding: spacing.lg, background: 'rgba(0, 212, 170, 0.1)', borderRadius: 8, border: `1px solid ${colors.accent_blue}` }}>
              <span style={{ color: colors.accent_blue, fontWeight: 600, fontSize: typography.fontSize.md }}>💡 Recommended Action</span>
              <p style={{ color: colors.text_secondary, fontSize: typography.fontSize.sm, marginTop: spacing.xs }}>
                {counterfactual.recommendedLabel}
              </p>
              <p style={{ color: colors.text_primary, fontSize: typography.fontSize.md, fontWeight: 500, marginTop: spacing.xs }}>
                {counterfactual.riskReductionPct}% risk reduction
              </p>
            </div>
          )}
        </Card>
      </Container>
    </div>
  )
}