import { Suspense } from 'react'

import AuthTokenPasswordForm from '@/components/auth/AuthTokenPasswordForm'
import BrandLoadingScreen from '@/components/ui/BrandLoadingScreen'

export default function ResetPasswordPage() {
  return <Suspense fallback={<BrandLoadingScreen />}><AuthTokenPasswordForm mode="reset" /></Suspense>
}
