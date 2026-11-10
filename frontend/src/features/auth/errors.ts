import type { AuthError } from '@supabase/supabase-js'

/** Turn Supabase auth errors into short, human messages. */
export function friendlyAuthError(error: AuthError): string {
  switch (error.code) {
    case 'invalid_credentials':
      return 'Wrong email or password.'
    case 'email_not_confirmed':
      return 'Please confirm your email first — check your inbox for the link.'
    case 'user_already_exists':
    case 'email_exists':
      return 'An account with this email already exists. Try signing in.'
    case 'weak_password':
      return 'That password is too weak. Use at least 8 characters with a mix of letters and numbers.'
    case 'over_email_send_rate_limit':
    case 'over_request_rate_limit':
      return 'Too many attempts. Please wait a minute and try again.'
    case 'validation_failed':
      return 'Please enter a valid email address.'
    default:
      if (error.status === 0 || error.name === 'AuthRetryableFetchError') {
        return 'Could not reach the sign-in service. Check your connection.'
      }
      return error.message || 'Something went wrong. Please try again.'
  }
}
