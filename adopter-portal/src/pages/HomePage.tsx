import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { fetchPets } from '../services/apiService'
import type { Pet } from '../types'
import { formatCurrency, formatPetAge } from '../utils/format'
import { Spinner, ErrorState } from '../components/UI'
import { CollarTagArt, Icon, PawMark } from '../components/Icons'
import type { IconName } from '../components/Icons'

const reasons: { icon: IconName; title: string; desc: string }[] = [
  { icon: 'heart', title: 'Loving homes', desc: 'Every pet is cared for while waiting for their forever family.' },
  { icon: 'shield', title: 'Health checked', desc: 'All our pets receive veterinary care and vaccinations.' },
  { icon: 'route', title: 'Supportive process', desc: 'We guide you through every step of the adoption journey.' },
]

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
      <section className="overflow-hidden bg-white">
        <div className="mx-auto grid max-w-7xl items-center gap-10 px-4 py-14 sm:px-6 sm:py-20 lg:grid-cols-[1.15fr_1fr] lg:px-8 lg:py-24">
          <div>
            <h1 className="max-w-xl font-display text-5xl font-extrabold leading-[1.02] tracking-tight text-primary-900 sm:text-6xl lg:text-7xl">
              Find your new best friend
            </h1>
            <p className="mt-6 max-w-lg text-lg leading-relaxed text-stone-600">
              Every pet deserves a loving home. Browse our adoptable pets and start
              your adoption journey today.
            </p>
            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
              <Link to="/pets" className="btn btn-accent btn-lg">
                Browse Pets
              </Link>
              <Link to="/register" className="btn btn-secondary btn-lg">
                Start Adopting
              </Link>
            </div>
          </div>
          <div className="mx-auto w-full max-w-md lg:max-w-none">
            <CollarTagArt className="h-auto w-full" />
          </div>
        </div>
      </section>

      {/* Featured pets */}
      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8 lg:py-20">
        <div className="mb-10 flex items-end justify-between gap-4">
          <h2 className="text-3xl font-bold text-primary-900 sm:text-4xl">Latest Pets</h2>
          <Link
            to="/pets"
            className="inline-flex items-center gap-1.5 font-semibold text-primary-700 transition-colors hover:text-primary-900"
          >
            View all
            <Icon name="arrowRight" className="h-4 w-4" />
          </Link>
        </div>

        {loading && <Spinner label="Loading featured pets..." />}
        {error && <ErrorState message="Could not load pets." />}
        {!loading && !error && featured.length === 0 && (
          <p className="py-8 text-center text-stone-500">
            No available pets right now. Check back soon!
          </p>
        )}

        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {featured.map((pet) => (
            <Link key={pet.id} to={`/pets/${pet.id}`} className="pet-card">
              <div className="relative h-64 bg-stone-200">
                {pet.primary_image?.image ? (
                  <img src={pet.primary_image.image} alt={pet.name} className="h-full w-full object-cover" />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-stone-400" aria-hidden="true">
                    <PawMark className="h-16 w-16" />
                  </div>
                )}
                <span className="absolute bottom-3 left-3 rounded-full bg-white/95 px-3 py-1 text-xs font-semibold capitalize text-primary-900 shadow-sm">
                  {pet.species}
                </span>
              </div>
              <div className="p-6">
                <h3 className="text-2xl font-bold text-primary-900">{pet.name}</h3>
                <p className="mt-1.5 text-stone-600">
                  {pet.breed || 'Mixed breed'} · {formatPetAge(pet.age_years)}
                </p>
                <div className="mt-5 flex items-center justify-between border-t border-dashed border-stone-300 pt-5">
                  <span className="rounded-md bg-accent-100 px-3 py-1.5 text-sm font-bold text-primary-900">
                    {pet.adoption_fee > 0 ? formatCurrency(pet.adoption_fee) : 'Free adoption'}
                  </span>
                  <Icon name="arrowRight" className="h-5 w-5 text-primary-600" />
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Why adopt */}
      <section className="border-t border-stone-200 bg-white py-16 lg:py-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <h2 className="mb-12 max-w-md text-3xl font-bold text-primary-900 sm:text-4xl">
            Why adopt from us?
          </h2>
          <div className="grid grid-cols-1 gap-10 sm:grid-cols-3 sm:gap-8">
            {reasons.map((item) => (
              <div key={item.title}>
                <div
                  className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary-50 text-primary-700 ring-1 ring-inset ring-primary-100"
                  aria-hidden="true"
                >
                  <Icon name={item.icon} className="h-6 w-6" />
                </div>
                <h3 className="mt-5 text-xl font-bold text-primary-900">{item.title}</h3>
                <p className="mt-2 leading-relaxed text-stone-600">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
