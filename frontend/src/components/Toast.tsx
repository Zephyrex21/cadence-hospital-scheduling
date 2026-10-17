import { AnimatePresence, m } from 'framer-motion'
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

type ToastTone = 'success' | 'warning' | 'danger' | 'info'

interface ToastItem {
  id: number
  tone: ToastTone
  title: string
  description?: string
}

interface ToastApi {
  toast: (t: Omit<ToastItem, 'id'>) => void
}

const ToastContext = createContext<ToastApi | null>(null)

// Imperative bridge so non-React callers (e.g. the QueryClient's global mutation
// error handler, created outside the provider) can raise a toast. Set while a
// ToastProvider is mounted.
let emit: ((t: Omit<ToastItem, 'id'>) => void) | null = null

/** Raise a toast from outside React (no hook). No-op if no provider is mounted. */
export function toast(t: Omit<ToastItem, 'id'>): void {
  emit?.(t)
}

const ICON: Record<ToastTone, typeof Info> = {
  success: CheckCircle2,
  warning: AlertTriangle,
  danger: XCircle,
  info: Info,
}
const ACCENT: Record<ToastTone, string> = {
  success: 'text-success',
  warning: 'text-warning',
  danger: 'text-danger',
  info: 'text-info',
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const idRef = useRef(0)

  const dismiss = useCallback((id: number) => {
    setItems((x) => x.filter((t) => t.id !== id))
  }, [])

  const toast = useCallback(
    (t: Omit<ToastItem, 'id'>) => {
      const id = (idRef.current += 1)
      setItems((x) => [...x, { ...t, id }])
      window.setTimeout(() => dismiss(id), 5000)
    },
    [dismiss],
  )

  const api = useMemo<ToastApi>(() => ({ toast }), [toast])

  // Expose the imperative bridge while this provider is mounted.
  useEffect(() => {
    emit = toast
    return () => {
      if (emit === toast) emit = null
    }
  }, [toast])

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(92vw,22rem)] flex-col gap-2"
      >
        <AnimatePresence initial={false}>
          {items.map((t) => {
            const Icon = ICON[t.tone]
            return (
              <m.div
                key={t.id}
                layout
                role="status"
                initial={{ opacity: 0, y: 12, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8, scale: 0.98 }}
                transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                className="pointer-events-auto flex items-start gap-3 rounded-card border border-hairline bg-elevated p-3 shadow-lg"
              >
                <Icon size={18} aria-hidden className={`mt-0.5 shrink-0 ${ACCENT[t.tone]}`} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-ink">{t.title}</p>
                  {t.description && <p className="mt-0.5 text-xs text-muted">{t.description}</p>}
                </div>
                <button
                  onClick={() => dismiss(t.id)}
                  aria-label="Dismiss"
                  className="-m-1 rounded-control p-1 text-muted transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
                >
                  <X size={14} />
                </button>
              </m.div>
            )
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within a ToastProvider')
  return ctx
}
