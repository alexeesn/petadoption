import { useCallback, useEffect, useState } from 'react'
import { fetchDocuments, deleteDocument } from '../services/apiService'
import { useAuth } from '../context/AuthContext'
import { Spinner, EmptyState, ErrorState, Alert, FieldError } from '../components/UI'
import type { Document } from '../types'

export default function DocumentsPage() {
  const { token } = useAuth()
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedType, setSelectedType] = useState('identification')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploadError, setUploadError] = useState('')
  const [success, setSuccess] = useState('')

  const load = useCallback(async () => {
    if (!token) return
    setLoading(true)
    setError('')
    try {
      const data = await fetchDocuments()
      setDocuments(Array.isArray(data) ? data : data.results ?? [])
    } catch {
      setError('Unable to load your documents.')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    load()
  }, [load])

  const handleUpload = (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedFile) {
      setUploadError('Please select a file to upload.')
      return
    }
    setUploadError(
      'Please open an application and upload your documents from there so they can be attached to the correct application.'
    )
  }

  const handleDelete = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this document?')) return
    try {
      await deleteDocument(id)
      setDocuments((prev) => prev.filter((d) => d.id !== id))
      setSuccess('Document deleted.')
    } catch {
      setError('Failed to delete document.')
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-stone-800 mb-2">My Documents</h1>
      <p className="text-stone-500 mb-6">View documents attached to your adoption applications.</p>

      {success && <div className="mb-4"><Alert type="success">{success}</Alert></div>}
      {error && <div className="mb-4"><ErrorState message={error} onRetry={load} /></div>}

      <div className="bg-white rounded-lg shadow-sm border border-orange-100 p-6 mb-6">
        <h2 className="text-lg font-semibold text-stone-800 mb-4">Upload a Document</h2>
        <form onSubmit={handleUpload} className="space-y-4">
          <div>
            <label htmlFor="docType" className="block text-sm font-medium text-stone-700 mb-1">
              Document Type
            </label>
            <select
              id="docType"
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="w-full rounded-md border border-stone-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500"
            >
              <option value="identification">Identification</option>
              <option value="proof_of_address">Proof of Address</option>
              <option value="income_proof">Income Proof</option>
              <option value="vet_reference">Veterinary Reference</option>
              <option value="personal_reference">Personal Reference</option>
              <option value="home_photos">Home Photos</option>
              <option value="lease_agreement">Lease Agreement</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div>
            <label htmlFor="file" className="block text-sm font-medium text-stone-700 mb-1">
              File
            </label>
            <input
              id="file"
              type="file"
              onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
              className="w-full text-sm text-stone-600 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:bg-orange-100 file:text-orange-700 hover:file:bg-orange-200"
            />
            <p className="text-xs text-stone-400 mt-1">Accepted: PDF, images, DOC/DOCX, TXT. Max 10MB.</p>
          </div>
          {uploadError && <FieldError message={uploadError} />}
          <button
            type="submit"
            disabled={!selectedFile}
            className="px-4 py-2 bg-orange-600 text-white text-sm rounded-md hover:bg-orange-700 disabled:opacity-50"
          >
            Upload
          </button>
        </form>
      </div>

      {loading ? (
        <Spinner />
      ) : documents.length === 0 ? (
        <EmptyState message="No documents uploaded yet." />
      ) : (
        <div className="bg-white rounded-lg shadow-sm border border-orange-100 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-stone-200">
              <thead className="bg-stone-50">
                <tr>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-stone-500 uppercase">Type</th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-stone-500 uppercase">Filename</th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-stone-500 uppercase">Size</th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-stone-500 uppercase">Uploaded</th>
                  <th scope="col" className="px-4 py-3 text-right text-xs font-medium text-stone-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-200">
                {documents.map((doc) => (
                  <tr key={doc.id}>
                    <td className="px-4 py-3 text-sm text-stone-700 capitalize">{doc.document_type.replace(/_/g, ' ')}</td>
                    <td className="px-4 py-3 text-sm text-stone-700">{doc.original_filename}</td>
                    <td className="px-4 py-3 text-sm text-stone-500">{(doc.file_size / 1024).toFixed(1)} KB</td>
                    <td className="px-4 py-3 text-sm text-stone-500">{new Date(doc.created_at).toLocaleDateString()}</td>
                    <td className="px-4 py-3 text-right text-sm">
                      {doc.download_url && (
                        <a href={doc.download_url} className="text-orange-600 hover:text-orange-700 mr-3">Download</a>
                      )}
                      <button
                        onClick={() => handleDelete(doc.id)}
                        className="text-red-600 hover:text-red-700"
                        aria-label={`Delete ${doc.original_filename}`}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
