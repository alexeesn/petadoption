/**
 * PhilippineAddressSelector
 *
 * Cascading dropdowns for Philippine addresses following the PSGC hierarchy:
 *   Region → Province → City/Municipality → Barangay
 *
 * NCR (National Capital Region) has no province level — the province
 * dropdown is hidden for NCR and the city/municipality options are taken
 * directly from the region's `cities` array.
 *
 * Props:
 *   value    – current address selections (controlled)
 *   onChange – called whenever any level changes; receives the complete updated value
 *   disabled – disables all selectors (e.g. while saving)
 *   errors   – field-level error messages keyed by field name
 */
import { useMemo } from 'react'
import philippineAddresses, { type Region, type Province, type CityMunicipality } from '../data/philippineAddresses'
import { FieldError } from './UI'

export interface PhilippineAddress {
  region: string      // Region name
  state: string       // Province name (blank for NCR)
  city: string        // City or municipality name
  barangay: string    // Barangay name
}

export const EMPTY_PH_ADDRESS: PhilippineAddress = {
  region: '',
  state: '',
  city: '',
  barangay: '',
}

interface Props {
  value: PhilippineAddress
  onChange: (updated: PhilippineAddress) => void
  disabled?: boolean
  errors?: Record<string, string>
}

const SELECT_CLS = 'field-input'

export default function PhilippineAddressSelector({ value, onChange, disabled, errors = {} }: Props) {
  // ── derive objects from names ──────────────────────────────────────────────
  const selectedRegion: Region | undefined = useMemo(
    () => philippineAddresses.find((r) => r.name === value.region),
    [value.region]
  )

  // NCR and similar regions with no provinces: use region.cities directly
  const isNoProv = (selectedRegion?.provinces?.length ?? 0) === 0

  const selectedProvince: Province | undefined = useMemo(() => {
    if (!selectedRegion || isNoProv) return undefined
    return selectedRegion.provinces?.find((p) => p.name === value.state)
  }, [selectedRegion, isNoProv, value.state])

  // Cities come either from province (normal) or region directly (NCR)
  const availableCities: CityMunicipality[] = useMemo(() => {
    if (!selectedRegion) return []
    if (isNoProv) return selectedRegion.cities ?? []
    if (!selectedProvince) return []
    return selectedProvince.cities
  }, [selectedRegion, isNoProv, selectedProvince])

  const selectedCity: CityMunicipality | undefined = useMemo(
    () => availableCities.find((c) => c.name === value.city),
    [availableCities, value.city]
  )

  // ── event handlers ─────────────────────────────────────────────────────────
  function handleRegionChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const regionName = e.target.value
    // Reset all child levels
    onChange({ region: regionName, state: '', city: '', barangay: '' })
  }

  function handleProvinceChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const provName = e.target.value
    onChange({ ...value, state: provName, city: '', barangay: '' })
  }

  function handleCityChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const cityName = e.target.value
    onChange({ ...value, city: cityName, barangay: '' })
  }

  function handleBarangayChange(e: React.ChangeEvent<HTMLSelectElement>) {
    onChange({ ...value, barangay: e.target.value })
  }

  // ── render ─────────────────────────────────────────────────────────────────
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {/* ── Region ── */}
      <div className="sm:col-span-2">
        <label htmlFor="ph_region" className="field-label mb-1">
          Region <span className="text-red-600" aria-hidden="true">*</span>
        </label>
        <select
          id="ph_region"
          value={value.region}
          onChange={handleRegionChange}
          disabled={disabled}
          required
          aria-invalid={errors.region ? true : undefined}
          aria-describedby={errors.region ? 'ph_region_error' : undefined}
          className={SELECT_CLS}
        >
          <option value="">— Select Region —</option>
          {philippineAddresses.map((r) => (
            <option key={r.code} value={r.name}>{r.name}</option>
          ))}
        </select>
        <FieldError message={errors.region} id="ph_region_error" />
      </div>

      {/* ── Province (hidden for NCR/no-province regions) ── */}
      {!isNoProv && (
        <div>
          <label htmlFor="ph_province" className="field-label mb-1">
            Province
            {/* Province is not required for NCR — no asterisk */}
          </label>
          <select
            id="ph_province"
            value={value.state}
            onChange={handleProvinceChange}
            disabled={disabled || !selectedRegion}
            aria-invalid={errors.state ? true : undefined}
            aria-describedby={errors.state ? 'ph_province_error' : undefined}
            className={SELECT_CLS}
          >
            <option value="">— Select Province —</option>
            {(selectedRegion?.provinces ?? []).map((p) => (
              <option key={p.code} value={p.name}>{p.name}</option>
            ))}
          </select>
          <FieldError message={errors.state} id="ph_province_error" />
        </div>
      )}

      {/* ── City / Municipality ── */}
      <div>
        <label htmlFor="ph_city" className="field-label mb-1">
          City / Municipality <span className="text-red-600" aria-hidden="true">*</span>
        </label>
        <select
          id="ph_city"
          value={value.city}
          onChange={handleCityChange}
          disabled={disabled || (!isNoProv && !selectedProvince) || (!selectedRegion)}
          required
          aria-invalid={errors.city ? true : undefined}
          aria-describedby={errors.city ? 'ph_city_error' : undefined}
          className={SELECT_CLS}
        >
          <option value="">— Select City / Municipality —</option>
          {availableCities.map((c) => (
            <option key={c.code} value={c.name}>{c.name}</option>
          ))}
        </select>
        {availableCities.length === 0 && selectedRegion && (isNoProv || selectedProvince) && (
          <p className="mt-1 text-xs text-stone-400 italic">
            No city / municipality data for the selected area.
          </p>
        )}
        <FieldError message={errors.city} id="ph_city_error" />
      </div>

      {/* ── Barangay ── */}
      <div>
        <label htmlFor="ph_barangay" className="field-label mb-1">
          Barangay <span className="text-red-600" aria-hidden="true">*</span>
        </label>
        <select
          id="ph_barangay"
          value={value.barangay}
          onChange={handleBarangayChange}
          disabled={disabled || !selectedCity}
          required
          aria-invalid={errors.barangay ? true : undefined}
          aria-describedby={errors.barangay ? 'ph_barangay_error' : undefined}
          className={SELECT_CLS}
        >
          <option value="">— Select Barangay —</option>
          {(selectedCity?.barangays ?? []).map((b) => (
            <option key={b.code} value={b.name}>{b.name}</option>
          ))}
        </select>
        {selectedCity && selectedCity.barangays.length === 0 && (
          <p className="mt-1 text-xs text-stone-400 italic">
            No barangay data for the selected city / municipality.
          </p>
        )}
        <FieldError message={errors.barangay} id="ph_barangay_error" />
      </div>
    </div>
  )
}
