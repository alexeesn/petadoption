import { useEffect, useState } from 'react';
import { Card, Loading, ErrorMessage, Empty, Table } from '../components/UI';
import { PageHeader } from '../layouts/DashboardLayout';
import { reviewService } from '../services/apiService';
import type { Review } from '../types';

export default function ReviewsPage() {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    reviewService
      .list()
      .then((res) => setReviews(res.data.results))
      .catch(() => setError('Failed to load reviews.'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <PageHeader
        title="Reviews"
        subtitle="Post-adoption feedback. A review is created after an application reaches 'adoption_completed'. Staff can record internal notes here; these are not visible to adopters."
      />
      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorMessage message={error} />
      ) : reviews.length === 0 ? (
        <Card><Empty message="No reviews found." /></Card>
      ) : (
        <Card>
          <Table headers={['Application', 'Reviewer', 'Decision', 'Notes', 'Date']}>
            {reviews.map((r) => (
              <tr key={r.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-sm font-medium text-slate-900">{r.application}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{r.reviewer_email}</td>
                <td className="px-4 py-3 text-sm text-slate-600 capitalize">{r.decision}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{r.adopter_visible_notes}</td>
                <td className="px-4 py-3 text-sm text-slate-500">{new Date(r.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </Table>
        </Card>
      )}
    </div>
  );
}
