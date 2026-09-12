import { createSlice, PayloadAction } from '@reduxjs/toolkit'

export interface AnalysisState {
  states: any[]
  networkState: any
  currentRisk: number
  forecastRisk: number
  activeHosts: number
  activeFlows: number
  anomalousFlows: number
  predictedStage: string
  confidence: number
  trafficSummary: any
  error: string | null
}

const initialState: AnalysisState = {
  states: [],
  networkState: {},
  currentRisk: 0,
  forecastRisk: 0,
  activeHosts: 0,
  activeFlows: 0,
  anomalousFlows: 0,
  predictedStage: 'Benign',
  confidence: 0,
  trafficSummary: {},
  error: null,
}

export const analysisSlice = createSlice({
  name: 'analysis',
  initialState,
  reducers: {
    setStates: (state, action: PayloadAction<any[]>) => {
      state.states = action.payload
    },
    setNetworkState: (state, action: PayloadAction<any>) => {
      state.networkState = action.payload
    },
    setRiskMetrics: (state, action: PayloadAction<{ currentRisk: number; forecastRisk: number }>) => {
      state.currentRisk = action.currentRisk
      state.forecastRisk = action.forecastRisk
    },
    setPredictedStage: (state, action: PayloadAction<{ stage: string; confidence: number }>) => {
      state.predictedStage = action.stage
      state.confidence = action.confidence
    },
    setTrafficSummary: (state, action: PayloadAction<{ nPackets: number; nFlows: number; nHosts: number; nProtocols: number; nUniquePorts: number; duration: string }>) => {
      state.trafficSummary = action.payload
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
  setStates,
  setNetworkState,
  setRiskMetrics,
  setPredictedStage,
  setTrafficSummary,
  setError,
  clear,
} = analysisSlice.actions

export default analysisSlice.reducer