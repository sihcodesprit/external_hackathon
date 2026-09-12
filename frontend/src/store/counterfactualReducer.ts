import { createSlice, PayloadAction } from '@reduxjs/toolkit'

export interface CounterfactualState {
  baselineRisk: number
  simulatedRisk: number
  riskReduction: number
  riskReductionPct: number
  recommendedAction: string
  recommendedLabel: string
  affectedHosts: number
  blockedConnections: number
  actionResults: any[]
  error: string | null
}

const initialState: CounterfactualState = {
  baselineRisk: 0,
  simulatedRisk: 0,
  riskReduction: 0,
  riskReductionPct: 0,
  recommendedAction: 'No Action',
  recommendedLabel: 'No Action',
  affectedHosts: 0,
  blockedConnections: 0,
  actionResults: [],
  error: null,
}

export const counterfactualSlice = createSlice({
  name: 'counterfactual',
  initialState,
  reducers: {
    startProcessing: (state) => {
      state.status = 'processing'
      state.error = null
    },
    updateStage: (state, action: PayloadAction<{ stage: string }>) => {
      state.stage = action.stage
    },
    setSimulationResults: (state, action: PayloadAction<{
      baselineRisk: number; simulatedRisk: number; riskReduction: number; riskReductionPct: number
      recommendedAction: string; recommendedLabel: string; affectedHosts: number; blockedConnections: number
      actionResults: any[]
    }>) => {
      state.baselineRisk = action.baselineRisk
      state.simulatedRisk = action.simulatedRisk
      state.riskReduction = action.riskReduction
      state.riskReductionPct = action.riskReductionPct
      state.recommendedAction = action.recommendedAction
      state.recommendedLabel = action.recommendedLabel
      state.affectedHosts = action.affectedHosts
      state.blockedConnections = action.blockedConnections
      state.actionResults = action.actionResults
    },
    setError: (state, action: PayloadAction<string>) => {
      state.error = action.payload
    },
    clear: (state) => {
      Object.assign(state, initialState)
    },
  },
})

export const {
  startProcessing,
  updateStage,
  setSimulationResults,
  setError,
  clear,
} = counterfactualSlice.actions
export default counterfactualSlice.reducer