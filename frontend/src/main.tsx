// FILE: frontend/src/main.tsx
// VERSION: 1.0.0
// ROLE: ENTRY_POINT
// MAP_MODE: SUMMARY
// START_MODULE_CONTRACT
//   PURPOSE: Application entry point -- creates React root, sets up QueryClient provider, renders App
//   SCOPE: ReactDOM.createRoot, QueryClient configuration with staleTime/retry defaults, StrictMode wrapper
//   DEPENDS: M-009 (frontend-user)
//   LINKS: M-009 (frontend-user)
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   queryClient - QueryClient instance with 5min staleTime, retry 1
//   AppRoot - ReactDOM.createRoot + QueryClientProvider + StrictMode + App
//   BLOCK_MAIN - main.tsx entry point (23 lines)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
// END_CHANGE_SUMMARY
//
// START_BLOCK_MAIN
import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from 'react-query'
import App from './App'
import './index.css'
import './i18n'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
)
// END_BLOCK_MAIN
