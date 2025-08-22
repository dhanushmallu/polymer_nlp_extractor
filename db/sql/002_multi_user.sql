-- ================================================================
-- Multi-User Session Management Schema Extension
-- Version: 2.1 - Production Multi-User Support
-- Created: 2025-08-22
-- Purpose: Add production-ready multi-user and session management
-- ================================================================

-- ================================================================
-- 1. USER MANAGEMENT TABLES
-- ================================================================

-- User accounts and authentication (minimal for extraction service)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) UNIQUE NOT NULL,  -- External user identifier (from auth system)
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    display_name VARCHAR(255),
    organization VARCHAR(255),
    user_role VARCHAR(50) DEFAULT 'researcher' CHECK (user_role IN ('admin', 'researcher', 'guest')),
    storage_quota_gb DECIMAL(10,2) DEFAULT 10.0,
    max_concurrent_sessions INTEGER DEFAULT 3,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_users_user_id ON users(user_id);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(is_active);
CREATE INDEX idx_users_role ON users(user_role);

-- ================================================================
-- 2. USER SESSION MANAGEMENT
-- ================================================================

-- User sessions for multi-user extraction workflows
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    session_name VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('creating', 'active', 'processing', 'idle', 'completing', 'completed', 'failed', 'expired', 'cleanup')),
    storage_prefix VARCHAR(500),  -- User-isolated storage namespace
    resource_requirements JSONB,  -- ResourceRequirements serialized
    allocated_resources JSONB,    -- Current resource allocation
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    completed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX idx_user_sessions_status ON user_sessions(status);
CREATE INDEX idx_user_sessions_created ON user_sessions(created_at);
CREATE INDEX idx_user_sessions_expires ON user_sessions(expires_at);
CREATE INDEX idx_user_sessions_last_activity ON user_sessions(last_activity);

-- ================================================================
-- 3. SESSION-AWARE EXTRACTION SESSIONS (Enhanced)
-- ================================================================

-- Enhance existing extraction_sessions table with user context
ALTER TABLE extraction_sessions ADD COLUMN IF NOT EXISTS user_session_id UUID REFERENCES user_sessions(id) ON DELETE SET NULL;
ALTER TABLE extraction_sessions ADD COLUMN IF NOT EXISTS user_id VARCHAR(255) REFERENCES users(user_id) ON DELETE SET NULL;
ALTER TABLE extraction_sessions ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT 1 CHECK (priority >= 1 AND priority <= 5);

-- Add indexes for user-aware extraction sessions
CREATE INDEX IF NOT EXISTS idx_extraction_sessions_user_session ON extraction_sessions(user_session_id);
CREATE INDEX IF NOT EXISTS idx_extraction_sessions_user_id ON extraction_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_extraction_sessions_priority ON extraction_sessions(priority);

-- ================================================================
-- 4. RESOURCE ALLOCATION TRACKING
-- ================================================================

-- Resource allocation and usage tracking
CREATE TABLE resource_allocations (
    id SERIAL PRIMARY KEY,
    user_session_id UUID NOT NULL REFERENCES user_sessions(id) ON DELETE CASCADE,
    resource_type VARCHAR(50) NOT NULL,  -- 'memory', 'cpu', 'storage', 'model', 'gpu'
    resource_name VARCHAR(100),          -- Specific resource identifier
    allocated_amount DECIMAL(10,4),      -- Amount allocated (GB, cores, etc.)
    allocated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deallocated_at TIMESTAMP,
    peak_usage DECIMAL(10,4),            -- Peak usage during allocation
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'deallocated', 'expired'))
);

CREATE INDEX idx_resource_allocations_session ON resource_allocations(user_session_id);
CREATE INDEX idx_resource_allocations_type ON resource_allocations(resource_type);
CREATE INDEX idx_resource_allocations_status ON resource_allocations(status);
CREATE INDEX idx_resource_allocations_allocated ON resource_allocations(allocated_at);

-- ================================================================
-- 5. USER STORAGE TRACKING
-- ================================================================

-- Track user storage usage for quota management
CREATE TABLE user_storage_usage (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    storage_key VARCHAR(500) NOT NULL,    -- Storage key/path
    file_size_bytes BIGINT NOT NULL,
    storage_backend VARCHAR(50),          -- 'local', 'appwrite', 's3'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_user_storage_user_id ON user_storage_usage(user_id);
CREATE INDEX idx_user_storage_key ON user_storage_usage(storage_key);
CREATE INDEX idx_user_storage_backend ON user_storage_usage(storage_backend);
CREATE INDEX idx_user_storage_created ON user_storage_usage(created_at);
CREATE INDEX idx_user_storage_accessed ON user_storage_usage(last_accessed);

-- ================================================================
-- 6. SESSION METRICS AND PERFORMANCE
-- ================================================================

-- Session-level performance metrics
CREATE TABLE session_metrics (
    id SERIAL PRIMARY KEY,
    user_session_id UUID NOT NULL REFERENCES user_sessions(id) ON DELETE CASCADE,
    metric_type VARCHAR(50) NOT NULL,     -- 'extraction', 'resource_usage', 'performance'
    metric_name VARCHAR(100) NOT NULL,    -- Specific metric identifier
    metric_value DECIMAL(15,6),           -- Numeric metric value
    metric_unit VARCHAR(20),              -- Unit of measurement
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_session_metrics_session ON session_metrics(user_session_id);
CREATE INDEX idx_session_metrics_type ON session_metrics(metric_type);
CREATE INDEX idx_session_metrics_name ON session_metrics(metric_name);
CREATE INDEX idx_session_metrics_recorded ON session_metrics(recorded_at);

-- ================================================================
-- 7. USER ACCESS LOGS
-- ================================================================

-- User access and activity logging
CREATE TABLE user_access_logs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    action VARCHAR(100) NOT NULL,         -- 'login', 'logout', 'session_create', 'extraction_start', etc.
    resource_accessed VARCHAR(255),       -- Session ID, paper ID, etc.
    ip_address INET,
    user_agent TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_user_access_logs_user_id ON user_access_logs(user_id);
CREATE INDEX idx_user_access_logs_action ON user_access_logs(action);
CREATE INDEX idx_user_access_logs_timestamp ON user_access_logs(timestamp);
CREATE INDEX idx_user_access_logs_success ON user_access_logs(success);

-- ================================================================
-- 8. ENHANCE EXISTING TABLES FOR USER AWARENESS
-- ================================================================

-- Note: User tracking columns for research_papers are now in core schema (001_core.sql)
-- Creating only indexes that might be missing:
CREATE INDEX IF NOT EXISTS idx_research_papers_uploaded_by ON research_papers(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_research_papers_access_level ON research_papers(access_level);

-- Add user tracking to datasets
ALTER TABLE datasets ADD COLUMN IF NOT EXISTS created_by VARCHAR(255) REFERENCES users(user_id) ON DELETE SET NULL;
ALTER TABLE datasets ADD COLUMN IF NOT EXISTS access_level VARCHAR(20) DEFAULT 'private' CHECK (access_level IN ('private', 'shared', 'public'));

CREATE INDEX IF NOT EXISTS idx_datasets_created_by ON datasets(created_by);
CREATE INDEX IF NOT EXISTS idx_datasets_access_level ON datasets(access_level);

-- Add user context to entities (via session tracking)
-- Note: entities already link to extraction_sessions, which now link to user_sessions

-- ================================================================
-- 9. SYSTEM CONFIGURATION
-- ================================================================

-- System-wide configuration for multi-user management
CREATE TABLE system_config (
    id SERIAL PRIMARY KEY,
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value TEXT NOT NULL,
    config_type VARCHAR(20) DEFAULT 'string' CHECK (config_type IN ('string', 'integer', 'decimal', 'boolean', 'json')),
    description TEXT,
    is_public BOOLEAN DEFAULT false,      -- Whether config is visible to non-admin users
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(255)
);

CREATE INDEX idx_system_config_key ON system_config(config_key);
CREATE INDEX idx_system_config_public ON system_config(is_public);

-- Insert default configuration values
INSERT INTO system_config (config_key, config_value, config_type, description, is_public) VALUES
('max_concurrent_sessions_global', '50', 'integer', 'Global maximum concurrent sessions across all users', false),
('max_concurrent_sessions_per_user', '3', 'integer', 'Maximum concurrent sessions per user', true),
('session_timeout_minutes', '60', 'integer', 'Default session timeout in minutes', true),
('resource_sharing_strategy', 'hybrid', 'string', 'Default resource sharing strategy', false),
('user_storage_isolation', 'true', 'boolean', 'Enable user storage isolation', false),
('default_storage_quota_gb', '10.0', 'decimal', 'Default storage quota per user in GB', true),
('cleanup_interval_minutes', '15', 'integer', 'Session cleanup interval in minutes', false),
('enable_guest_access', 'false', 'boolean', 'Allow guest user access', true),
('max_extraction_time_hours', '8', 'integer', 'Maximum extraction time per session', true);

-- ================================================================
-- 10. VIEWS FOR CONVENIENCE QUERIES
-- ================================================================

-- Active user sessions with resource usage
CREATE VIEW active_user_sessions AS
SELECT 
    us.id,
    us.user_id,
    u.username,
    u.display_name,
    us.session_name,
    us.status,
    us.storage_prefix,
    us.created_at,
    us.last_activity,
    us.expires_at,
    us.resource_requirements,
    us.allocated_resources,
    COUNT(es.id) as extraction_count,
    COALESCE(SUM(sts.file_size_bytes), 0) as storage_used_bytes
FROM user_sessions us
JOIN users u ON us.user_id = u.user_id
LEFT JOIN extraction_sessions es ON us.id = es.user_session_id
LEFT JOIN user_storage_usage sts ON us.user_id = sts.user_id
WHERE us.status IN ('active', 'processing', 'idle')
GROUP BY us.id, u.username, u.display_name;

-- User resource utilization summary
CREATE VIEW user_resource_summary AS
SELECT 
    u.user_id,
    u.username,
    u.display_name,
    u.storage_quota_gb,
    u.max_concurrent_sessions,
    COUNT(DISTINCT us.id) as active_sessions,
    COALESCE(SUM(sts.file_size_bytes), 0) / (1024.0^3) as storage_used_gb,
    u.storage_quota_gb - COALESCE(SUM(sts.file_size_bytes), 0) / (1024.0^3) as storage_remaining_gb,
    COUNT(DISTINCT es.id) as total_extractions,
    MAX(us.last_activity) as last_activity
FROM users u
LEFT JOIN user_sessions us ON u.user_id = us.user_id AND us.status IN ('active', 'processing', 'idle')
LEFT JOIN user_storage_usage sts ON u.user_id = sts.user_id
LEFT JOIN extraction_sessions es ON u.user_id = es.user_id
WHERE u.is_active = true
GROUP BY u.user_id, u.username, u.display_name, u.storage_quota_gb, u.max_concurrent_sessions;

-- System capacity overview
CREATE VIEW system_capacity_view AS
SELECT 
    COUNT(DISTINCT us.id) as total_active_sessions,
    COUNT(DISTINCT us.user_id) as active_users,
    COUNT(DISTINCT CASE WHEN us.status = 'processing' THEN us.id END) as processing_sessions,
    SUM(CASE WHEN ra.resource_type = 'memory' THEN ra.allocated_amount ELSE 0 END) as total_memory_allocated_gb,
    SUM(CASE WHEN ra.resource_type = 'cpu' THEN ra.allocated_amount ELSE 0 END) as total_cpu_allocated_cores,
    SUM(sts.file_size_bytes) / (1024.0^3) as total_storage_used_gb
FROM user_sessions us
LEFT JOIN resource_allocations ra ON us.id = ra.user_session_id AND ra.status = 'active'
LEFT JOIN user_storage_usage sts ON us.user_id = sts.user_id
WHERE us.status IN ('active', 'processing', 'idle');

-- ================================================================
-- 11. FUNCTIONS FOR COMMON OPERATIONS
-- ================================================================

-- Function to check if user can create new session
CREATE OR REPLACE FUNCTION can_user_create_session(p_user_id VARCHAR(255))
RETURNS BOOLEAN AS $$
DECLARE
    user_max_sessions INTEGER;
    current_sessions INTEGER;
    global_max_sessions INTEGER;
    current_global_sessions INTEGER;
BEGIN
    -- Get user's session limit
    SELECT max_concurrent_sessions INTO user_max_sessions
    FROM users WHERE user_id = p_user_id AND is_active = true;
    
    IF user_max_sessions IS NULL THEN
        RETURN false; -- User not found or inactive
    END IF;
    
    -- Count user's current active sessions
    SELECT COUNT(*) INTO current_sessions
    FROM user_sessions 
    WHERE user_id = p_user_id AND status IN ('active', 'processing', 'idle');
    
    -- Check user limit
    IF current_sessions >= user_max_sessions THEN
        RETURN false;
    END IF;
    
    -- Get global session limit
    SELECT config_value::INTEGER INTO global_max_sessions
    FROM system_config WHERE config_key = 'max_concurrent_sessions_global';
    
    -- Count total active sessions
    SELECT COUNT(*) INTO current_global_sessions
    FROM user_sessions WHERE status IN ('active', 'processing', 'idle');
    
    -- Check global limit
    IF current_global_sessions >= global_max_sessions THEN
        RETURN false;
    END IF;
    
    RETURN true;
END;
$$ LANGUAGE plpgsql;

-- Function to get user storage usage
CREATE OR REPLACE FUNCTION get_user_storage_usage(p_user_id VARCHAR(255))
RETURNS TABLE(
    storage_used_gb DECIMAL(10,4),
    storage_quota_gb DECIMAL(10,2),
    storage_remaining_gb DECIMAL(10,4),
    file_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COALESCE(SUM(sts.file_size_bytes), 0) / (1024.0^3)::DECIMAL(10,4) as storage_used_gb,
        u.storage_quota_gb,
        u.storage_quota_gb - COALESCE(SUM(sts.file_size_bytes), 0) / (1024.0^3)::DECIMAL(10,4) as storage_remaining_gb,
        COUNT(sts.id) as file_count
    FROM users u
    LEFT JOIN user_storage_usage sts ON u.user_id = sts.user_id
    WHERE u.user_id = p_user_id
    GROUP BY u.user_id, u.storage_quota_gb;
END;
$$ LANGUAGE plpgsql;

-- ================================================================
-- 12. TRIGGERS FOR AUTOMATIC MAINTENANCE
-- ================================================================

-- Trigger to update last_activity on user_sessions
CREATE OR REPLACE FUNCTION update_session_activity()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_activity = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_user_session_activity
    BEFORE UPDATE ON user_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_session_activity();

-- Trigger to log user access
CREATE OR REPLACE FUNCTION log_user_access()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO user_access_logs (user_id, action, resource_accessed)
    VALUES (
        NEW.user_id,
        CASE 
            WHEN TG_OP = 'INSERT' THEN 'session_create'
            WHEN TG_OP = 'UPDATE' AND OLD.status != NEW.status THEN 'session_status_change'
            ELSE 'session_update'
        END,
        NEW.id::TEXT
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER log_user_session_access
    AFTER INSERT OR UPDATE ON user_sessions
    FOR EACH ROW
    EXECUTE FUNCTION log_user_access();

-- ================================================================
-- 13. CLEANUP POLICIES
-- ================================================================

-- Create a cleanup function for expired sessions
CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    cleanup_count INTEGER := 0;
BEGIN
    -- Update expired sessions
    UPDATE user_sessions 
    SET status = 'expired'
    WHERE status IN ('active', 'idle') 
    AND expires_at < CURRENT_TIMESTAMP;
    
    GET DIAGNOSTICS cleanup_count = ROW_COUNT;
    
    -- Deallocate resources for expired sessions
    UPDATE resource_allocations
    SET status = 'expired', deallocated_at = CURRENT_TIMESTAMP
    WHERE user_session_id IN (
        SELECT id FROM user_sessions WHERE status = 'expired'
    ) AND status = 'active';
    
    RETURN cleanup_count;
END;
$$ LANGUAGE plpgsql;

-- ================================================================
-- 14. INDEXES FOR PERFORMANCE
-- ================================================================

-- Additional composite indexes for common multi-user queries
CREATE INDEX idx_user_sessions_user_status ON user_sessions(user_id, status);
CREATE INDEX idx_user_sessions_status_expires ON user_sessions(status, expires_at);
CREATE INDEX idx_extraction_sessions_user_created ON extraction_sessions(user_id, created_at);
CREATE INDEX idx_resource_allocations_session_type ON resource_allocations(user_session_id, resource_type);
CREATE INDEX idx_user_storage_user_created ON user_storage_usage(user_id, created_at);

-- ================================================================
-- END OF MULTI-USER SESSION MANAGEMENT SCHEMA
-- ================================================================
