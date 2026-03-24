-- ══════════════════════════════════════════════════════
--  SuperEye database schema
--  Run this entire file in Supabase SQL Editor once.
-- ══════════════════════════════════════════════════════

create table if not exists users (
  id            uuid primary key default gen_random_uuid(),
  username      text not null unique,
  is_online     boolean default false,
  last_seen     timestamptz,
  last_status   jsonb
);

create table if not exists tokens (
  id            uuid primary key default gen_random_uuid(),
  token_string  text not null unique,
  user_id       uuid references users(id) on delete cascade,
  role          text not null default 'user' check (role in ('user', 'admin')),
  revoked       boolean not null default false,
  created_at    timestamptz not null default now(),
  expires_at    timestamptz
);

create table if not exists commands (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid references users(id) on delete cascade,
  command       text not null check (command in ('stop', 'start')),
  issued_at     timestamptz not null default now(),
  acknowledged  boolean not null default false
);

-- Indexes for fast lookups
create index if not exists idx_tokens_string   on tokens(token_string);
create index if not exists idx_tokens_user     on tokens(user_id);
create index if not exists idx_commands_user   on commands(user_id, acknowledged);

-- Row Level Security: disable for service role (backend uses service key)
alter table users    disable row level security;
alter table tokens   disable row level security;
alter table commands disable row level security;
