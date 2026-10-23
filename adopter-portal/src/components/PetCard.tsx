import { Link } from 'react-router-dom'
import type { Pet } from '../types'
import { capitalize, formatPetAge, formatPetLabel } from '../utils/format'
import { Icon } from './Icons'
import PetPhoto from './PetPhoto'

export default function PetCard({ pet }: { pet: Pet }) {
  const name = formatPetLabel(pet.name)
  return <Link to={`/pets/${pet.id}`} className="pet-card group">
    <div className="relative aspect-[4/3] overflow-hidden">
      <PetPhoto src={pet.primary_image?.image} name={name} className="transition-transform duration-300 group-hover:scale-[1.025]" />
      <span className="pet-species-label">{capitalize(pet.species)}</span>
    </div>
    <div className="p-5">
      <div className="mb-2 flex items-start justify-between gap-3"><h3 className="pet-name text-xl font-bold text-stone-900">{name}</h3><span className="pet-availability"><span aria-hidden="true" />{capitalize(pet.status)}</span></div>
      <p className="text-sm text-stone-600">{formatPetLabel(pet.breed) || 'Breed not recorded'}</p>
      <p className="mt-1 text-xs text-stone-500">{[formatPetAge(pet.age_years, pet.age_months), capitalize(pet.gender), pet.weight_kg != null && `${pet.weight_kg} kg`].filter(Boolean).join(' / ')}</p>
      <div className="mt-5 flex items-center justify-between border-t border-stone-200 pt-4 text-sm font-semibold text-primary-700"><span>Get to know {name}</span><Icon name="arrowRight" className="h-4 w-4 transition-transform group-hover:translate-x-1" /></div>
    </div>
  </Link>
}
