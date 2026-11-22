// Typed client for the FareWatch FastAPI backend. Money arrives as decimal
// strings and stays a string for display; it is only converted to a number
// for chart geometry.

export type Money = string;

export interface Flight {
  id: number;
  origin: string;
  destination: string;
  origin_tz: string;
  destination_tz: string;
  flight_date: string;
  flight_number: string;
  airline: string;
  scheduled_departure_local: string | null;
  scheduled_arrival_local: string | null;
  schedule_status: string;
  direction: string;
  is_target: boolean;
  label: string | null;
}

export interface Observation {
  id: number;
  flight_id: number;
  captured_at_utc: string;
  currency: string;
  price_total: Money;
  original_currency: string;
  original_price: Money;
  fx_rate: string | null;
  fx_source: string | null;
  source: string;
  source_url: string | null;
  passengers: number;
  fare_product: string;
  baggage_profile: string;
  taxes_fees_included: string;
  discount_club: string;
  verification: string;
  profile_assumed: boolean;
  booking_url: string | null;
  is_demo: boolean;
  notes: string | null;
  flight_number: string;
  origin: string;
  destination: string;
  flight_date: string;
  lead_time_days: number;
}

export type Status =
  | "INSUFFICIENT DATA"
  | "ATTRACTIVE PRICE"
  | "NORMAL RANGE"
  | "EXPENSIVE RELATIVE TO HISTORY";

export interface Stats {
  count: number;
  days_to_departure: number;
  min: Money | null;
  max: Money | null;
  median: Money | null;
  mean: Money | null;
  latest: Money | null;
  latest_at: string | null;
  previous: Money | null;
  pct_change_vs_previous: string | null;
  median_7d: Money | null;
  median_7d_count: number;
  median_7d_note: string | null;
  latest_rank: number | null;
  latest_percentile: string | null;
  volatility_stdev: Money | null;
  volatility_cv_pct: string | null;
  drop_detected: boolean;
  best: Money | null;
  best_at: string | null;
  latest_vs_median_pct: string | null;
  status: Status;
  status_reason: string;
  threshold_pct: string;
  min_samples: number;
  heuristic_note: string;
}

export interface ProfileAnalysis {
  profile: {
    currency: string;
    passengers: number;
    fare_product: string;
    baggage_profile: string;
    taxes_fees_included: string;
    discount_club: string;
  };
  profile_label: string;
  matches_preferences: boolean;
  is_member_fare: boolean;
  stats: Stats;
  latest_source: string;
  latest_verification: string;
  latest_profile_assumed: boolean;
  sources: string[];
}

export interface FlightAnalysis {
  flight_id: number;
  total_quotes: number;
  last_valid_quote_at: string | null;
  primary: ProfileAnalysis | null;
  profiles: ProfileAnalysis[];
  note: string | null;
}

export interface BookingLink {
  label: string;
  url: string;
  note: string;
}

export interface Preferences {
  demo_mode: boolean;
  display_currency: string;
  baggage_profile: string;
  discount_club: string;
  passengers: number;
  median_threshold_pct: string;
  min_samples_for_status: number;
  drop_alert_pct: string;
  collector_times: string;
  max_queries_per_day: number;
  min_minutes_between_checks: number;
  collector_include_comparisons: boolean;
}

export interface DashboardLeg {
  flight: Flight;
  analysis: FlightAnalysis;
  latest_observation: Observation | null;
  best_observation: Observation | null;
  freshness_hours: number | null;
  booking_links: BookingLink[];
}

export interface Dashboard {
  demo: boolean;
  generated_at_utc: string;
  preferences: Preferences;
  provider: {
    serpapi_configured: boolean;
    collector_enabled: boolean;
    last_successful_fetch_utc: string | null;
  };
  legs: DashboardLeg[];
  combined_legs: {
    available: boolean;
    reasons: string[];
    currency?: string;
    latest_total?: Money;
    best_total?: Money;
    outbound_latest_at?: string;
    return_latest_at?: string;
    note?: string;
  };
  latest_round_trip_quote: {
    price_total: Money;
    currency: string;
    captured_at_utc: string;
    source: string;
    baggage_profile: string;
    discount_club: string;
    verification: string;
  } | null;
  disclaimer: string;
}

export interface FlightDetail {
  demo: boolean;
  flight: Flight;
  analysis: FlightAnalysis;
  observations: Observation[];
  booking_links: BookingLink[];
}

export interface CompareRow {
  observation_id: number;
  flight_id: number;
  flight_number: string;
  airline: string;
  origin: string;
  destination: string;
  flight_date: string;
  is_target: boolean;
  captured_at_utc: string;
  price_total: Money;
  currency: string;
  source: string;
  verification: string;
  matches_preferences: boolean;
  profile_label: string;
  discount_club: string;
  lead_time_days: number;
  lead_time_bucket: string;
  travel_weekday: string;
  observation_weekday: string;
  travel_is_holiday: boolean;
  travel_holiday_name: string | null;
  travel_near_holiday: boolean;
  travel_festive_window: boolean;
}

export interface CompareData {
  demo: boolean;
  rows: CompareRow[];
  lead_time_buckets: { bucket: string; count: number; median: Money | null; flights: number }[];
  note: string;
}

export interface AlertRule {
  id: number;
  flight_id: number;
  kind: "threshold" | "pct_drop";
  threshold: Money | null;
  pct_drop: string | null;
  currency: string;
  baggage_profile: string;
  discount_club: string;
  active: boolean;
  email: boolean;
  created_at: string;
  flight: string;
}

export interface AlertEvent {
  id: number;
  rule_id: number;
  flight_id: number;
  observation_id: number;
  triggered_at_utc: string;
  message: string;
  email_status: string;
  acknowledged: boolean;
  flight: string | null;
}

export interface SettingsView {
  preferences: Preferences;
  providers: {
    name: string;
    label: string;
    connected: boolean;
    description: string;
    last_successful_fetch_utc?: string | null;
  }[];
  collector: {
    enabled: boolean;
    scheduler_running: boolean;
    next_runs: string[];
    timezone: string;
    budget: {
      used_today: number;
      daily_cap: number;
      used_this_month: number;
      monthly_quota: number;
      remaining_today: number;
      remaining_month: number;
    };
  };
  email_configured: boolean;
  currencies: string[];
}

export interface ProviderRun {
  id: number;
  provider: string;
  trigger: string;
  started_at_utc: string;
  finished_at_utc: string | null;
  origin: string | null;
  destination: string | null;
  search_date: string | null;
  status: string;
  queries_used: number;
  observations_created: number;
  http_status: number | null;
  message: string | null;
}

export interface Promotion {
  id: number;
  title: string;
  airline: string;
  announced_date: string | null;
  booking_deadline: string | null;
  travel_start: string | null;
  travel_end: string | null;
  discount_description: string;
  excluded_dates: string | null;
  member_only: boolean;
  source_url: string | null;
  notes: string | null;
  created_at: string;
}

export interface Fee {
  id: number;
  flight_id: number | null;
  item: string;
  price: Money;
  currency: string;
  per: string;
  observed_at_utc: string;
  source: string;
  source_url: string | null;
  notes: string | null;
}

export interface FeeComparison {
  demo: boolean;
  currency: string;
  legs: {
    flight_id: number;
    flight: string;
    base_observed_at: string | null;
    base_source: string | null;
    options: {
      bundle: string;
      label: string;
      base_fare: Money | null;
      addon_fee: Money | null;
      addon_known: boolean;
      total: Money | null;
      addon_source: string | null;
      addon_observed_at: string | null;
      addon_source_url: string | null;
    }[];
  }[];
  discount_club_membership: Fee | null;
  note: string;
}

export interface ForecastResult {
  status: "insufficient_data" | "evaluated";
  experimental: boolean;
  message?: string;
  requirements?: Record<string, string>;
  profile?: string;
  n_train?: number;
  n_test?: number;
  mae_model?: Money;
  mae_baseline_last_price?: Money;
  model_beats_baseline?: boolean;
  abs_error_p10?: Money;
  abs_error_p90?: Money;
  method?: string;
  caveat?: string;
}

export interface ImportReport {
  total_rows: number;
  imported: number;
  duplicates: number;
  errors: { row: number; error: string }[];
  dry_run: boolean;
}

export class ApiError extends Error {
  status: number;
  details: { field: string; message: string }[];
  constructor(status: number, message: string, details: { field: string; message: string }[] = []) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: init?.body instanceof FormData ? init?.headers : { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "Cannot reach the FareWatch backend. Is it running on http://127.0.0.1:8000?");
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!res.ok) {
    const b = body as { detail?: unknown; errors?: { field: string; message: string }[] } | null;
    const detail = typeof b?.detail === "string" ? b.detail : `Request failed (${res.status})`;
    throw new ApiError(res.status, detail, b?.errors ?? []);
  }
  return body as T;
}

const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });

export const api = {
  dashboard: () => request<Dashboard>("/api/dashboard"),
  flights: () => request<Flight[]>("/api/flights"),
  createFlight: (body: Record<string, unknown>) => request<Flight>("/api/flights", json("POST", body)),
  flight: (id: number) => request<FlightDetail>(`/api/flights/${id}`),
  observations: (params: Record<string, string | undefined> = {}) => {
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]);
    return request<{ demo: boolean; items: Observation[] }>(`/api/observations?${q}`);
  },
  addObservation: (body: Record<string, unknown>) =>
    request<{ observation: Observation | null; duplicate: boolean; alerts_triggered: number; message: string }>(
      "/api/observations",
      json("POST", body),
    ),
  deleteObservation: (id: number) => request<void>(`/api/observations/${id}`, { method: "DELETE" }),
  importCsv: (file: File, dryRun: boolean) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<ImportReport>(`/api/observations/import?dry_run=${dryRun}`, { method: "POST", body: fd });
  },
  addRoundTrip: (body: Record<string, unknown>) => request("/api/round-trips", json("POST", body)),
  compare: (origin?: string, destination?: string) => {
    const q = new URLSearchParams();
    if (origin) q.set("origin", origin);
    if (destination) q.set("destination", destination);
    return request<CompareData>(`/api/compare?${q}`);
  },
  forecast: () => request<ForecastResult>("/api/forecast"),
  alertRules: () => request<AlertRule[]>("/api/alerts/rules"),
  addAlertRule: (body: Record<string, unknown>) => request<AlertRule>("/api/alerts/rules", json("POST", body)),
  toggleAlertRule: (id: number, active: boolean) =>
    request<AlertRule>(`/api/alerts/rules/${id}?active=${active}`, { method: "PATCH" }),
  deleteAlertRule: (id: number) => request<void>(`/api/alerts/rules/${id}`, { method: "DELETE" }),
  alertEvents: () => request<AlertEvent[]>("/api/alerts/events"),
  ackAlert: (id: number) => request(`/api/alerts/events/${id}/ack`, { method: "POST" }),
  settings: () => request<SettingsView>("/api/settings"),
  updateSettings: (changes: Partial<Preferences>) => request<Preferences>("/api/settings", json("PUT", changes)),
  runs: () => request<ProviderRun[]>("/api/collector/runs"),
  runCollector: (includeComparisons: boolean, comparisonCount = 1) =>
    request<{ ran: boolean; reason?: string; results: { route: string; status: string; message: string }[] }>(
      `/api/collector/run?include_comparisons=${includeComparisons}&comparison_count=${comparisonCount}`,
      { method: "POST" },
    ),
  serpapiAccount: () => request<Record<string, unknown>>("/api/provider/serpapi/account"),
  clearDemo: () => request("/api/demo", { method: "DELETE" }),
  promotions: () => request<Promotion[]>("/api/promotions"),
  addPromotion: (body: Record<string, unknown>) => request<Promotion>("/api/promotions", json("POST", body)),
  deletePromotion: (id: number) => request<void>(`/api/promotions/${id}`, { method: "DELETE" }),
  fees: () => request<Fee[]>("/api/fees"),
  addFee: (body: Record<string, unknown>) => request<Fee>("/api/fees", json("POST", body)),
  deleteFee: (id: number) => request<void>(`/api/fees/${id}`, { method: "DELETE" }),
  feeComparison: () => request<FeeComparison>("/api/fees/comparison"),
};

// --- Explore / routes / trips ------------------------------------------------

export interface Airport {
  code: string;
  city: string;
  name: string;
  country: string;
  tz?: string;
}

export interface ExploreDestination {
  name: string;
  country: string | null;
  airport_code: string;
  airport_name: string | null;
  start_date: string | null;
  end_date: string | null;
  price: Money;
  currency: string;
  airline: string | null;
  airline_code: string | null;
  stops: number | null;
  duration_minutes: number | null;
  thumbnail: string | null;
}

export type TripType = "one_way" | "round_trip";

export interface ExploreView {
  origin: string;
  status?: string;
  message?: string;
  snapshot: {
    id: number;
    trip_type: TripType;
    month: number;
    travel_duration: number;
    currency: string;
    passengers: number;
    fetched_at_utc: string;
  } | null;
  destinations: ExploreDestination[];
  next_refresh_utc: string | null;
  can_refresh: boolean;
}

export interface RouteFlight {
  flight: Flight;
  analysis: FlightAnalysis;
  observations: Observation[];
}

export interface RouteView {
  demo: boolean;
  origin: Airport | null;
  destination: Airport | null;
  date: string;
  trip: { id: number; kind: string; last_checked_utc: string | null } | null;
  flights: RouteFlight[];
  booking_links: BookingLink[];
}

export interface SearchOutcome {
  route: string;
  date: string;
  status: string;
  message: string;
  observations_created?: number;
}

export interface Trip {
  id: number;
  kind: "target" | "user";
  origin: Airport | null;
  destination: Airport | null;
  date: string;
  last_checked_utc: string | null;
  latest_price: Money | null;
  latest_currency: string | null;
  latest_flight_number: string | null;
}

function exploreQuery(tripType: TripType, month: number, duration: number) {
  return `trip_type=${tripType}&month=${month}&duration=${duration}`;
}

export const exploreApi = {
  airports: (q: string) => request<Airport[]>(`/api/airports?q=${encodeURIComponent(q)}`),
  explore: (t: TripType, month: number, duration: number) =>
    request<ExploreView>(`/api/explore?${exploreQuery(t, month, duration)}`),
  refresh: (t: TripType, month: number, duration: number) =>
    request<ExploreView>(`/api/explore/refresh?${exploreQuery(t, month, duration)}`, { method: "POST" }),
  route: (o: string, d: string, date: string) =>
    request<RouteView>(`/api/route?origin=${o}&destination=${d}&date=${date}`),
  searchRoute: (o: string, d: string, date: string) =>
    request<SearchOutcome>("/api/route/search", json("POST", { origin: o, destination: d, date })),
  trips: () => request<Trip[]>("/api/trips"),
  removeTrip: (id: number) => request<{ ok: boolean }>(`/api/trips/${id}`, { method: "DELETE" }),
};
