import { ReactNode } from 'react'

export function Spinner({ label = 'Loading...' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-stone-500" role="status">
      <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-orange-600" />
      <p className="mt-4 text-sm">{label}</p>
    </div>
  )
}

export function EmptyState({ message, action }: { message: string; action?: ReactNode }) {
  return (
    <div className="text-center py-12 text-stone-500">
      <div className="text-4xl mb-3" aria-hidden="true">🐾</div>
      <p>{message}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function ErrorState({ message = 'Something went wrong.', onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div className="text-center py-12" role="alert">
      <div className="mx-auto mb-4 w-12 h-12 rounded-full bg-red-100 flex items-center justify-center text-2xl" aria-hidden="true">⚠️</div>
      <p className="text-stone-700 font-medium">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-4 px-4 py-2 bg-orange-600 text-white text-sm rounded-md hover:bg-orange-700">
          Try again
        </button>
      )}
    </div>
  )
}

export function FieldError({ id, message }: { id?: string; message?: string }) {
  if (!message) return null
  return (
    <p id={id} role="alert" className="mt-1 text-sm text-red-600">
      {message}
    </p>
  )
}

export function Alert({ type = 'info', children }: { type?: 'info' | 'success' | 'error'; children: ReactNode }) {
  const styles = {
    info: 'bg-blue-50 text-blue-800 border-blue-200',
    success: 'bg-green-50 text-green-800 border-green-200',
    error: 'bg-red-50 text-red-800 border-red-200',
  }
  return (
    <div className={`border rounded-md p-4 text-sm ${styles[type]}`} role={type === 'error' ? 'alert' : 'status'}>
      {children}
    </div>
  )
}
