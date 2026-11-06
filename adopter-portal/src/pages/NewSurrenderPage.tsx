import { Link, useNavigate } from 'react-router-dom'
import RequestForm from '../features/surrenders/RequestForm'

export default function NewSurrenderPage() {
  const navigate = useNavigate()
  return <div className="mx-auto max-w-3xl space-y-6"><Link to="/surrenders" className="text-sm font-semibold text-primary-700">← My Surrender Requests</Link><div><h1 className="text-3xl font-bold text-stone-900">Request to surrender a pet</h1><p className="mt-2 text-sm text-stone-600">An initial request helps the center assess and coordinate intake before you travel.</p></div><RequestForm onSaved={request => navigate(`/surrenders/${request.id}`, { state: { submitted: true } })} /></div>
}
