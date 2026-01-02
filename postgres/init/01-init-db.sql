-- PostgreSQL Initialization Script for FAQ/RAG Application
-- This script runs when the PostgreSQL container is first created

-- Create extensions that might be useful for the application
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Set some performance-related settings
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET log_statement = 'all';
ALTER SYSTEM SET log_min_duration_statement = 1000;
ALTER SYSTEM SET log_checkpoints = on;
ALTER SYSTEM SET log_connections = on;
ALTER SYSTEM SET log_disconnections = on;

-- Optimize for the expected workload
ALTER SYSTEM SET effective_cache_size = '256MB';
ALTER SYSTEM SET shared_buffers = '64MB';
ALTER SYSTEM SET work_mem = '4MB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';

-- Connection settings
ALTER SYSTEM SET max_connections = 100;
ALTER SYSTEM SET idle_in_transaction_session_timeout = '10min';

-- Reload configuration
SELECT pg_reload_conf();

-- Grant necessary permissions to the application user
GRANT CONNECT ON DATABASE faq_production TO faq_user;
GRANT USAGE ON SCHEMA public TO faq_user;
GRANT CREATE ON SCHEMA public TO faq_user;