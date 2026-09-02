import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { fetchPets } from '../services/apiService'
import type { Pet } from '../types'
import { formatCurrency, capitalize } from '../utils/format'
import { Spinner, ErrorState } from '../components/UI'

const speciesOptions = ['dog', 'cat', 'bird', 'rabbit', 'other']
const sizeOptions = ['small', 'medium', 'large', 'extra_large']

export default function PetsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [pets, setPets] = useState<Pet[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [nextPage, setNextPage] = useState<string | null>(null)

  const species = searchParams.get('species') || ''
  const size = searchParams.get('size') || ''
  const search = searchParams.get('search') || ''

  useEffect(() => {
    setLoading(true)
    setError(false)
    const params: Record<string, string> = { status: 'available' }
    if (species) params.species = species
    if (size) params.size = size
    if (search) params.search = search
    fetchPets(params)
      .then((data) => {
        setPets(data.results || data)
        setNextPage(data.next || null)
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [species, size, search])

  const updateParam = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams)
    if (value) params.set(key, value)
    else params.delete(key)
    setSearchParams(params)
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <h1 className="text-3xl font-bold text-stone-800">Find Your New Friend</h1>
      <p className="mt-2 text-stone-500">Browse available pets looking for their forever home.</p>

      <div className="mt-6 bg-white rounded-lg border border-orange-100 p-4">
        <form
          className="flex flex-col sm:flex-row gap-4"
          onSubmit={(e) => { e.preventDefault(); const form = new FormData(e.currentTarget); updateParam('search', String(form.get('search') || '')); }}
        >
          <div className="flex-1">
            <label htmlFor="search" className="sr-only">Search pets</label>
            <input
              id="search"
              name="search"
              type="text"
              defaultValue={search}
              placeholder="Search by name or breed..."
              className="w-full px-3 py-2 border border-stone-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
            />
          </div>
          <select
            aria-label="Species"
            value={species}
            onChange={(e) => updateParam('species', e.target.value)}
            className="px-3 py-2 border border-stone-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
          >
            <option value="">All species</option>
            {speciesOptions.map((s) => (
              <option key={s} value={s}>{capitalize(s)}</option>
            ))}
          </select>
          <select
            aria-label="Size"
            value={size}
            onChange={(e) => updateParam('size', e.target.value)}
            className="px-3 py-2 border border-stone-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
          >
            <option value="">All sizes</option>
            {sizeOptions.map((s) => (
              <option key={s} value={s}>{capitalize(s)}</option>
            ))}
          </select>
          <button type="submit" className="px-4 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700">
            Search
          </button>
        </form>
      </div>

      {loading && <Spinner label="Loading pets..." />}
      {error && <ErrorState message="Could not load pets." />}

      {!loading && !error && pets.length === 0 && (
        <p className="text-center text-stone-500 py-12">No pets match your search.</p>
      )}

      {!loading && !error && pets.length > 0 && (
        <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {pets.map((pet) => (
            <Link
              key={pet.id}
              to={`/pets/${pet.id}`}
              className="bg-white rounded-lg shadow-sm border border-orange-100 overflow-hidden hover:shadow-md transition-shadow"
            >
              <div className="h-48 bg-stone-100">
                {pet.primary_image?.image ? (
                  <img src={pet.primary_image.image} alt={pet.name} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-5xl" aria-hidden="true">🐾</div>
                )}
              </div>
              <div className="p-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-stone-800">{pet.name}</h3>
                  <span className="text-xs px-2 py-0.5 bg-orange-100 text-orange-700 rounded-full">{capitalize(pet.species)}</span>
                </div>
                <p className="mt-1 text-sm text-stone-500">
                  {pet.breed || 'Mixed'} · {pet.age_months} mo · {capitalize(pet.gender)}
                </p>
                <p className="mt-1 text-sm text-stone-500">
                  {pet.size && capitalize(pet.size)}
                  {pet.is_vaccinated ? ' · Vaccinated' : ''}
                </p>
                <div className="mt-3 pt-3 border-t border-stone-100 font-medium text-orange-600 text-sm">
                  {pet.adoption_fee > 0 ? formatCurrency(pet.adoption_fee) : 'Free adoption'}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {!loading && !error && nextPage && (
        <div className="text-center mt-8">
          <Link
            to={`/pets?${searchParams.toString()}&page=2`}
            className="px-4 py-2 border border-orange-300 text-orange-600 rounded-md hover:bg-orange-50"
          >
            Next page
          </Link>
        </div>
      )}
    </div>
  )
}
