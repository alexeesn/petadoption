import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { fetchPets } from '../services/apiService'
import type { Pet } from '../types'
import { capitalize } from '../utils/format'
import { Spinner, ErrorState } from '../components/UI'
import { Icon } from '../components/Icons'
import PetCard from '../components/PetCard'

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
  const page = Math.max(1, Number(searchParams.get('page')) || 1)

  useEffect(() => {
    setLoading(true)
    setError(false)
    const params: Record<string, string> = { status: 'available', page: String(page) }
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
  }, [species, size, search, page])

  const updateParam = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams)
    if (value) params.set(key, value)
    else params.delete(key)
    params.delete('page')
    setSearchParams(params)
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8 lg:py-12">
      <p className="section-label mb-3">Meet your next companion</p>
      <h1 className="text-4xl font-bold text-primary-900 sm:text-5xl">Find a Pet</h1>
      <p className="mt-3 max-w-xl text-lg text-stone-600">Browse available pets looking for their forever home.</p>

      <div className="mt-8 rounded-xl border border-stone-200 bg-white p-2 shadow-sm">
        <form
          className="flex flex-col gap-2 sm:flex-row sm:items-center"
          onSubmit={(e) => { e.preventDefault(); const form = new FormData(e.currentTarget); updateParam('search', String(form.get('search') || '')); }}
        >
          <div className="relative flex-1">
            <label htmlFor="search" className="sr-only">Search pets</label>
            <Icon name="search" className="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-stone-400" />
            <input
              id="search"
              name="search"
              type="text"
              defaultValue={search}
              placeholder="Search by name or breed..."
              className="field-input border-transparent pl-11 focus:border-primary-500"
            />
          </div>
          <select
            aria-label="Species"
            value={species}
            onChange={(e) => updateParam('species', e.target.value)}
            className="field-input border-transparent bg-stone-100 sm:w-40"
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
            className="field-input border-transparent bg-stone-100 sm:w-40"
          >
            <option value="">All sizes</option>
            {sizeOptions.map((s) => (
              <option key={s} value={s}>{capitalize(s)}</option>
            ))}
          </select>
          <button type="submit" className="btn btn-primary px-6 py-3">
            Search
          </button>
        </form>
      </div>

      {loading && <Spinner label="Loading pets..." />}
      {error && <ErrorState message="Could not load pets." />}

      {!loading && !error && pets.length === 0 && (
        <p className="py-16 text-center text-stone-500">No pets match your search.</p>
      )}

      {!loading && !error && pets.length > 0 && (
        <div className="mt-10 grid grid-cols-1 gap-7 sm:grid-cols-2 lg:grid-cols-3">
          {pets.map(pet => <PetCard key={pet.id} pet={pet} />)}
        </div>
      )}

      {!loading && !error && (nextPage || page > 1) && (
        <div className="mt-10 flex items-center justify-center gap-4">
          {page > 1 && <Link to={`/pets?${new URLSearchParams({ ...Object.fromEntries(searchParams), page: String(page - 1) })}`} className="btn btn-secondary">Previous page</Link>}
          <span className="text-sm text-stone-500">Page {page}</span>
          {nextPage && (
          <Link
            to={`/pets?${new URLSearchParams({ ...Object.fromEntries(searchParams), page: String(page + 1) })}`}
            className="btn btn-secondary"
          >
            Next page
          </Link>
          )}
        </div>
      )}
    </div>
  )
}
