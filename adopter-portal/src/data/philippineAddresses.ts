/**
 * Philippine Standard Geographic Code (PSGC) Dataset
 *
 * Source: Philippine Statistics Authority (PSA) PSGC via isaacdarcilla/philippine-addresses
 * Retrieval Date: 2026-10-20
 *
 * Hierarchy:
 *   Region -> Province (when applicable) -> City/Municipality -> Barangay
 *
 * Note on NCR:
 *   National Capital Region (NCR) has no province level. Cities and municipalities
 *   are direct children of the region.
 */
import rawData from './philippineAddresses.json'

export interface Barangay {
  code: string
  name: string
}

export interface CityMunicipality {
  code: string
  name: string
  barangays: Barangay[]
}

export interface Province {
  code: string
  name: string
  cities: CityMunicipality[]
}

export interface Region {
  code: string
  name: string
  provinces?: Province[]
  cities?: CityMunicipality[]
}

export const philippineAddresses: Region[] = rawData as unknown as Region[]
export default philippineAddresses
