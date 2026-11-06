import { Icon } from './Icons'

const adoptionSteps = [
  {
    icon: 'user',
    title: 'Adopter assessment',
    description: 'Staff review your application and readiness to give your chosen pet a suitable home.',
  },
  {
    icon: 'clipboard',
    title: 'Adoption paperwork',
    description: 'Complete the required forms and receive the documents for your pet’s adoption.',
  },
  {
    icon: 'home',
    title: 'Onsite handover',
    description: 'Meet the team at the center and follow their guidance before bringing your companion home.',
  },
]

export default function AdoptionFeeSection() {
  return (
    <section id="adoption-fee" aria-labelledby="adoption-fee-title" className="border-y border-stone-200 bg-surface">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8 lg:py-16">
        <div className="grid gap-8 lg:grid-cols-[0.85fr_1.15fr] lg:gap-14">
          <div>
            <p className="section-label">Adoption fee &amp; what to expect</p>
            <h2 id="adoption-fee-title" className="mt-3 text-3xl font-bold text-stone-900 sm:text-4xl">A clear start to<br />a life together.</h2>
            <p className="mt-4 max-w-md text-sm leading-7 text-stone-600">Know the adoption fee and the steps ahead before you apply, so you can focus on welcoming your new companion.</p>

            <div className="mt-6 rounded-xl border border-primary-200 bg-primary-50 p-6">
              <p className="text-sm font-semibold text-primary-800">Adoption fee</p>
              <p className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1"><span className="text-5xl font-bold tracking-tight text-primary-900">₱500</span><span className="text-sm text-primary-800">per adoption</span></p>
              <p className="mt-4 text-sm leading-7 text-stone-700">Paid onsite after application approval and a confirmed visit. Staff record your payment and provide a receipt reference.</p>
              <div className="mt-5 flex items-start gap-2 border-t border-primary-200 pt-4 text-xs leading-6 text-primary-800">
                <Icon name="shield" className="mt-0.5 h-4 w-4 shrink-0" />
                <p>You can browse pets and submit your application before paying the adoption fee.</p>
              </div>
            </div>
          </div>

          <div className="min-w-0">
            <h3 className="text-xl font-bold text-stone-900">What is the ₱500 for?</h3>
            <p className="mt-3 text-sm leading-7 text-stone-600">This is the center’s adoption fee, based on the published Quezon City fee. Your adoption journey includes the following steps:</p>
            <ul className="mt-5 divide-y divide-stone-200">
              {adoptionSteps.map(step => (
                <li key={step.title} className="flex items-start gap-4 py-5 first:pt-0">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-stone-200 bg-stone-50 text-primary-700"><Icon name={step.icon} className="h-5 w-5" /></span>
                  <div><h4 className="text-sm font-bold text-stone-900">{step.title}</h4><p className="mt-1 text-sm leading-7 text-stone-600">{step.description}</p></div>
                </li>
              ))}
            </ul>
            <div className="mt-1 rounded-lg border border-stone-200 bg-stone-50 p-5">
              <h4 className="text-sm font-bold text-stone-900">Prepare for your visit</h4>
              <p className="mt-2 text-sm leading-7 text-stone-600">Bring an appropriate carrier or cage, plus a collar, harness, or leash. Ask staff about your chosen pet’s health records and any care or services it may need.</p>
            </div>
          </div>
        </div>

        <div className="mt-8 flex flex-col justify-between gap-3 border-t border-stone-200 pt-5 sm:flex-row sm:items-center">
          <p className="max-w-2xl text-xs leading-6 text-stone-600">Fee reference: Quezon City Animal Care and Adoption Center. The published fee has no itemized breakdown of medical or shelter expenses.</p>
          <a href="https://quezoncity.gov.ph/qcitizen-guides/how-to-adopt-a-pet/" target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 shrink-0 items-center gap-2 self-start text-sm font-semibold text-primary-700 underline decoration-primary-300 underline-offset-4 hover:text-primary-900 sm:self-auto">View official QC guide<span className="sr-only"> (opens in a new tab)</span><Icon name="arrowRight" className="h-4 w-4" /></a>
        </div>
      </div>
    </section>
  )
}
