// ── User profile & persistent data types ─────────────────────────────────

export type WatchlistTag = 'Buy' | 'Hold' | 'Avoid' | 'Watch' | string

export interface WatchlistItem {
  ticker: string
  region: string                  // region key e.g. 'US', 'TW', 'HK'
  alertPrice: number | null       // null = no alert set
  alertDirection: 'above' | 'below' // alert fires when price goes above/below
  tag: WatchlistTag | null
  note: string
  addedAt: string                 // ISO date string
}

export interface PortfolioPosition {
  ticker: string
  region: string                  // region key e.g. 'US', 'TW', 'HK'
  shares: number
  avgCostBasis: number            // price paid per share in local currency
  addedAt: string                 // ISO date string
  note: string
}

export interface SoldPosition {
  id: string                      // uuid so multiple sells of same ticker are allowed
  ticker: string
  region: string
  shares: number
  avgCostBasis: number            // buy price per share in local currency
  soldPrice: number               // sell price per share in local currency
  soldAt: string                  // ISO date string of sale
  note: string
}

export interface UserProfile {
  name: string
  watchlist: WatchlistItem[]
  portfolio: PortfolioPosition[]
  soldPositions: SoldPosition[]
  createdAt: string
  updatedAt: string
}

// ── Live price data (returned from backend) ───────────────────────────────

export interface LivePrice {
  ticker: string
  price: number | null
  change: number | null           // absolute change in local currency
  changePct: number | null        // % change
  currency: string                // ISO 4217 e.g. 'USD', 'TWD'
  error?: string
}
