import { useEffect, useState } from 'react';
import { Card, Loading, ErrorMessage, Empty, Table } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { documentService, openDocument, saveDocument } from '../services/apiService';
import type { Document } from '../types';

export default function DocumentsPage() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState('');

  const load = () => {
    setLoading(true);
    setError('');
    documentService
      .list()
      .then((res) => setDocs(res.data.results))
      .catch(() => setError('Failed to load documents.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleDelete = (id: string) => {
    if (!window.confirm('Delete this document?')) return;
    documentService
      .remove(id)
      .then(load)
      .catch(() => setError('Failed to delete document.'));
  };

  // Documents are private, so they are fetched with the auth token instead of
  // being linked directly (a plain <a href> cannot send the Authorization header).
  const handleOpen = async (doc: Document) => {
    setBusyId(doc.id);
    setError('');
    try {
      await openDocument(doc.id);
    } catch {
      setError('Failed to open the document.');
    } finally {
      setBusyId('');
    }
  };

  const handleDownload = async (doc: Document) => {
    setBusyId(doc.id);
    setError('');
    try {
      await saveDocument(doc.id, doc.original_filename);
    } catch {
      setError('Failed to download the document.');
    } finally {
      setBusyId('');
    }
  };

  return (
    <div>
      <PageHeader title="Documents" subtitle="Review submitted application documents" />
      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorMessage message={error} />
      ) : docs.length === 0 ? (
        <Card><Empty message="No documents found." /></Card>
      ) : (
        <Card>
          <Table headers={['Type', 'Filename', 'Size', 'Application', 'Uploaded', '']}>
            {docs.map((doc) => (
              <tr key={doc.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-sm font-medium text-slate-900">{doc.document_type.replace(/_/g, ' ')}</td>
                <td className="px-4 py-3 text-sm text-slate-600">
                  <button
                    type="button"
                    onClick={() => handleOpen(doc)}
                    disabled={busyId === doc.id}
                    className="text-primary-600 hover:underline disabled:opacity-50"
                  >
                    {doc.original_filename}
                  </button>
                </td>
                <td className="px-4 py-3 text-sm text-slate-600">{(doc.file_size / 1024).toFixed(1)} KB</td>
                <td className="px-4 py-3 text-sm text-slate-600">{doc.application}</td>
                <td className="px-4 py-3 text-sm text-slate-500">{new Date(doc.created_at).toLocaleDateString()}</td>
                <td className="px-4 py-3 text-right whitespace-nowrap">
                  <button
                    type="button"
                    onClick={() => handleDownload(doc)}
                    disabled={busyId === doc.id}
                    className="text-slate-600 hover:underline text-sm font-medium mr-3 disabled:opacity-50"
                  >
                    Download
                  </button>
                  <button onClick={() => handleDelete(doc.id)} className="text-red-600 hover:underline text-sm font-medium">Delete</button>
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      )}
    </div>
  );
}
