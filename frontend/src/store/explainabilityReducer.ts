import { createSlice, PayloadAction } from '@reduxjs/toolkit'

export interface ExplainabilityState {
  topContributors: any[]
  plainLanguage: string
  featureContributions: any[]
  error: string | null
}

const initialState: ExplainabilityState = {
  topContributors: [],
  plainLanguage: '',
  featureContributions: [],
  error: null,
}

export const explainabilitySlice = createSlice({
  name: 'explainability',
  initialState,
  reducers: {
    setTopContributors: (state, action: PayloadAction<any[]>) => {
      state.topContributors = action.payload
    },
    setPlainLanguage: (state, action: PayloadAction<string>) => {
      state.plainLanguage = action.payload
    },
    setFeatureContributions: (state, action: PayloadAction<any[]>) => {
      state.featureContributions = action.payload
    },
    setError: (state, action: PayloadAction<string>) => {
      state.error = action.payload
    },
    clear: (state) => {
      Object.assign(state, initialState)
    },
  },
})

export const { setTopContributors, setPlainLanguage, setFeatureContributions, setError, clear } = explainabilitySlice.actions
export default explainabilitySlice.reducer