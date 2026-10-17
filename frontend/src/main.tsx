import { MutationCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { LazyMotion, MotionConfig } from 'framer-motion'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import { App } from './App'
import { toast, ToastProvider } from './components/Toast'
import { AuthProvider } from './features/auth/AuthContext'
import { ApiError } from './lib/api'
import './styles/index.css'
import { ThemeProvider } from './theme/ThemeProvider'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 30_000 },
  },
  // Any failed write (booking, triage, commit, resolve, status change, …) raises
  // an ambient error toast in addition to any inline message at the call site.
  mutationCache: new MutationCache({
    onError: (error) => {
      toast({
        tone: 'danger',
        title: 'Something went wrong',
        description: error instanceof ApiError ? error.message : 'Please try again.',
      })
    },
  }),
})

// Lazy-load framer-motion's full feature set (layout, etc.) as its own chunk so
// the initial bundle stays small; `m` components render statically until it loads.
const loadMotionFeatures = () => import('framer-motion').then((mod) => mod.domMax)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <LazyMotion features={loadMotionFeatures} strict>
        <MotionConfig reducedMotion="user">
          <QueryClientProvider client={queryClient}>
            <BrowserRouter>
              <AuthProvider>
                <ToastProvider>
                  <App />
                </ToastProvider>
              </AuthProvider>
            </BrowserRouter>
          </QueryClientProvider>
        </MotionConfig>
      </LazyMotion>
    </ThemeProvider>
  </StrictMode>,
)
