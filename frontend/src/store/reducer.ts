import { combineReducers } from '@reduxjs/toolkit'

import uploadReducer from './uploadReducer'
import analysisReducer from './analysisReducer'
import forecastReducer from './forecastReducer'
import mitreReducer from './mitreReducer'
import explainabilityReducer from './explainabilityReducer'
import counterfactualReducer from './counterfactualReducer'
import systemReducer from './systemReducer'

export const rootReducer = combineReducers({
  upload: uploadReducer,
  analysis: analysisReducer,
  forecast: forecastReducer,
  mitre: mitreReducer,
  explainability: explainabilityReducer,
  counterfactual: counterfactualReducer,
  system: systemReducer,
})