import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchPet } from '../services/apiService'
import type { Pet } from '../types'
import { formatCurrency, capitalize } from '../utils/format'
import { Spinner, ErrorState } from '../components/UI'
import { useAuth } from '../context/AuthContext'

export default function PetDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuth()
  const [pet, setPet] = useState<Pet | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  // Index of the photo shown in the main gallery frame. Lets the adopter
  // view EVERY photo of the pet, not just the first one.
  const [activeImageIndex, setActiveImageIndex] = useState(0)

  useEffect(() => {
    if (!id) return
    setActiveImageIndex(0)
    fetchPet(id)
      .then(setPet)
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <Spinner label="Loading pet..." />
  if (error) return <ErrorState message="Could not load this pet." />
  if (!pet) return null

  const images = pet.images ?? []
  // Guard against an out-of-range index so a stale index can never blank the gallery.
  const activeIndex = Math.min(activeImageIndex, Math.max(images.length - 1, 0))
  const activeImage = images[activeIndex]
  const hasMultiple = images.length > 1

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <Link to="/pets" className="text-orange-600 text-sm font-medium hover:underline">
        ← Back to pets
      </Link>

      <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div data-testid="pet-gallery">
          <div data-testid="pet-gallery-main" className="relative bg-stone-100 rounded-lg overflow-hidden aspect-square">
            {activeImage?.image ? (
              <img
                src={activeImage.image}
                alt={activeImage.caption || pet.name}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-7xl" aria-hidden="true">🐾</div>
            )}
            {hasMultiple && (
              <>
                <button
                  type="button"
                  onClick={() => setActiveImageIndex((activeIndex - 1 + images.length) % images.length)}
                  aria-label="Previous photo"
                  className="absolute left-2 top-1/2 -translate-y-1/2 h-9 w-9 rounded-full bg-white/90 text-stone-700 shadow flex items-center justify-center hover:bg-white focus:outline-none focus:ring-2 focus:ring-orange-500"
                >
                  ‹
                </button>
                <button
                  type="button"
                  onClick={() => setActiveImageIndex((activeIndex + 1) % images.length)}
                  aria-label="Next photo"
                  className="absolute right-2 top-1/2 -translate-y-1/2 h-9 w-9 rounded-full bg-white/90 text-stone-700 shadow flex items-center justify-center hover:bg-white focus:outline-none focus:ring-2 focus:ring-orange-500"
                >
                  ›
                </button>
                <span data-testid="pet-gallery-counter" className="absolute bottom-2 right-2 px-2 py-0.5 rounded-full bg-stone-900/70 text-white text-xs">
                  {activeIndex + 1} / {images.length}
                </span>
              </>
            )}
          </div>
          {hasMultiple && (
            <div data-testid="pet-gallery-thumbs" className="mt-3 grid grid-cols-4 sm:grid-cols-5 gap-2">
              {images.map((img, idx) => (
                <button
                  key={img.id}
                  type="button"
                  onClick={() => setActiveImageIndex(idx)}
                  aria-label={`View photo ${idx + 1} of ${pet.name}`}
                  aria-current={idx === activeIndex}
                  className={`h-20 w-full object-cover rounded-md border-2 transition-opacity focus:outline-none focus:ring-2 focus:ring-orange-500 ${
                    idx === activeIndex ? 'border-orange-500 opacity-100' : 'border-transparent opacity-80 hover:opacity-100'
                  }`}
                >
                  <img src={img.image} alt={img.caption || `${pet.name} photo ${idx + 1}`} className="h-full w-full object-cover rounded-md pointer-events-none" />
                </button>
              ))}
            </div>
          )}
        </div>

        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold text-stone-800">{pet.name}</h1>
            <span className="px-3 py-1 bg-orange-100 text-orange-700 rounded-full text-sm capitalize">
              {pet.status.replace(/_/g, ' ')}
            </span>
          </div>
          <p className="mt-2 text-stone-500">
            {capitalize(pet.species)} · {pet.breed || 'Mixed'} · {pet.age_months} months
          </p>

          <div className="mt-6 space-y-3 border-t border-stone-100 pt-6">
            <InfoRow label="Gender" value={capitalize(pet.gender)} />
            <InfoRow label="Size" value={pet.size ? capitalize(pet.size) : '—'} />
            {pet.weight_kg && <InfoRow label="Weight" value={`${pet.weight_kg} kg`} />}
            <InfoRow label="Color" value={pet.color || '—'} />
            <InfoRow label="Vaccinated" value={pet.is_vaccinated ? 'Yes' : 'No'} />
            <InfoRow label="Neutered" value={pet.is_neutered ? 'Yes' : 'No'} />
            <InfoRow label="Adoption fee" value={pet.adoption_fee > 0 ? formatCurrency(pet.adoption_fee) : 'Free'} />
          </div>

          {pet.description && (
            <div className="mt-6 border-t border-stone-100 pt-6">
              <h2 className="font-semibold text-stone-800">About {pet.name}</h2>
              <p className="mt-2 text-stone-600 whitespace-pre-line">{pet.description}</p>
            </div>
          )}

          <div className="mt-8">
            {user ? (
              <Link
                to={`/applications/new?pet=${pet.id}`}
                className="inline-flex px-6 py-3 bg-orange-600 text-white font-semibold rounded-md hover:bg-orange-700"
              >
                Apply to Adopt {pet.name}
              </Link>
            ) : (
              <Link
                to={`/register?pet=${pet.id}`}
                className="inline-flex px-6 py-3 bg-orange-600 text-white font-semibold rounded-md hover:bg-orange-700"
              >
                Sign up to Adopt {pet.name}
              </Link>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-stone-500">{label}</span>
      <span className="font-medium text-stone-700">{value}</span>
    </div>
  )
}
