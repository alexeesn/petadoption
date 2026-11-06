import { useState, useEffect, useRef, useCallback } from 'react'
import {
  fetchIdentityVerification,
  submitIdentityVerification,
  downloadVerificationFile,
} from '../../services/apiService'
import type { IdentityVerification } from '../../types'
import { Alert, Spinner } from '../../components/UI'
import { Icon } from '../../components/Icons'
import { useToast } from '../../context/ToastContext'
import { formatDate } from '../../utils/format'

const MAX_PDF_SIZE = 20 * 1024 * 1024 // 20 MB
const MAX_IMAGE_SIZE = 10 * 1024 * 1024 // 10 MB

export default function IdentityVerificationSection({
  onStatusChange,
}: {
  onStatusChange?: (status: IdentityVerification['status']) => void
}) {
  const toast = useToast()
  const [record, setRecord] = useState<IdentityVerification | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  // Form states
  const [combinedPdf, setCombinedPdf] = useState<File | null>(null)
  const [selfieFile, setSelfieFile] = useState<File | null>(null)
  const [selfiePreview, setSelfiePreview] = useState<string | null>(null)
  const [privacyConsent, setPrivacyConsent] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  // Camera states
  const [cameraActive, setCameraActive] = useState(false)
  const [cameraError, setCameraError] = useState('')
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const pdfInputRef = useRef<HTMLInputElement | null>(null)

  const loadVerification = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const data = await fetchIdentityVerification()
      setRecord(data)
      onStatusChange?.(data.status)
    } catch {
      setLoadError('Failed to load identity verification status.')
    } finally {
      setLoading(false)
    }
  }, [onStatusChange])

  useEffect(() => {
    loadVerification()
  }, [loadVerification])

  // Stop camera stream when component unmounts or camera is deactivated
  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
    setCameraActive(false)
    setCameraError('')
  }, [])

  useEffect(() => {
    return () => {
      stopCamera()
    }
  }, [stopCamera])

  // Start webcam
  const startCamera = async () => {
    setCameraError('')
    setError('')
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setCameraError(
          'Camera access is not supported by your browser. Please choose a photo file instead.'
        )
        return
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      })
      streamRef.current = stream
      setCameraActive(true)
      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          videoRef.current.play().catch(() => {})
        }
      }, 50)
    } catch (err: unknown) {
      const e = err as { name?: string; message?: string }
      if (e.name === 'NotAllowedError' || e.name === 'PermissionDeniedError') {
        setCameraError(
          'Camera permission was denied. Please allow camera access in your browser settings, or upload a photo file below.'
        )
      } else if (e.name === 'NotFoundError' || e.name === 'DevicesNotFoundError') {
        setCameraError('No camera found on your device. Please upload a photo file below.')
      } else {
        setCameraError(
          'Could not start camera. Please upload a photo file from your device instead.'
        )
      }
    }
  }

  // Capture photo from video stream
  const capturePhoto = () => {
    if (!videoRef.current) return
    const video = videoRef.current
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth || 640
    canvas.height = video.videoHeight || 480
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

    canvas.toBlob(
      (blob) => {
        if (blob) {
          const file = new File([blob], 'selfie_with_id.jpg', { type: 'image/jpeg' })
          setSelfieFile(file)
          setSelfiePreview(URL.createObjectURL(blob))
          stopCamera()
          setFieldErrors((prev) => {
            const next = { ...prev }
            delete next.selfie_with_id
            return next
          })
        }
      },
      'image/jpeg',
      0.9
    )
  }

  const handlePdfChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
      setFieldErrors((prev) => ({
        ...prev,
        combined_pdf: 'Only PDF files are accepted for the combined document.',
      }))
      return
    }
    if (file.size > MAX_PDF_SIZE) {
      setFieldErrors((prev) => ({
        ...prev,
        combined_pdf: 'The combined PDF must be 20 MB or smaller.',
      }))
      return
    }
    setCombinedPdf(file)
    setFieldErrors((prev) => {
      const next = { ...prev }
      delete next.combined_pdf
      return next
    })
  }

  const handleImageFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const validTypes = ['image/jpeg', 'image/png', 'image/webp']
    const validExts = ['.jpg', '.jpeg', '.png', '.webp']
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!validTypes.includes(file.type) && !validExts.includes(ext)) {
      setFieldErrors((prev) => ({
        ...prev,
        selfie_with_id: 'Please select a valid image file (JPG, PNG, or WebP).',
      }))
      return
    }
    if (file.size > MAX_IMAGE_SIZE) {
      setFieldErrors((prev) => ({
        ...prev,
        selfie_with_id: 'The selfie image must be 10 MB or smaller.',
      }))
      return
    }
    setSelfieFile(file)
    setSelfiePreview(URL.createObjectURL(file))
    setFieldErrors((prev) => {
      const next = { ...prev }
      delete next.selfie_with_id
      return next
    })
  }

  const clearSelfie = () => {
    setSelfieFile(null)
    if (selfiePreview) {
      URL.revokeObjectURL(selfiePreview)
      setSelfiePreview(null)
    }
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleDownload = async (field: 'combined_pdf' | 'selfie_with_id', filename: string) => {
    try {
      const blob = await downloadVerificationFile(field)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch {
      setError('Could not download the verification file. Please try again.')
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    const errors: Record<string, string> = {}

    if (!combinedPdf) {
      errors.combined_pdf = 'Please upload your combined PDF containing the required documents.'
    }
    if (!selfieFile) {
      errors.selfie_with_id = 'Please capture or upload a selfie with your valid ID.'
    }
    if (!privacyConsent) {
      errors.privacy_consent = 'You must review and agree to the Privacy Notice before submitting.'
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors)
      setError('Please resolve the highlighted issues before submitting.')
      return
    }

    setSubmitting(true)
    try {
      const formData = new FormData()
      formData.append('combined_pdf', combinedPdf as Blob)
      formData.append('selfie_with_id', selfieFile as Blob)
      formData.append('privacy_consent', 'true')

      const updated = await submitIdentityVerification(formData)
      setRecord(updated)
      onStatusChange?.(updated.status)
      setCombinedPdf(null)
      clearSelfie()
      setPrivacyConsent(false)
      toast.success(
        'Documents submitted',
        'Your identity verification documents have been submitted and are now pending review.'
      )
    } catch (err: unknown) {
      const response = (err as { response?: { data?: Record<string, unknown> } })?.response
      if (response?.data && typeof response.data === 'object') {
        const data = response.data
        if (data.error) {
          setError(String(data.error))
        } else if (data.non_field_errors) {
          setError(
            Array.isArray(data.non_field_errors)
              ? data.non_field_errors.join(' ')
              : String(data.non_field_errors)
          )
        } else {
          const fe: Record<string, string> = {}
          for (const [k, v] of Object.entries(data)) {
            fe[k] = Array.isArray(v) ? v.join(' ') : String(v)
          }
          setFieldErrors(fe)
          setError('Please correct the errors indicated below.')
        }
      } else {
        setError('Submission failed. Please check your connection and try again.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="panel p-6 mt-8">
        <Spinner label="Loading verification status..." />
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="panel p-6 mt-8">
        <Alert type="error">{loadError}</Alert>
      </div>
    )
  }

  const status = record?.status || 'not_submitted'
  const isVerified = status === 'verified'
  const isPending = status === 'pending_review'
  const isRejected = status === 'rejected'
  const isNotSubmitted = status === 'not_submitted'

  return (
    <div className="panel p-6 mt-8 space-y-6">
      {/* Header and status badge */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-stone-200 pb-4">
        <div>
          <h2 className="text-lg font-bold text-primary-900 flex items-center gap-2">
            <Icon name="check-circle" className="w-5 h-5 text-primary-600" />
            Identity &amp; Document Verification
          </h2>
          <p className="text-xs text-stone-500 mt-0.5">
            Verify your identity once. Approved documents are automatically applied to all future
            adoption applications.
          </p>
        </div>

        {/* Status Pill */}
        <div className="shrink-0">
          {isVerified && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              Verified
            </span>
          )}
          {isPending && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">
              <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
              Pending Review
            </span>
          )}
          {isRejected && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-100 text-rose-800">
              <span className="w-2 h-2 rounded-full bg-rose-500" />
              Requires Resubmission
            </span>
          )}
          {isNotSubmitted && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-stone-100 text-stone-700">
              <span className="w-2 h-2 rounded-full bg-stone-400" />
              Not Submitted
            </span>
          )}
        </div>
      </div>

      {/* Global alert messages */}
      {error && <Alert type="error">{error}</Alert>}

      {/* ── STATE: VERIFIED ── */}
      {isVerified && (
        <div className="space-y-4">
          <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-4">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-full bg-emerald-100 text-emerald-700 shrink-0">
                <Icon name="check-circle" className="w-5 h-5" />
              </div>
              <div className="text-sm">
                <h3 className="font-semibold text-emerald-950">Identity Verified</h3>
                <p className="text-emerald-900 mt-1">
                  Your identity and general eligibility documents have been reviewed and approved by
                  authorized shelter staff. Your verified status is active and automatically reused
                  for all current and future adoption applications.
                </p>
                {record?.submitted_at && (
                  <p className="text-xs text-emerald-700 mt-2">
                    Verified submission date: {formatDate(record.submitted_at)}
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Secure Document Preview / Download Options */}
          <div className="border border-stone-200 rounded-xl p-4 bg-stone-50/50">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-stone-600 mb-3">
              Your Verified Documents
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div className="flex items-center justify-between p-3 bg-white rounded-lg border border-stone-200">
                <div className="flex items-center gap-2 text-stone-800 font-medium">
                  <Icon name="document" className="w-4 h-4 text-primary-600" />
                  Combined Required Documents (PDF)
                </div>
                <button
                  type="button"
                  onClick={() => handleDownload('combined_pdf', 'verified_documents.pdf')}
                  className="text-primary-700 hover:text-primary-900 font-semibold underline"
                >
                  Download
                </button>
              </div>

              <div className="flex items-center justify-between p-3 bg-white rounded-lg border border-stone-200">
                <div className="flex items-center gap-2 text-stone-800 font-medium">
                  <Icon name="user" className="w-4 h-4 text-primary-600" />
                  Selfie with Valid ID (Photo)
                </div>
                <button
                  type="button"
                  onClick={() => handleDownload('selfie_with_id', 'verified_selfie.jpg')}
                  className="text-primary-700 hover:text-primary-900 font-semibold underline"
                >
                  Download
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── STATE: PENDING REVIEW ── */}
      {isPending && (
        <div className="space-y-4">
          <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-4">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-full bg-amber-100 text-amber-700 shrink-0">
                <Icon name="clock" className="w-5 h-5" />
              </div>
              <div className="text-sm">
                <h3 className="font-semibold text-amber-950">Documents Under Review</h3>
                <p className="text-amber-900 mt-1 leading-relaxed">
                  Your identity documents and selfie with ID were submitted on{' '}
                  <span className="font-medium">
                    {record?.submitted_at ? formatDate(record.submitted_at) : 'recently'}
                  </span>{' '}
                  and are currently queued for staff review. Once approved, you will be notified and
                  able to submit adoption applications.
                </p>
                <p className="text-xs text-amber-800 mt-2 italic">
                  Documents cannot be modified while review is in progress.
                </p>
              </div>
            </div>
          </div>

          {/* Secure Download Links */}
          <div className="border border-stone-200 rounded-xl p-4 bg-stone-50/50">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-stone-600 mb-3">
              Submitted Files
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div className="flex items-center justify-between p-3 bg-white rounded-lg border border-stone-200">
                <div className="flex items-center gap-2 text-stone-800 font-medium truncate">
                  <Icon name="document" className="w-4 h-4 text-primary-600 shrink-0" />
                  <span className="truncate">Combined Required Documents (PDF)</span>
                </div>
                <button
                  type="button"
                  onClick={() => handleDownload('combined_pdf', 'submitted_documents.pdf')}
                  className="text-primary-700 hover:text-primary-900 font-semibold underline shrink-0 ml-2"
                >
                  Download
                </button>
              </div>

              <div className="flex items-center justify-between p-3 bg-white rounded-lg border border-stone-200">
                <div className="flex items-center gap-2 text-stone-800 font-medium truncate">
                  <Icon name="user" className="w-4 h-4 text-primary-600 shrink-0" />
                  <span className="truncate">Selfie with Valid ID (Photo)</span>
                </div>
                <button
                  type="button"
                  onClick={() => handleDownload('selfie_with_id', 'submitted_selfie.jpg')}
                  className="text-primary-700 hover:text-primary-900 font-semibold underline shrink-0 ml-2"
                >
                  Download
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── STATE: REJECTED (SHOW REJECTION REASON + RESUBMISSION FORM) ── */}
      {isRejected && (
        <div className="rounded-xl border border-rose-300 bg-rose-50/70 p-4 space-y-2">
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-full bg-rose-100 text-rose-700 shrink-0">
              <Icon name="x-circle" className="w-5 h-5" />
            </div>
            <div className="text-sm">
              <h3 className="font-semibold text-rose-950">Verification Requires Correction</h3>
              <p className="text-rose-900 mt-1">
                Your submitted verification could not be approved. Please review the reason below,
                update your files, and resubmit.
              </p>
              {record?.rejection_reason && (
                <div className="mt-3 p-3 bg-white rounded-lg border border-rose-200 text-rose-900">
                  <span className="font-semibold block text-xs uppercase tracking-wide text-rose-800 mb-1">
                    Staff Feedback / Reason for Rejection:
                  </span>
                  <p className="whitespace-pre-line text-sm">{record.rejection_reason}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── SUBMISSION FORM (NOT SUBMITTED OR REJECTED) ── */}
      {(isNotSubmitted || isRejected) && (
        <form onSubmit={handleSubmit} className="space-y-6 pt-2">
          {/* 1. Privacy Notice */}
          <div className="rounded-xl border border-primary-200 bg-primary-50/50 p-4 text-xs text-stone-700 space-y-2.5">
            <h3 className="font-bold text-primary-950 text-sm flex items-center gap-1.5">
              <Icon name="lock" className="w-4 h-4 text-primary-700" />
              Privacy Notice &amp; Data Protection
            </h3>
            <p className="leading-relaxed">
              Before submitting your documents, please review how your personal information is
              handled:
            </p>
            <ul className="list-disc pl-5 space-y-1 text-stone-600">
              <li>
                <strong>Purpose:</strong> Your government ID, proof of address, barangay
                certification, and selfie are collected strictly to verify your identity and legal
                eligibility as a pet adopter.
              </li>
              <li>
                <strong>Authorized Access:</strong> Only authorized shelter staff and system
                administrators can access your submitted files during review.
              </li>
              <li>
                <strong>Protection:</strong> Files are stored in protected private storage and
                authenticated through Django. They are never published via public URLs.
              </li>
              <li>
                <strong>Retention &amp; Deletion:</strong> Your documents are securely retained
                while your account is active and throughout the adoption lifecycle. You may contact
                shelter staff to request deletion of unverified files.
              </li>
            </ul>

            <label className="flex items-start gap-2.5 pt-2 text-stone-900 font-medium cursor-pointer">
              <input
                type="checkbox"
                checked={privacyConsent}
                onChange={(e) => {
                  setPrivacyConsent(e.target.checked)
                  if (e.target.checked) {
                    setFieldErrors((prev) => {
                      const next = { ...prev }
                      delete next.privacy_consent
                      return next
                    })
                  }
                }}
                className="mt-0.5 w-4 h-4 rounded text-primary-600 focus:ring-primary-500"
              />
              <span>
                I have read and agree to the Privacy Notice, and I give consent to the collection and
                verification of my identity documents and selfie by shelter staff.{' '}
                <span className="text-red-600">*</span>
              </span>
            </label>
            {fieldErrors.privacy_consent && (
              <p className="text-red-600 text-xs font-semibold">{fieldErrors.privacy_consent}</p>
            )}
          </div>

          {/* 2. Combined Required Documents (Single PDF) */}
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-semibold text-stone-900">
                Combined Required Documents (PDF){' '}
                <span className="text-red-600" aria-hidden="true">
                  *
                </span>
              </label>
              <p className="text-xs text-stone-500 mt-0.5">
                Upload a single PDF containing all three required eligibility documents.
              </p>
            </div>

            {/* Expected contents guide */}
            <div className="rounded-lg bg-stone-50 border border-stone-200 p-3 text-xs text-stone-700">
              <span className="font-semibold text-stone-900 block mb-1.5">
                Expected Contents of the Combined PDF:
              </span>
              <ol className="list-decimal pl-4 space-y-1 text-stone-600">
                <li>
                  <strong className="text-stone-800">Valid ID:</strong> Clear copy of a
                  government-issued ID (Passport, Driver&apos;s License, UMID, National ID, Postal ID).
                </li>
                <li>
                  <strong className="text-stone-800">Proof of Address:</strong> Recent utility bill,
                  lease contract, or bank statement matching your profile address.
                </li>
                <li>
                  <strong className="text-stone-800">Barangay Certification:</strong> Residency
                  certificate issued by your local barangay.
                </li>
              </ol>
            </div>

            {/* File Upload Slot */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
              <input
                ref={pdfInputRef}
                type="file"
                accept="application/pdf,.pdf"
                onChange={handlePdfChange}
                className="hidden"
                id="combined-pdf-upload"
              />
              <button
                type="button"
                onClick={() => pdfInputRef.current?.click()}
                className="btn btn-outline text-xs px-3 py-2 flex items-center gap-1.5"
              >
                <Icon name="document" className="w-4 h-4 text-primary-600" />
                {combinedPdf ? 'Change PDF File' : 'Choose Combined PDF File'}
              </button>

              {combinedPdf ? (
                <div className="flex items-center gap-2 text-xs text-stone-800">
                  <span className="font-medium truncate max-w-xs">{combinedPdf.name}</span>
                  <span className="text-stone-400">
                    ({(combinedPdf.size / (1024 * 1024)).toFixed(2)} MB)
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setCombinedPdf(null)
                      if (pdfInputRef.current) pdfInputRef.current.value = ''
                    }}
                    className="text-rose-600 hover:text-rose-800 font-bold ml-1"
                    title="Remove file"
                  >
                    &times;
                  </button>
                </div>
              ) : (
                <span className="text-xs text-stone-400 italic">No PDF file selected yet</span>
              )}
            </div>
            {fieldErrors.combined_pdf && (
              <p className="text-red-600 text-xs font-semibold">{fieldErrors.combined_pdf}</p>
            )}
          </div>

          {/* 3. Selfie with Valid ID */}
          <div className="space-y-3 pt-2">
            <div>
              <label className="block text-sm font-semibold text-stone-900">
                Selfie with Valid ID{' '}
                <span className="text-red-600" aria-hidden="true">
                  *
                </span>
              </label>
              <p className="text-xs text-stone-500 mt-0.5">
                Take a clear photo showing your face while holding your valid ID next to your face.
                Both your face and ID details must be clear and readable.
              </p>
            </div>

            {/* Camera Error Message */}
            {cameraError && <Alert type="error">{cameraError}</Alert>}

            {/* Camera Viewfinder */}
            {cameraActive && (
              <div className="rounded-xl border-2 border-primary-400 bg-black overflow-hidden p-2 max-w-md mx-auto space-y-3">
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className="w-full h-64 object-cover rounded-lg bg-stone-900"
                />
                <div className="flex justify-center gap-3">
                  <button
                    type="button"
                    onClick={capturePhoto}
                    className="btn btn-primary text-xs flex items-center gap-1.5"
                  >
                    <Icon name="camera" className="w-4 h-4" />
                    Capture Photo
                  </button>
                  <button
                    type="button"
                    onClick={stopCamera}
                    className="btn btn-outline text-xs text-white border-stone-500 hover:bg-stone-800"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {/* Captured / Uploaded Preview */}
            {!cameraActive && selfiePreview && (
              <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 p-3 bg-stone-50 rounded-xl border border-stone-200 max-w-md">
                <img
                  src={selfiePreview}
                  alt="Selfie with ID preview"
                  className="w-32 h-32 object-cover rounded-lg border border-stone-300"
                />
                <div className="space-y-2 text-xs">
                  <p className="font-semibold text-stone-900">Photo Ready</p>
                  <p className="text-stone-500">
                    Verify that your face and ID are clearly visible and in focus.
                  </p>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={clearSelfie}
                      className="text-rose-600 hover:text-rose-800 font-semibold underline"
                    >
                      Remove / Retake
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Action buttons to trigger camera or file upload */}
            {!cameraActive && !selfiePreview && (
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={startCamera}
                  className="btn btn-outline text-xs px-3 py-2 flex items-center gap-1.5"
                >
                  <Icon name="camera" className="w-4 h-4 text-primary-600" />
                  Take Photo with Camera
                </button>

                <span className="text-xs text-stone-400">or</span>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handleImageFileChange}
                  className="hidden"
                  id="selfie-file-upload"
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="btn btn-outline text-xs px-3 py-2 flex items-center gap-1.5"
                >
                  <Icon name="upload" className="w-4 h-4 text-stone-600" />
                  Upload Photo File
                </button>
              </div>
            )}

            {fieldErrors.selfie_with_id && (
              <p className="text-red-600 text-xs font-semibold">{fieldErrors.selfie_with_id}</p>
            )}
          </div>

          {/* Submit Action */}
          <div className="border-t border-stone-200 pt-4 flex flex-col sm:flex-row items-center justify-between gap-3">
            <p className="text-xs text-stone-500">
              Authorized staff will review your submission. Approvals are not automated.
            </p>
            <button
              type="submit"
              disabled={submitting}
              className="btn btn-primary w-full sm:w-auto text-sm flex items-center justify-center gap-2"
            >
              {submitting ? (
                <>
                  <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  Submitting Documents...
                </>
              ) : isRejected ? (
                'Resubmit for Verification'
              ) : (
                'Submit for Verification'
              )}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
