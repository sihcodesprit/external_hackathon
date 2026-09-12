import { createSlice, PayloadAction } from '@reduxjs/toolkit'

export interface ForecastState {
  current: any
  future: any[]
  riskTimeline: any[]
  confidence: number
  stageTimeline: any[]
  error: string | null
}

const initialState: ForecastState = {
  current: { risk: 0, stage: 'Benign', confidence: 0 },
  future: [],
  riskTimeline: [],
  confidence: 0,
  stageTimeline: [],
  error: null,
}

export const forecastSlice = createSlice({
  name: 'forecast',
  initialState,
  reducers: {
    setForecast: (state, action: PayloadAction<{
      current: any; future: any[]; riskTimeline: any[]; confidence: number; stageTimeline: any[]
    }>) => {
      state.current = action.current
      state.future = action.future
      state.riskTimeline = action.riskTimeline
      state.confidence = action.confidence
      state.stageTimeline = action.stageTimeline
    },
    setError: (state, action: PayloadAction<string>) => {
      state.error = action.payload
    },
    clear: (state) => {
      Object.assign(state, initialState)
    },
  },
})

export const { setForecast, setError, clear } = forecastSlice.actions
export default forecastSlice.reducer