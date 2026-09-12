import { createSlice, PayloadAction } from '@reduxjs/toolkit'

export interface MitreState {
  trajectory: any[]
  observedStage: string
  currentStage: string
  confidence: number
  error: string | null
}

const initialState: MitreState = {
  trajectory: [],
  observedStage: 'Reconnaissance',
  currentStage: 'Reconnaissance',
  confidence: 0,
  error: null,
}

export const mitreSlice = createSlice({
  name: 'mitre',
  initialState,
  reducers: {
    setMitreTrajectory: (state, action: PayloadAction<any[]>) => {
      state.trajectory = action.payload
    },
    setObservedStage: (state, action: PayloadAction<string>) => {
      state.observedStage = action.payload
    },
    setCurrentStage: (state, action: PayloadAction<{ stage: string; confidence: number }>) => {
      state.currentStage = action.stage
      state.confidence = action.confidence
    },
    setError: (state, action: PayloadAction<string>) => {
      state.error = action.payload
    },
    clear: (state) => {
      Object.assign(state, initialState)
    },
  },
})

export const { setMitreTrajectory, setObservedStage, setCurrentStage, setError, clear } = mitreSlice.actions
export default mitreSlice.reducer