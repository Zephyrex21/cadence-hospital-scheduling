import { useSyncExternalStore } from 'react'

import { getBackendStatus, subscribeBackend, type BackendStatus } from './backend'

/** Live view of the backend wake state (see `backend.ts`). */
export function useBackendStatus(): BackendStatus {
  return useSyncExternalStore(subscribeBackend, getBackendStatus, getBackendStatus)
}
