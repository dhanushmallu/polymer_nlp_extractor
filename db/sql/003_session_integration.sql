-- ================================================================
-- Session Integration: Triggers and Functions
-- Version: 2.1
-- Purpose: Add session support triggers and functions (columns now in core schema)
-- ================================================================

-- Update the updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Ensure the trigger exists for research_papers
DROP TRIGGER IF EXISTS update_research_papers_updated_at ON research_papers;
CREATE TRIGGER update_research_papers_updated_at 
    BEFORE UPDATE ON research_papers 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Session activity tracking function (optional - can be added when session management is needed)
-- CREATE OR REPLACE FUNCTION update_session_activity() RETURNS TRIGGER AS $$
-- BEGIN
--     IF NEW.session_id IS NOT NULL THEN
--         UPDATE user_sessions SET last_activity = CURRENT_TIMESTAMP WHERE id = NEW.session_id;
--     END IF;
--     RETURN NEW;
-- END;
-- $$ language 'plpgsql';

-- User access logging function (optional - can be added when session management is needed)  
-- CREATE OR REPLACE FUNCTION log_user_access() RETURNS TRIGGER AS $$
-- BEGIN
--     IF NEW.user_id IS NOT NULL THEN
--         INSERT INTO user_access_logs (user_id, table_name, operation, timestamp)
--         VALUES (NEW.user_id, TG_TABLE_NAME, TG_OP, CURRENT_TIMESTAMP);
--     END IF;
--     RETURN NEW;
-- END;
-- $$ language 'plpgsql';
