import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchPet } from '../services/apiService'
import type { Pet } from '../types'
import { formatCurrency, capitalize, formatPetAge, formatDate } from '../utils/format'
import { Spinner, ErrorState } from '../components/UI'
import { useAuth } from '../context/AuthContext'
import { Icon, PawMark } from '../components/Icons'

// ---------------------------------------------------------------------------
// Lightbox
// ---------------------------------------------------------------------------

interface LightboxProps {
  src: string
  alt: string
  onClose: () => void
}

/**
 * Full-viewport lightbox that shows one enlarged pet photo.
 *
 * Accessibility contract:
 *  - The backdrop is a <dialog> rendered via a portal so it sits above every
 *    other element in the z-stack and receives focus on open.
 *  - Escape key closes it (native <dialog> behaviour + our own handler for
 *    Safari < 15.4 where ESC on <dialog> is not guaranteed).
 *  - Clicking the semi-transparent backdrop area closes it; clicking the image
 *    itself does NOT close it (stopPropagation on the <img> wrapper).
 *  - A visible "Close" button with an aria-label provides a pointer/touch target.
 *  - The dialog carries role="dialog" + aria-label + aria-modal implicitly.
 */
function Lightbox({ src, alt, onClose }: LightboxProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)

  // Open the native dialog and focus it so Escape works without extra wiring.
  useEffect(() => {
    const el = dialogRef.current
    if (!el) return
    if (!el.open) el.showModal()

    // Fallback ESC listener for browsers that don't fire `cancel` on <dialog>.
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  // The <dialog> `cancel` event fires when the user presses Escape natively.
  const handleCancel = (e: React.SyntheticEvent<HTMLDialogElement>) => {
    e.preventDefault()
    onClose()
  }

  // Clicking the semi-transparent backdrop (the dialog element itself, outside
  // the inner content box) closes the lightbox.
  const handleBackdropClick = () => onClose()

  // Stop clicks that land *on* the image wrapper from propagating to the
  // backdrop handler above.
  const handleContentClick = (e: React.MouseEvent) => e.stopPropagation()

  return (
    <dialog
      ref={dialogRef}
      onCancel={handleCancel}
      onClick={handleBackdropClick}
      aria-label={`Enlarged photo: ${alt}`}
      aria-modal="true"
      className={[
        // Reset browser dialog chrome
        'bg-transparent p-0 border-0 outline-none',
        // Fill the viewport
        'fixed inset-0 m-0 max-h-none max-w-none w-screen h-screen',
        // Dark translucent backdrop (::backdrop does not work reliably in all
        // browsers alongside Tailwind purge, so we replicate it with a full-
        // screen bg on the dialog itself)
        'bg-primary-900/85 backdrop-blur-sm',
        // Flex centre the image
        'flex items-center justify-center',
        // Sit on top of everything else
        'z-50',
      ].join(' ')}
    >
      {/* Content wrapper — stops click events reaching the backdrop */}
      <div
        onClick={handleContentClick}
        className="relative flex max-h-[92dvh] max-w-[92dvw] items-center justify-center sm:max-h-[88dvh] sm:max-w-[88dvw]"
      >
        {/* Close button — top-right, always visible */}
        <button
          type="button"
          onClick={onClose}
          aria-label="Close photo"
          className={[
            'absolute -top-4 -right-4 z-10',
            'flex h-9 w-9 items-center justify-center rounded-full',
            'bg-white text-primary-900 shadow-lg',
            'transition-colors hover:bg-accent-400',
            'focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-primary-900',
          ].join(' ')}
        >
          <Icon name="close" className="h-5 w-5" />
        </button>

        {/* The enlarged image — preserves natural aspect ratio, fits viewport */}
        <img
          src={src}
          alt={alt}
          className="block max-h-[92dvh] max-w-[92dvw] rounded-lg object-contain shadow-2xl sm:max-h-[88dvh] sm:max-w-[88dvw]"
          draggable={false}
        />
      </div>
    </dialog>
  )
}

// ---------------------------------------------------------------------------
// Pet Detail Page
// ---------------------------------------------------------------------------

export default function PetDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuth()
  const [pet, setPet] = useState<Pet | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  // Index of the photo shown in the main gallery frame. Lets the adopter
  // view EVERY photo of the pet, not just the first one.
  const [activeImageIndex, setActiveImageIndex] = useState(0)
  // When non-null the lightbox is open showing this image URL.
  const [lightboxSrc, setLightboxSrc] = useState<string | null>(null)
  const [lightboxAlt, setLightboxAlt] = useState('')

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

  const openLightbox = (src: string, alt: string) => {
    setLightboxSrc(src)
    setLightboxAlt(alt)
  }
  const closeLightbox = () => setLightboxSrc(null)

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
      <Link to="/pets" className="inline-flex items-center gap-1.5 text-sm font-medium text-primary-700 transition-colors hover:text-primary-900">
        <Icon name="arrowLeft" className="h-4 w-4" />
        Back to pets
      </Link>

      <div className="mt-6 grid grid-cols-1 gap-10 lg:grid-cols-[1.05fr_1fr]">
        <div data-testid="pet-gallery">
          {/* Main gallery frame — clicking the photo opens the lightbox */}
          <div data-testid="pet-gallery-main" className="relative aspect-square overflow-hidden rounded-xl border border-stone-200 bg-stone-200">
            {activeImage?.image ? (
              <button
                type="button"
                aria-label={`View enlarged photo of ${pet.name}`}
                onClick={() => openLightbox(activeImage.image, activeImage.caption || pet.name)}
                className="group block h-full w-full cursor-zoom-in focus:outline-none focus-visible:ring-4 focus-visible:ring-primary-500 focus-visible:ring-offset-2"
              >
                <img
                  src={activeImage.image}
                  alt={activeImage.caption || pet.name}
                  className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
                />
                {/* Subtle expand hint on hover */}
                <span
                  className="absolute bottom-12 right-3 flex items-center gap-1 rounded-full bg-primary-900/75 px-2.5 py-1 text-xs font-medium text-white opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
                  aria-hidden="true"
                >
                  <Icon name="expand" className="h-3.5 w-3.5" />
                  Enlarge
                </span>
              </button>
            ) : (
              <div className="flex h-full w-full items-center justify-center text-stone-400" aria-hidden="true">
                <PawMark className="h-24 w-24" />
              </div>
            )}
            {hasMultiple && (
              <>
                <button
                  type="button"
                  onClick={() => setActiveImageIndex((activeIndex - 1 + images.length) % images.length)}
                  aria-label="Previous photo"
                  className="absolute left-3 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full bg-white/95 text-primary-900 shadow-md transition-colors hover:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  <Icon name="chevronLeft" className="h-5 w-5" />
                </button>
                <button
                  type="button"
                  onClick={() => setActiveImageIndex((activeIndex + 1) % images.length)}
                  aria-label="Next photo"
                  className="absolute right-3 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full bg-white/95 text-primary-900 shadow-md transition-colors hover:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  <Icon name="chevronRight" className="h-5 w-5" />
                </button>
                <span data-testid="pet-gallery-counter" className="absolute bottom-3 right-3 rounded-full bg-primary-900/80 px-2.5 py-0.5 text-xs font-medium text-white">
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
                  className={`h-20 w-full rounded-md border-2 object-cover transition-opacity focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                    idx === activeIndex ? 'border-accent-400 opacity-100' : 'border-transparent opacity-70 hover:opacity-100'
                  }`}
                >
                  <img src={img.image} alt={img.caption || `${pet.name} photo ${idx + 1}`} className="h-full w-full object-cover rounded-md pointer-events-none" />
                </button>
              ))}
            </div>
          )}
        </div>

        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-4xl font-extrabold text-primary-900 sm:text-5xl">{pet.name}</h1>
            <span className="rounded-full bg-accent-100 px-3 py-1 text-sm font-semibold capitalize text-primary-900 ring-1 ring-inset ring-accent-300">
              {pet.status.replace(/_/g, ' ')}
            </span>
          </div>
          <p className="mt-3 text-lg text-stone-600">
            {capitalize(pet.species)} · {pet.breed || 'Mixed'} · {formatPetAge(pet.age_years, pet.age_months)}
          </p>

          <div className="mt-7 space-y-3 rounded-xl border border-stone-200 bg-white p-6 shadow-sm">
            <InfoRow label="Gender" value={capitalize(pet.gender)} />
            <InfoRow label="Size" value={pet.size ? capitalize(pet.size) : '—'} />
            {pet.weight_kg && <InfoRow label="Weight" value={`${pet.weight_kg} kg`} />}
            <InfoRow label="Color" value={pet.color || '—'} />
            <InfoRow label="At the center since" value={pet.arrival_date ? formatDate(pet.arrival_date) : '—'} />
          </div>

          {pet.description && (
            <div className="mt-8">
              <h2 className="text-xl font-bold text-primary-900">About {pet.name}</h2>
              <p className="mt-2 max-w-prose leading-relaxed text-stone-600 whitespace-pre-line">{pet.description}</p>
            </div>
          )}

          <PetHealthInfo pet={pet} />

          <div className="mt-9">
            {user ? (
              <Link
                to={`/applications/new?pet=${pet.id}`}
                className="btn btn-accent btn-lg"
              >
                Apply to Adopt {pet.name}
              </Link>
            ) : (
              <Link
                to={`/register?pet=${pet.id}`}
                className="btn btn-accent btn-lg"
              >
                Sign up to Adopt {pet.name}
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* Lightbox — rendered when a photo is clicked */}
      {lightboxSrc && (
        <Lightbox
          src={lightboxSrc}
          alt={lightboxAlt}
          onClose={closeLightbox}
        />
      )}
    </div>
  )
}

/**
 * Health Information for the Pet Details page.
 *
 * Everything shown here comes from the pet detail API: the vaccination and
 * spayed/neutered flags are part of the pet record, and `health_summary` is
 * built by the backend from the pet's existing health records. Staff-only
 * fields (internal notes, treatment details, veterinarian information) are
 * never sent to the adopter portal.
 *
 * Exported because it is driven purely by the `pet` prop.
 */
export function PetHealthInfo({ pet }: { pet: Pet }) {
  const health = pet.health_summary
  const vaccinationStatus = health?.vaccination_status ?? null
  const healthStatus = health?.health_status?.trim() || ''
  const lastCheckup = health?.last_checkup_date ? formatDate(health.last_checkup_date) : ''
  const nextCheckup = health?.next_checkup_date ? formatDate(health.next_checkup_date) : ''
  // No health record and no vaccination records yet: only the basic vaccinated
  // and spayed/neutered flags on the pet record are known.
  const hasNoHealthData = !health?.has_health_record && !vaccinationStatus

  return (
    <section className="mt-6 rounded-xl border border-stone-200 bg-white p-6 shadow-sm" data-testid="pet-health-info">
      <h2 className="text-xl font-bold text-primary-900">Health Information</h2>
      <div className="mt-4 space-y-3">
        <InfoRow label="Vaccination" value={pet.is_vaccinated ? 'Vaccinated' : 'Not vaccinated'} />
        {vaccinationStatus && (
          <InfoRow
            label="Vaccination status"
            value={VACCINATION_STATUS_LABELS[vaccinationStatus] ?? capitalize(vaccinationStatus)}
          />
        )}
        <InfoRow label="Spayed/Neutered" value={pet.is_neutered ? 'Yes' : 'No'} />
        {healthStatus && <InfoRow label="Health status" value={healthStatus} />}
        {lastCheckup && <InfoRow label="Last checkup" value={lastCheckup} />}
        {nextCheckup && <InfoRow label="Next checkup" value={nextCheckup} />}
      </div>
      {hasNoHealthData && (
        <p className="mt-4 text-sm text-stone-500" data-testid="pet-health-empty">
          No health information available yet.
        </p>
      )}
    </section>
  )
}

// Vaccination status codes computed by the backend health records.
const VACCINATION_STATUS_LABELS: Record<string, string> = {
  up_to_date: 'Up to date',
  due_soon: 'Due soon',
  overdue: 'Overdue',
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="leader-row">
      <span className="text-stone-500">{label}</span>
      <span className="text-right font-semibold text-primary-900 whitespace-pre-line">{value}</span>
    </div>
  )
}
