import { Suspense } from 'react'

import AuthTokenPasswordForm from '@/components/auth/AuthTokenPasswordForm'
import BrandLoadingScreen from '@/components/ui/BrandLoadingScreen'

export default function AcceptInvitationPage() {
  return <Suspense fallback={<BrandLoadingScreen />}><AuthTokenPasswordForm mode="invitation" /></Suspense>
}
