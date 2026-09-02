import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { fetchPets } from '../services/apiService'
import type { Pet } from '../types'
import { formatCurrency } from '../utils/format'
import { Spinner, ErrorState } from '../components/UI'

export default function HomePage() {
  const [featured, setFeatured] = useState<Pet[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    fetchPets({ status: 'available', page_size: '3' })
      .then((data) => setFeatured(data.results || data))
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      {/* Hero */}
      <section className="bg-orange-600 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-20">
          <div className="max-w-2xl">
            <h1 className="text-4xl sm:text-5xl font-bold leading-tight">
              Find your new best friend
            </h1>
            <p className="mt-4 text-lg text-orange-100">
              Every pet deserves a loving home. Browse our adoptable pets and start
              your adoption journey today.
            </p>
            <div className="mt-8 flex flex-col sm:flex-row gap-4">
              <Link
                to="/pets"
                className="inline-flex items-center justify-center px-6 py-3 bg-white text-orange-700 font-semibold rounded-md hover:bg-orange-50"
              >
                Browse Pets
              </Link>
              <Link
                to="/register"
                className="inline-flex items-center justify-center px-6 py-3 bg-orange-700 text-white font-semibold rounded-md hover:bg-orange-800"
              >
                Start Adopting
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Featured pets */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-stone-800">Featured Pets</h2>
          <Link to="/pets" className="text-orange-600 font-medium hover:underline">
            View all →
          </Link>
        </div>

        {loading && <Spinner label="Loading featured pets..." />}
        {error && <ErrorState message="Could not load pets." />}
        {!loading && !error && featured.length === 0 && (
          <p className="text-stone-500 text-center py-8">
            No available pets right now. Check back soon!
          </p>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {featured.map((pet) => (
            <Link
              key={pet.id}
              to={`/pets/${pet.id}`}
              className="bg-white rounded-lg shadow-sm border border-orange-100 overflow-hidden hover:shadow-md transition-shadow"
            >
              <div className="h-48 bg-stone-100">
                {pet.primary_image?.image ? (
                  <img
                    src={pet.primary_image.image}
                    alt={pet.name}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-5xl" aria-hidden="true">
                    🐾
                  </div>
                )}
              </div>
              <div className="p-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-stone-800">{pet.name}</h3>
                  <span className="text-xs text-orange-600">{pet.species}</span>
                </div>
                <p className="mt-1 text-sm text-stone-500">
                  {pet.breed || 'Mixed breed'} · {pet.age_months} mo
                </p>
                <div className="mt-3 pt-3 border-t border-stone-100 flex items-center justify-between">
                  <span className="text-sm font-medium text-orange-600">
                    {pet.adoption_fee > 0 ? formatCurrency(pet.adoption_fee) : 'Free adoption'}
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Why adopt */}
      <section className="bg-white border-t border-orange-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <h2 className="text-2xl font-bold text-stone-800 text-center mb-8">
            Why adopt from us?
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            {[
              { icon: '❤️', title: 'Loving homes', desc: 'Every pet is cared for while waiting for their forever family.' },
              { icon: '🩺', title: 'Health checked', desc: 'All our pets receive veterinary care and vaccinations.' },
              { icon: '🤝', title: 'Supportive process', desc: 'We guide you through every step of the adoption journey.' },
            ].map((item) => (
              <div key={item.title} className="text-center p-6 rounded-lg bg-orange-50 border border-orange-100">
                <div className="text-3xl mb-3" aria-hidden="true">{item.icon}</div>
                <h3 className="font-semibold text-stone-800">{item.title}</h3>
                <p className="mt-2 text-sm text-stone-600">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
