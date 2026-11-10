import { createClient } from '@supabase/supabase-js'

import { config } from '@/lib/config'

/**
 * Supabase client — used ONLY for authentication (sign up, sign in, sessions).
 * All financial data is read and written through our FastAPI backend.
 *
 * supabase-js stores the session in localStorage and refreshes the access token
 * automatically before it expires.
 */
export const supabase = createClient(config.supabaseUrl, config.supabaseKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true, // picks up the session from email-confirmation links
  },
})
