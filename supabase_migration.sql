-- Run this in your Supabase SQL Editor:
-- https://supabase.com/dashboard/project/mfuceucqjgyarlbbkgvv/sql

-- 1. Registered users table
CREATE TABLE IF NOT EXISTS users (
  user_id   BIGINT PRIMARY KEY,
  username  TEXT,
  first_name TEXT,
  registered_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Shared plans (collaborations between users)
CREATE TABLE IF NOT EXISTS shared_plans (
  id              SERIAL PRIMARY KEY,
  task_id         INT  REFERENCES tasks(id) ON DELETE CASCADE,
  owner_id        BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
  collaborator_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(task_id, collaborator_id)
);
