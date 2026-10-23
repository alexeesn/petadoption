import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { fetchPets } from '../services/apiService'
import type { Pet } from '../types'
import { formatPetLabel, capitalize, formatPetAge } from '../utils/format'
import { Spinner, ErrorState } from '../components/UI'
import PetCard from '../components/PetCard'
import { Icon } from '../components/Icons'
import PetPhoto from '../components/PetPhoto'

export default function HomePage() {
  const [featured, setFeatured] = useState<Pet[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  useEffect(() => {
    let active = true
    fetchPets({ status: 'available', ordering: '-created_at' })
      .then(data => { if (active) setFeatured((data.results || data).filter((pet: Pet) => pet.status === 'available').slice(0, 3)) })
      .catch(() => { if (active) setError(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])
  const heroPet = featured[0]
  return <div>
    <section className="home-hero mx-auto max-w-7xl px-4 pb-10 pt-6 sm:px-6 lg:px-8 lg:pb-14 lg:pt-9">
      <div className="hero-bento">
        <div className="hero-copy-card">
          <p className="hero-eyebrow"><span aria-hidden="true" />A better beginning starts here</p>
          <h1 className="hero-title">A little love.<br /><span>A whole new life.</span></h1>
          <p className="hero-description">Find a companion who feels like home. Meet our pets, get to know their stories, and take the first step together.</p>
          <div className="mt-8 flex flex-wrap items-center gap-3"><Link to="/pets" className="btn btn-primary btn-lg">Find a Pet<Icon name="arrowRight" className="h-4 w-4" /></Link><a href="#how-it-works" className="btn btn-outline">How it works<Icon name="chevronRight" className="h-4 w-4" /></a></div>
          <div className="hero-care-note"><span className="hero-note-icon"><Icon name="shield" className="h-5 w-5" /></span><div><p className="text-sm font-semibold text-stone-800">A real connection. A thoughtful process.</p><p className="mt-1 text-xs text-stone-600">Our team is here to guide every step.</p></div></div>
        </div>
        <div className="spotlight-card">
          <div className="spotlight-photo"><PetPhoto src={heroPet?.primary_image?.image} name={formatPetLabel(heroPet?.name) || 'our pets'} eager /><span className="spotlight-label"><Icon name="heart" className="h-3.5 w-3.5" />{heroPet ? 'Your next hello' : 'Room for a new friend'}</span></div>
          <div className="spotlight-details"><div className="min-w-0"><p className="section-label">{heroPet ? 'Waiting to meet you' : 'Start your adoption journey'}</p><p className="pet-name mt-1 text-2xl font-bold text-stone-900">{formatPetLabel(heroPet?.name) || 'Find a connection'}</p>{heroPet && <p className="mt-1 text-sm text-stone-600">{capitalize(heroPet.species)} / {formatPetAge(heroPet.age_years, heroPet.age_months)}</p>}</div><Link to={heroPet ? `/pets/${heroPet.id}` : '/pets'} aria-label={heroPet ? `Meet ${heroPet.name}` : 'Browse pets'} className="spotlight-link"><Icon name="arrowRight" className="h-5 w-5" /></Link></div>
        </div>
      </div>
    </section>

    <section className="latest-pets-section border-y border-stone-200" id="latest-pets">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8 lg:py-16">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4"><div><p className="section-label">Ready for a new chapter</p><h2 className="mt-2 text-3xl font-bold text-stone-900 sm:text-4xl">Latest Pets</h2><p className="mt-3 text-sm text-stone-600">A few friendly faces. Many more stories to discover.</p></div><Link to="/pets" className="btn btn-secondary">Meet all our pets<Icon name="arrowRight" className="h-4 w-4"/></Link></div>
        {loading && <Spinner label="Loading featured pets..." />}
        {error && <ErrorState message="Could not load pets." />}
        {!loading && !error && featured.length === 0 && <p className="py-8 text-stone-500">No available pets right now. Check back soon!</p>}
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3" data-testid="latest-pets">
          {!loading && !error && featured.map(pet => <PetCard key={pet.id} pet={pet} />)}
        </div>
      </div>
    </section>

    <section id="how-it-works" className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8 lg:py-20">
      <div className="mb-10 max-w-lg"><p className="section-label">The adoption journey</p><h2 className="mt-3 text-3xl font-bold leading-tight text-stone-900 sm:text-4xl">Good things start<br />with a connection.</h2></div>
      <div className="grid gap-4 sm:grid-cols-3">{[
        ['01', 'Find your companion', 'Browse the pets, read their profiles, and find someone you would love to meet.'],
        ['02', 'Tell us about yourself', 'Complete your profile and application. Our team will review the information you submit.'],
        ['03', 'Meet and welcome home', 'Once approved, request your visit. Staff will guide you through the onsite steps and physical handover.'],
      ].map(([number,title,description]) => <div key={number} className="journey-step"><span className="journey-number">{number}</span><h3 className="mt-5 text-xl font-bold text-primary-900">{title}</h3><p className="mt-3 text-sm leading-7 text-stone-600">{description}</p></div>)}</div>
    </section>
  </div>
}
