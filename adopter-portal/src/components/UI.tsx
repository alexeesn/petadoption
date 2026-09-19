import { ReactNode } from 'react'
import { Icon, PawMark } from './Icons'

export function Spinner({ label = 'Loading...' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-stone-500" role="status">
      <div
        className="h-9 w-9 animate-spin rounded-full border-[3px] border-stone-200 border-t-primary-600"
        aria-hidden="true"
      />
      <p className="mt-4 text-sm">{label}</p>
    </div>
  )
}

export function EmptyState({ message, action }: { message: string; action?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-stone-300 bg-white px-6 py-14 text-center">
      <div
        className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-accent-100 text-primary-900"
        aria-hidden="true"
      >
        <PawMark className="h-7 w-7" />
      </div>
      <p className="mx-auto max-w-sm text-stone-600">{message}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function ErrorState({ message = 'Something went wrong.', onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div className="rounded-xl border border-red-200 bg-white px-6 py-12 text-center" role="alert">
      <div
        className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-50 text-xl font-bold text-red-600"
        aria-hidden="true"
      >
        !
      </div>
      <p className="font-medium text-stone-800">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="btn btn-primary mt-5">
          Try again
        </button>
      )}
    </div>
  )
}

export function FieldError({ id, message }: { id?: string; message?: string }) {
  if (!message) return null
  return (
    <p id={id} role="alert" className="mt-1.5 text-sm text-red-600">
      {message}
    </p>
  )
}

export function Alert({ type = 'info', children }: { type?: 'info' | 'success' | 'error'; children: ReactNode }) {
  const styles = {
    info: 'border-primary-200 bg-primary-50 text-primary-900',
    success: 'border-green-200 bg-green-50 text-green-900',
    error: 'border-red-200 bg-red-50 text-red-900',
  }
  const bar = {
    info: 'bg-primary-500',
    success: 'bg-green-600',
    error: 'bg-red-600',
  }
  return (
    <div
      className={`relative overflow-hidden rounded-md border py-3 pl-5 pr-4 text-sm ${styles[type]}`}
      role={type === 'error' ? 'alert' : 'status'}
    >
      <span className={`absolute inset-y-0 left-0 w-1.5 ${bar[type]}`} aria-hidden="true" />
      {type === 'success' && <Icon name="check" className="mr-1.5 inline h-4 w-4 align-[-2px]" />}
      {children}
    </div>
  )
}
