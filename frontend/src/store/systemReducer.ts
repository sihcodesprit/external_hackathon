import { createSlice, PayloadAction } from '@reduxjs/toolkit'

export interface SystemState {
  backend: string
  worldModel: string
  data: string
  error: string | null
}

const initialState: SystemState = {
  backend: 'Disconnected',
  worldModel: 'Uninitialized',
  data: 'No Analysis',
  error: null,
}

export const systemSlice = createSlice({
  name: 'system',
  initialState,
  reducers: {
    setStatus: (state, action: PayloadAction<{
      backend: string; worldModel: string; data: string
    }>) => {
      state.backend = action.backend
      state.worldModel = action.worldModel
      state.data = action.data
    },
    setError: (state, action: PayloadAction<string>) => {
      state.error = action.payload
    },
    clear: (state) => {
      Object.assign(state, initialState)
    },
  },
})

export const { setStatus, setError, clear } = systemSlice.actions
export default systemSlice.reducer