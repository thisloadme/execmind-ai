-- ============================================================
-- ExecMind Database Schema
-- Version: 2.0.0
-- ============================================================

-- Custom ENUM Types
CREATE TYPE user_role AS ENUM ('superadmin', 'admin', 'executive', 'viewer');
CREATE TYPE user_status AS ENUM ('active', 'inactive', 'locked');
CREATE TYPE kb_sensitivity AS ENUM ('public', 'internal', 'confidential', 'top_secret');
CREATE TYPE doc_status AS ENUM ('uploading', 'processing', 'indexed', 'failed', 'deleted');
CREATE TYPE message_role AS ENUM ('user', 'assistant', 'system');
CREATE TYPE audit_action AS ENUM (
    'login', 'logout', 'login_failed', 'password_change',
    'doc_upload', 'doc_delete', 'doc_update', 'doc_view',
    'collection_create', 'collection_delete',
    'user_create', 'user_update', 'user_deactivate',
    'chat_query', 'export_audit_log'
);

-- ============================================================
-- USERS
-- ============================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    position VARCHAR(255),
    unit VARCHAR(255),
    role user_role NOT NULL DEFAULT 'executive',
    status user_status NOT NULL DEFAULT 'active',
    failed_attempts SMALLINT DEFAULT 0,
    locked_until TIMESTAMPTZ,
    last_login_at TIMESTAMPTZ,
    last_login_ip INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_status ON users(status);

-- ============================================================
-- REFRESH TOKENS
-- ============================================================
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);

-- ============================================================
-- KNOWLEDGE BASE COLLECTIONS
-- ============================================================
CREATE TABLE kb_collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    sensitivity kb_sensitivity NOT NULL DEFAULT 'confidential',
    qdrant_name VARCHAR(255) UNIQUE NOT NULL,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_kb_collections_sensitivity ON kb_collections(sensitivity);

-- ============================================================
-- COLLECTION ACCESS CONTROL
-- ============================================================
CREATE TABLE collection_access (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID NOT NULL REFERENCES kb_collections(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role user_role,
    granted_by UUID REFERENCES users(id),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(collection_id, user_id),
    UNIQUE(collection_id, role)
);

CREATE INDEX idx_collection_access_collection_id ON collection_access(collection_id);
CREATE INDEX idx_collection_access_user_id ON collection_access(user_id);

-- ============================================================
-- DOCUMENTS
-- ============================================================
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID NOT NULL REFERENCES kb_collections(id),
    original_name VARCHAR(500) NOT NULL,
    stored_path TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    title VARCHAR(500),
    description TEXT,
    category VARCHAR(255),
    doc_date DATE,
    status doc_status NOT NULL DEFAULT 'uploading',
    chunk_count INTEGER DEFAULT 0,
    error_message TEXT,
    uploaded_by UUID REFERENCES users(id),
    indexed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_documents_collection_id ON documents(collection_id);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_created_at ON documents(created_at DESC);

-- ============================================================
-- CHAT SESSIONS
-- ============================================================
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    collection_id UUID REFERENCES kb_collections(id),
    title VARCHAR(500) NOT NULL DEFAULT 'New Chat',
    message_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX idx_chat_sessions_created_at ON chat_sessions(created_at DESC);

-- ============================================================
-- CHAT MESSAGES
-- ============================================================
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role message_role NOT NULL,
    content TEXT NOT NULL,
    sources JSONB DEFAULT '[]',
    tokens_used INTEGER,
    latency_ms INTEGER,
    feedback SMALLINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    attachments JSONB DEFAULT '[]'
);

CREATE INDEX idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX idx_chat_messages_created_at ON chat_messages(created_at DESC);

-- ============================================================
-- AUDIT LOGS (append-only)
-- ============================================================
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    action audit_action NOT NULL,
    resource VARCHAR(100),
    resource_id UUID,
    action_metadata JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource, resource_id);

-- ============================================================
-- SEED: Default superadmin user
-- Password: Admin123! (bcrypt hash)
-- ============================================================
INSERT INTO users (username, email, password_hash, full_name, role, status)
VALUES (
    'admin',
    'admin@execmind.local',
    '$2b$12$uiBFZT393990KzDkeP1Ceezk9okhsLOzv4vnrmjcR/C0ofBsOdu.y', -- Admin123!
    'System Administrator',
    'superadmin',
    'active'
);
