import json
import os
import urllib.request

def build_philippine_addresses():
    base = 'https://raw.githubusercontent.com/isaacdarcilla/philippine-addresses/master/'
    print('Downloading PSGC dataset from isaacdarcilla/philippine-addresses...')
    regions = json.loads(urllib.request.urlopen(base + 'region.json').read().decode('utf-8'))
    provinces = json.loads(urllib.request.urlopen(base + 'province.json').read().decode('utf-8'))
    cities = json.loads(urllib.request.urlopen(base + 'city.json').read().decode('utf-8'))
    barangays = json.loads(urllib.request.urlopen(base + 'barangay.json').read().decode('utf-8'))

    # Group barangays by city_code
    b_by_city = {}
    for b in barangays:
        c_code = b['city_code']
        if c_code not in b_by_city:
            b_by_city[c_code] = []
        b_by_city[c_code].append({'code': b['brgy_code'], 'name': b['brgy_name']})

    # Sort barangays by name
    for c_code in b_by_city:
        b_by_city[c_code].sort(key=lambda x: x['name'])

    # Group cities by province_code and region_code
    c_by_prov = {}
    c_by_reg = {}
    for c in cities:
        p_code = c.get('province_code')
        r_code = c.get('region_desc')
        c_obj = {
            'code': c['city_code'],
            'name': c['city_name'],
            'barangays': b_by_city.get(c['city_code'], [])
        }
        if p_code:
            if p_code not in c_by_prov:
                c_by_prov[p_code] = []
            c_by_prov[p_code].append(c_obj)
        if r_code:
            if r_code not in c_by_reg:
                c_by_reg[r_code] = []
            c_by_reg[r_code].append(c_obj)

    # Build aggregated City of Manila
    manila_brgys = []
    seen_brgys = set()
    for c_code, b_list in b_by_city.items():
        if c_code.startswith('1339'):
            for b in b_list:
                if b['code'] not in seen_brgys:
                    seen_brgys.add(b['code'])
                    manila_brgys.append(b)
    manila_brgys.sort(key=lambda x: x['name'])
    city_of_manila = {
        'code': '133900',
        'name': 'City of Manila',
        'barangays': manila_brgys
    }
    if '13' in c_by_reg:
        # Check if already present
        if not any(c['name'].lower() == 'city of manila' for c in c_by_reg['13']):
            c_by_reg['13'].append(city_of_manila)

    # Sort cities
    for p_code in c_by_prov:
        c_by_prov[p_code].sort(key=lambda x: x['name'])
    for r_code in c_by_reg:
        c_by_reg[r_code].sort(key=lambda x: x['name'])

    # Group provinces by region_code
    p_by_reg = {}
    for p in provinces:
        r_code = p['region_code']
        if r_code == '13':
            # NCR has no provinces
            continue
        p_obj = {
            'code': p['province_code'],
            'name': p['province_name'],
            'cities': c_by_prov.get(p['province_code'], [])
        }
        if r_code not in p_by_reg:
            p_by_reg[r_code] = []
        p_by_reg[r_code].append(p_obj)

    for r_code in p_by_reg:
        p_by_reg[r_code].sort(key=lambda x: x['name'])

    res = []
    for r in regions:
        r_code = r['region_code']
        r_name = r['region_name']
        is_ncr = '13' in r_code or 'NCR' in r_name
        reg_obj = {
            'code': r_code,
            'name': r_name,
        }
        if is_ncr:
            reg_obj['cities'] = c_by_reg.get(r_code, [])
        else:
            reg_obj['provinces'] = p_by_reg.get(r_code, [])
        res.append(reg_obj)

    res.sort(key=lambda x: x['name'])

    # Output paths
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    backend_out_dir = os.path.join(base_dir, 'backend', 'apps', 'adopters', 'data')
    os.makedirs(backend_out_dir, exist_ok=True)
    backend_out_file = os.path.join(backend_out_dir, 'philippine_addresses.json')

    frontend_out_dir = os.path.join(base_dir, 'adopter-portal', 'src', 'data')
    os.makedirs(frontend_out_dir, exist_ok=True)
    frontend_out_file = os.path.join(frontend_out_dir, 'philippineAddresses.json')

    print(f'Saving backend dataset to {backend_out_file}...')
    with open(backend_out_file, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

    print(f'Saving frontend dataset to {frontend_out_file}...')
    with open(frontend_out_file, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

    print(f'Done! Successfully wrote {len(res)} regions.')
    for r in res:
        if 'provinces' in r:
            print(f"  {r['name']}: {len(r['provinces'])} provinces")
        else:
            print(f"  {r['name']}: {len(r['cities'])} cities (no province)")

if __name__ == '__main__':
    build_philippine_addresses()
