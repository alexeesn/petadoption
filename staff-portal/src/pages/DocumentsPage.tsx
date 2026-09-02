import { useEffect, useState } from 'react';
import { Card, Loading, ErrorMessage, Empty, Table } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { documentService } from '../services/apiService';
import type { Document } from '../types';

export default function DocumentsPage() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

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
                  <a href={documentService.downloadUrl(doc.id)} className="text-indigo-600 hover:underline">{doc.original_filename}</a>
                </td>
                <td className="px-4 py-3 text-sm text-slate-600">{(doc.file_size / 1024).toFixed(1)} KB</td>
                <td className="px-4 py-3 text-sm text-slate-600">{doc.application}</td>
                <td className="px-4 py-3 text-sm text-slate-500">{new Date(doc.created_at).toLocaleDateString()}</td>
                <td className="px-4 py-3 text-right">
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
