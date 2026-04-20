export interface RegionConfig {
  key: string
  label: string
  flag: string
  suffix: string        // yfinance ticker suffix (empty = US)
  currency: string      // ISO 4217
  currencySymbol: string
  exchangeName: string
}

export const REGIONS: RegionConfig[] = [
  { key: 'US',  label: 'United States',   flag: '🇺🇸', suffix: '',     currency: 'USD', currencySymbol: '$',  exchangeName: 'NYSE / NASDAQ' },
  { key: 'TW',  label: 'Taiwan (TWSE)',   flag: '🇹🇼', suffix: '.TW',  currency: 'TWD', currencySymbol: 'NT$', exchangeName: 'Taiwan Stock Exchange' },
  { key: 'TWO', label: 'Taiwan (OTC)',    flag: '🇹🇼', suffix: '.TWO', currency: 'TWD', currencySymbol: 'NT$', exchangeName: 'Taipei Exchange (OTC)' },
  { key: 'HK',  label: 'Hong Kong',       flag: '🇭🇰', suffix: '.HK',  currency: 'HKD', currencySymbol: 'HK$', exchangeName: 'HKEX' },
  { key: 'JP',  label: 'Japan',           flag: '🇯🇵', suffix: '.T',   currency: 'JPY', currencySymbol: '¥',  exchangeName: 'Tokyo Stock Exchange' },
  { key: 'KR',  label: 'South Korea',     flag: '🇰🇷', suffix: '.KS',  currency: 'KRW', currencySymbol: '₩',  exchangeName: 'Korea Exchange (KRX)' },
  { key: 'CN',  label: 'China (Shanghai)',flag: '🇨🇳', suffix: '.SS',  currency: 'CNY', currencySymbol: '¥',  exchangeName: 'Shanghai Stock Exchange' },
  { key: 'CNS', label: 'China (Shenzhen)',flag: '🇨🇳', suffix: '.SZ',  currency: 'CNY', currencySymbol: '¥',  exchangeName: 'Shenzhen Stock Exchange' },
  { key: 'UK',  label: 'United Kingdom',  flag: '🇬🇧', suffix: '.L',   currency: 'GBp', currencySymbol: 'p',  exchangeName: 'London Stock Exchange' },
  { key: 'DE',  label: 'Germany',         flag: '🇩🇪', suffix: '.DE',  currency: 'EUR', currencySymbol: '€',  exchangeName: 'XETRA' },
  { key: 'FR',  label: 'France',          flag: '🇫🇷', suffix: '.PA',  currency: 'EUR', currencySymbol: '€',  exchangeName: 'Euronext Paris' },
  { key: 'AU',  label: 'Australia',       flag: '🇦🇺', suffix: '.AX',  currency: 'AUD', currencySymbol: 'A$', exchangeName: 'ASX' },
  { key: 'CA',  label: 'Canada',          flag: '🇨🇦', suffix: '.TO',  currency: 'CAD', currencySymbol: 'C$', exchangeName: 'Toronto Stock Exchange' },
  { key: 'IN',  label: 'India (NSE)',     flag: '🇮🇳', suffix: '.NS',  currency: 'INR', currencySymbol: '₹',  exchangeName: 'National Stock Exchange' },
  { key: 'SG',  label: 'Singapore',       flag: '🇸🇬', suffix: '.SI',  currency: 'SGD', currencySymbol: 'S$', exchangeName: 'Singapore Exchange' },
]

export const REGION_MAP: Record<string, RegionConfig> = Object.fromEntries(
  REGIONS.map((r) => [r.key, r])
)

/** Infer region key from a ticker symbol by its suffix */
export function inferRegion(ticker: string): string {
  if (!ticker.includes('.')) return 'US'
  for (const r of REGIONS) {
    if (r.suffix && ticker.endsWith(r.suffix)) return r.key
  }
  return 'US'
}

/** Get currency symbol for a ticker */
export function currencySymbolForTicker(ticker: string, overrideCurrency?: string): string {
  if (overrideCurrency) {
    // Map ISO code → symbol
    const map: Record<string, string> = {
      USD: '$', TWD: 'NT$', HKD: 'HK$', JPY: '¥', KRW: '₩',
      CNY: '¥', GBp: 'p', EUR: '€', AUD: 'A$', CAD: 'C$', INR: '₹', SGD: 'S$',
    }
    return map[overrideCurrency] ?? overrideCurrency
  }
  const region = inferRegion(ticker)
  return REGION_MAP[region]?.currencySymbol ?? '$'
}
