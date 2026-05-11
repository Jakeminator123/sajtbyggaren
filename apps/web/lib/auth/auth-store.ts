/**
 * Stub auth-store för apps/web.
 *
 * apps/web är en publik UI-import från Sajtmaskin utan auth-backend, drizzle
 * eller Zustand-persistance. Den här stubben matchar typkontraktet som
 * `@/components/layout/{navbar,header-actions,site-audit-section}` förväntar
 * sig så att kompilering och rendering funkar — men allt är no-ops.
 *
 * När apps/web får riktig auth (egen, eller via en kommande sajtbyggaren-backend)
 * ska den här filen ersättas med en riktig implementation.
 */

export interface AuthUser {
  id: string;
  email: string | null;
  name: string | null;
  image: string | null;
  diamonds: number;
  emailVerified?: boolean;
  provider: "google" | "email" | "anonymous";
  github_token: string | null;
  github_username: string | null;
}

export interface GuestInfo {
  sessionId: string;
  generationsUsed: number;
  refinesUsed: number;
  canGenerate: boolean;
  canRefine: boolean;
}

export function useAuth() {
  return {
    user: null as AuthUser | null,
    guest: null as GuestInfo | null,
    isLoading: false,
    isInitialized: true,
    isAuthenticated: false,
    diamonds: 0,
    logout: () => {
      // no-op stub
    },
    fetchUser: async () => {
      // no-op stub
    },
    refreshUser: async () => {
      // no-op stub
    },
    updateDiamonds: (_diamonds: number) => {
      // no-op stub
    },
  };
}
