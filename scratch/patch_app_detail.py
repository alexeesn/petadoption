p = "staff-portal/src/pages/ApplicationDetailPage.tsx"
with open(p, "r", encoding="utf-8") as f:
    c = f.read()

# 1. Update REQUIRED_DOCUMENTS
old_req = """const REQUIRED_DOCUMENTS = [
  { type: 'identification', label: 'Valid ID' },
  { type: 'proof_of_address', label: 'Proof of Address' },
  { type: 'barangay_certification', label: 'Barangay Certification' },
  { type: 'cage_photo', label: 'Cage/Kennel Photo' },
];"""

new_req = """/**
 * Application-specific required documents (cage_photo).
 * Note: General identity & eligibility documents (Valid ID, Proof of Address,
 * Barangay Certification) are verified at the profile level via Identity Verification.
 */
const REQUIRED_DOCUMENTS = [
  { type: 'cage_photo', label: 'Cage/Kennel Photo' },
];"""

if old_req in c:
    c = c.replace(old_req, new_req, 1)
    print("Replaced REQUIRED_DOCUMENTS LF")
else:
    old_req_crlf = old_req.replace("\n", "\r\n")
    new_req_crlf = new_req.replace("\n", "\r\n")
    if old_req_crlf in c:
        c = c.replace(old_req_crlf, new_req_crlf, 1)
        print("Replaced REQUIRED_DOCUMENTS CRLF")
    else:
        print("ERROR: REQUIRED_DOCUMENTS not found")

# 2. Add identity verification detail row
old_detail = """          <Detail label="Phone" value={profile?.phone_number} />"""
new_detail = """          <Detail label="Phone" value={profile?.phone_number} />
          <Detail
            label="Identity verification"
            value={
              app.adopter_verification_status ? (
                <div className="flex items-center gap-2">
                  <StatusBadge status={app.adopter_verification_status} />
                  <Link
                    to="/verification-requests"
                    className="text-xs text-primary-600 hover:underline"
                  >
                    View &rarr;
                  </Link>
                </div>
              ) : (
                '—'
              )
            }
          />"""

if old_detail in c:
    c = c.replace(old_detail, new_detail, 1)
    print("Added verification detail LF")
else:
    old_detail_crlf = old_detail.replace("\n", "\r\n")
    new_detail_crlf = new_detail.replace("\n", "\r\n")
    if old_detail_crlf in c:
        c = c.replace(old_detail_crlf, new_detail_crlf, 1)
        print("Added verification detail CRLF")
    else:
        print("ERROR: Detail label=Phone not found")

with open(p, "w", encoding="utf-8") as f:
    f.write(c)

print("ApplicationDetailPage updated")
