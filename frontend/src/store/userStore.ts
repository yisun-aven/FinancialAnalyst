import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { UserProfile, WatchlistItem, PortfolioPosition, SoldPosition, LivePrice } from '../types/user'

const API_BASE = 'http://localhost:8000'

function now(): string {
  return new Date().toISOString()
}

function defaultProfile(): UserProfile {
  return {
    name: '',
    watchlist: [],
    portfolio: [],
    soldPositions: [],
    createdAt: now(),
    updatedAt: now(),
  }
}

export interface UserStore {
  profile: UserProfile

  // Live price cache
  livePrices: Record<string, LivePrice>
  pricesLoading: boolean
  pricesLastFetched: string | null

  // FX rates: 1 unit of <currency> = N USD
  fxRates: Record<string, number | null>
  fxLoading: boolean

  // Sync state
  syncing: boolean
  syncError: string | null

  // Profile actions
  setName: (name: string) => void

  // Watchlist actions
  addToWatchlist: (item: Omit<WatchlistItem, 'addedAt'>) => void
  removeFromWatchlist: (ticker: string) => void
  updateWatchlistItem: (ticker: string, patch: Partial<Omit<WatchlistItem, 'ticker' | 'addedAt'>>) => void

  // Portfolio actions
  addPosition: (pos: Omit<PortfolioPosition, 'addedAt'>) => void
  removePosition: (ticker: string) => void
  updatePosition: (ticker: string, patch: Partial<Omit<PortfolioPosition, 'ticker' | 'addedAt'>>) => void

  // Sold positions actions
  addSoldPosition: (pos: Omit<SoldPosition, 'id'>) => void
  removeSoldPosition: (id: string) => void
  updateSoldPosition: (id: string, patch: Partial<Omit<SoldPosition, 'id'>>) => void

  // Live price actions
  fetchLivePrices: (tickers: string[]) => Promise<void>

  // FX rate actions
  fetchFxRates: (currencies: string[]) => Promise<void>

  // Backend sync
  loadFromServer: () => Promise<void>
  saveToServer: () => Promise<void>
}

export const useUserStore = create<UserStore>()(
  persist(
    (set, get) => ({
      profile: defaultProfile(),
      livePrices: {},
      pricesLoading: false,
      pricesLastFetched: null,
      fxRates: { USD: 1.0 },
      fxLoading: false,
      syncing: false,
      syncError: null,

      setName: (name) => {
        set((s) => ({ profile: { ...s.profile, name, updatedAt: now() } }))
        get().saveToServer()
      },

      addToWatchlist: (item) => {
        const newItem: WatchlistItem = { ...item, addedAt: now() }
        set((s) => ({
          profile: {
            ...s.profile,
            watchlist: [...s.profile.watchlist.filter((w) => w.ticker !== item.ticker), newItem],
            updatedAt: now(),
          },
        }))
        get().saveToServer()
      },

      removeFromWatchlist: (ticker) => {
        set((s) => ({
          profile: {
            ...s.profile,
            watchlist: s.profile.watchlist.filter((w) => w.ticker !== ticker),
            updatedAt: now(),
          },
        }))
        get().saveToServer()
      },

      updateWatchlistItem: (ticker, patch) => {
        set((s) => ({
          profile: {
            ...s.profile,
            watchlist: s.profile.watchlist.map((w) =>
              w.ticker === ticker ? { ...w, ...patch } : w
            ),
            updatedAt: now(),
          },
        }))
        get().saveToServer()
      },

      addPosition: (pos) => {
        const newPos: PortfolioPosition = { ...pos, addedAt: now() }
        set((s) => ({
          profile: {
            ...s.profile,
            portfolio: [...s.profile.portfolio.filter((p) => p.ticker !== pos.ticker), newPos],
            updatedAt: now(),
          },
        }))
        get().saveToServer()
      },

      removePosition: (ticker) => {
        set((s) => ({
          profile: {
            ...s.profile,
            portfolio: s.profile.portfolio.filter((p) => p.ticker !== ticker),
            updatedAt: now(),
          },
        }))
        get().saveToServer()
      },

      updatePosition: (ticker, patch) => {
        set((s) => ({
          profile: {
            ...s.profile,
            portfolio: s.profile.portfolio.map((p) =>
              p.ticker === ticker ? { ...p, ...patch } : p
            ),
            updatedAt: now(),
          },
        }))
        get().saveToServer()
      },

      addSoldPosition: (pos) => {
        const newPos: SoldPosition = { ...pos, id: crypto.randomUUID() }
        set((s) => ({
          profile: {
            ...s.profile,
            soldPositions: [...(s.profile.soldPositions ?? []), newPos],
            updatedAt: now(),
          },
        }))
        get().saveToServer()
      },

      removeSoldPosition: (id) => {
        set((s) => ({
          profile: {
            ...s.profile,
            soldPositions: (s.profile.soldPositions ?? []).filter((p) => p.id !== id),
            updatedAt: now(),
          },
        }))
        get().saveToServer()
      },

      updateSoldPosition: (id, patch) => {
        set((s) => ({
          profile: {
            ...s.profile,
            soldPositions: (s.profile.soldPositions ?? []).map((p) =>
              p.id === id ? { ...p, ...patch } : p
            ),
            updatedAt: now(),
          },
        }))
        get().saveToServer()
      },

      fetchLivePrices: async (tickers) => {
        if (!tickers.length) return
        set({ pricesLoading: true })
        try {
          const params = new URLSearchParams({ tickers: tickers.join(',') })
          const res = await fetch(`${API_BASE}/api/prices?${params}`)
          if (!res.ok) throw new Error(`HTTP ${res.status}`)
          const data: LivePrice[] = await res.json()
          const map: Record<string, LivePrice> = {}
          for (const lp of data) map[lp.ticker] = lp
          set({ livePrices: map, pricesLastFetched: now(), pricesLoading: false })
        } catch {
          set({ pricesLoading: false })
        }
      },

      fetchFxRates: async (currencies) => {
        const unique = [...new Set(currencies.filter((c) => c && c !== 'USD'))]
        if (!unique.length) return
        set({ fxLoading: true })
        try {
          const params = new URLSearchParams({ currencies: unique.join(',') })
          const res = await fetch(`${API_BASE}/api/fx?${params}`)
          if (!res.ok) throw new Error(`HTTP ${res.status}`)
          const data: Record<string, number | null> = await res.json()
          set((s) => ({ fxRates: { ...s.fxRates, ...data }, fxLoading: false }))
        } catch {
          set({ fxLoading: false })
        }
      },

      loadFromServer: async () => {
        set({ syncing: true, syncError: null })
        try {
          const res = await fetch(`${API_BASE}/api/user`)
          if (res.ok) {
            const data: UserProfile = await res.json()
            if (!data.soldPositions) data.soldPositions = []
            set({ profile: data, syncing: false })
          } else if (res.status === 404) {
            // No server file yet — keep local state, push it up
            set({ syncing: false })
            await get().saveToServer()
          } else {
            throw new Error(`HTTP ${res.status}`)
          }
        } catch (e: unknown) {
          set({ syncing: false, syncError: e instanceof Error ? e.message : 'Unknown error' })
        }
      },

      saveToServer: async () => {
        try {
          const { profile } = get()
          await fetch(`${API_BASE}/api/user`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...profile, updatedAt: now() }),
          })
        } catch {
          // Silently fail — data is still safe in localStorage
        }
      },
    }),
    {
      name: 'fa-user-profile',
      partialize: (s) => ({ profile: s.profile }),
    }
  )
)
