import { createSlice, PayloadAction } from '@reduxjs/toolkit'

export interface UploadState {
  isProcessing: boolean
  progress: number
  currentStage: string
  statusMessage: string
  nPackets: number
  nFlows: number
  nHosts: number
  nProtocols: number
  nUniquePorts: number
  duration: string
  filename: string
  error: string | null
}

const initialState: UploadState = {
  isProcessing: false,
  progress: 0,
  currentStage: 'Idle',
  statusMessage: 'Ready to analyze',
  nPackets: 0,
  nFlows: 0,
  nHosts: 0,
  nProtocols: 0,
  nUniquePorts: 0,
  duration: '0s',
  filename: '',
  error: null,
}

export const uploadSlice = createSlice({
  name: 'upload',
  initialState,
  reducers: {
    startProcessing: (state) => {
      state.isProcessing = true
      state.progress = 0
      state.currentStage = 'Archive detected'
      state.statusMessage = 'Starting analysis pipeline...'
    },
    updateStage: (state, action: PayloadAction<{ stage: string; message: string }>) => {
      state.currentStage = action.stage
      state.statusMessage = action.message
    },
    updateProgress: (state, action: PayloadAction<{ progress: number; stage: string }>) => {
      state.progress = action.progress
      state.currentStage = action.stage
    },
    setMetrics: (state, action: PayloadAction<{
      nPackets: number; nFlows: number; nHosts: number; nProtocols: number; nUniquePorts: number; duration: string
    }>) => {
      state.isProcessing = false
      state.nPackets = action.nPackets
      state.nFlows = action.nFlows
      state.nHosts = action.nHosts
      state.nProtocols = action.nProtocols
      state.nUniquePorts = action.nUniquePorts
      state.duration = action.duration
      state.statusMessage = 'Analysis complete'
    },
    setError: (state, action: PayloadAction<string>) => {
      state.isProcessing = false
      state.error = action.payload
      state.statusMessage = 'Analysis failed'
    },
    reset: (state) => {
      Object.assign(state, initialState)
    },
  },
})

export const {
  startProcessing,
  updateStage,
  updateProgress,
  setMetrics,
  setError,
  reset,
} = uploadSlice.actions

export default uploadSlice.reducer