import { Suspense } from 'react'

import VerifyEmailClient from '@/components/auth/VerifyEmailClient'
import BrandLoadingScreen from '@/components/ui/BrandLoadingScreen'

export default function VerifyEmailPage() {
  return <Suspense fallback={<BrandLoadingScreen />}><VerifyEmailClient /></Suspense>
}
