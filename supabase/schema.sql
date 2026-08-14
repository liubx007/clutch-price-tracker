create extension if not exists pgcrypto;

create table if not exists public.tracked_segments (
  id text primary key,
  make text not null,
  model text not null,
  priority integer not null default 0,
  notes text,
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.tracked_vehicles (
  vehicle_id bigint primary key,
  url text not null,
  source_segment_id text references public.tracked_segments(id),
  province text,
  year integer,
  make text,
  model text,
  trim text,
  mileage integer,
  exterior_color text,
  image_url text,
  purchase_status text,
  website_state text,
  visible_on_site boolean,
  current_disposition text,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  last_checked_at timestamptz,
  is_active boolean not null default true,
  last_snapshot jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.price_observations (
  id uuid primary key default gen_random_uuid(),
  vehicle_id bigint not null references public.tracked_vehicles(vehicle_id) on delete cascade,
  checked_at timestamptz not null,
  province text,
  price integer,
  admin_fee integer,
  subtotal_before_tax numeric,
  estimated_after_tax numeric,
  mileage integer,
  purchase_status text,
  website_state text,
  listing_type text,
  visible_on_site boolean,
  current_disposition text,
  check_status text not null default 'available',
  check_error text,
  raw jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (vehicle_id, checked_at)
);

create index if not exists idx_price_observations_vehicle_time
  on public.price_observations (vehicle_id, checked_at desc);

create table if not exists public.prediction_snapshots (
  id uuid primary key default gen_random_uuid(),
  vehicle_id bigint not null references public.tracked_vehicles(vehicle_id) on delete cascade,
  generated_at timestamptz not null default now(),
  recommendation text not null,
  score integer not null,
  confidence text not null,
  price_drop_probability_7d numeric,
  price_drop_probability_14d numeric,
  expected_drop_min integer,
  expected_drop_max integer,
  reasons jsonb not null default '[]'::jsonb,
  features jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_prediction_snapshots_vehicle_time
  on public.prediction_snapshots (vehicle_id, generated_at desc);

alter table public.tracked_segments enable row level security;
alter table public.tracked_vehicles enable row level security;
alter table public.price_observations enable row level security;
alter table public.prediction_snapshots enable row level security;

drop policy if exists "public read tracked segments" on public.tracked_segments;
drop policy if exists "public read tracked vehicles" on public.tracked_vehicles;
drop policy if exists "public read price observations" on public.price_observations;
drop policy if exists "public read prediction snapshots" on public.prediction_snapshots;

create policy "public read tracked segments"
  on public.tracked_segments for select
  using (true);

create policy "public read tracked vehicles"
  on public.tracked_vehicles for select
  using (true);

create policy "public read price observations"
  on public.price_observations for select
  using (true);

create policy "public read prediction snapshots"
  on public.prediction_snapshots for select
  using (true);
