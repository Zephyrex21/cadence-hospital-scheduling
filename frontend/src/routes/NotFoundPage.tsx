import { Link } from 'react-router-dom'

import { Button } from '../components/Button'
import { Illustration404 } from '../components/illustrations'

export function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <Illustration404 />
      <div>
        <h2 className="font-display text-title font-semibold text-ink">Page not found</h2>
        <p className="mt-1 text-sm text-muted">
          That screen doesn&apos;t exist. Let&apos;s get you back to the dashboard.
        </p>
      </div>
      <Link to="/">
        <Button>Back to dashboard</Button>
      </Link>
    </div>
  )
}
