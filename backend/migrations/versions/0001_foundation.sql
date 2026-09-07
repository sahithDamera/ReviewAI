REVOKE ALL ON SCHEMA reviewflow FROM PUBLIC;

CREATE TABLE reviewflow.users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email varchar(320) NOT NULL UNIQUE CHECK (email = lower(email)),
    password_hash text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    is_verified boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE reviewflow.business_categories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug varchar(50) NOT NULL UNIQUE,
    name varchar(80) NOT NULL,
    display_order integer NOT NULL DEFAULT 0,
    is_active boolean NOT NULL DEFAULT true
);

CREATE TABLE reviewflow.experience_attributes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id uuid NOT NULL REFERENCES reviewflow.business_categories(id),
    slug varchar(50) NOT NULL,
    label varchar(80) NOT NULL,
    display_order integer NOT NULL DEFAULT 0,
    UNIQUE (category_id, slug)
);

CREATE TABLE reviewflow.businesses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id uuid NOT NULL UNIQUE REFERENCES reviewflow.users(id),
    name varchar(120) NOT NULL CHECK (length(trim(name)) > 0),
    category_id uuid NOT NULL REFERENCES reviewflow.business_categories(id),
    description varchar(500),
    logo_url varchar(2048),
    brand_tone varchar(20) NOT NULL DEFAULT 'friendly'
        CHECK (brand_tone IN ('casual','professional','friendly','luxury')),
    public_identifier varchar(64) NOT NULL UNIQUE CHECK (length(public_identifier) >= 22),
    status varchar(10) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','paused')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX businesses_category_idx ON reviewflow.businesses(category_id);

CREATE TABLE reviewflow.business_attributes (
    business_id uuid NOT NULL REFERENCES reviewflow.businesses(id) ON DELETE CASCADE,
    attribute_id uuid NOT NULL REFERENCES reviewflow.experience_attributes(id),
    enabled boolean NOT NULL DEFAULT true,
    display_order integer NOT NULL DEFAULT 0,
    PRIMARY KEY (business_id, attribute_id)
);

CREATE TABLE reviewflow.business_google_destinations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id uuid NOT NULL UNIQUE REFERENCES reviewflow.businesses(id) ON DELETE CASCADE,
    url varchar(2048) NOT NULL CHECK (url LIKE 'https://%'),
    validated_at timestamptz NOT NULL,
    owner_confirmed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE reviewflow.review_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id uuid NOT NULL REFERENCES reviewflow.businesses(id),
    token_hash varchar(64) NOT NULL UNIQUE CHECK (token_hash ~ '^[a-f0-9]{64}$'),
    rating smallint CHECK (rating BETWEEN 1 AND 5),
    selected_attributes jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(selected_attributes) = 'array'
            AND jsonb_array_length(selected_attributes) <= 5),
    customer_comment varchar(500),
    input_version integer NOT NULL DEFAULT 0 CHECK (input_version >= 0),
    generation_attempts integer NOT NULL DEFAULT 0 CHECK (generation_attempts >= 0),
    entry_source varchar(10) NOT NULL DEFAULT 'direct' CHECK (entry_source IN ('qr','direct')),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    completed_at timestamptz,
    CHECK (expires_at > created_at),
    UNIQUE (id, business_id)
);
CREATE INDEX review_sessions_business_created_idx ON reviewflow.review_sessions(business_id,created_at);
CREATE INDEX review_sessions_expiry_idx ON reviewflow.review_sessions(expires_at);

CREATE TABLE reviewflow.review_generations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES reviewflow.review_sessions(id) ON DELETE CASCADE,
    request_key varchar(100) NOT NULL,
    input_version integer NOT NULL CHECK (input_version >= 0),
    input_snapshot jsonb NOT NULL CHECK (jsonb_typeof(input_snapshot) = 'object'),
    status varchar(10) NOT NULL CHECK (status IN ('pending','succeeded','failed')),
    reviews jsonb,
    provider varchar(50) NOT NULL,
    model varchar(100) NOT NULL,
    prompt_version varchar(50) NOT NULL,
    input_tokens integer CHECK (input_tokens >= 0),
    output_tokens integer CHECK (output_tokens >= 0),
    latency_ms integer CHECK (latency_ms >= 0),
    error_code varchar(80),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (session_id, request_key),
    UNIQUE (id, session_id),
    CHECK (status <> 'succeeded' OR (reviews IS NOT NULL
        AND jsonb_typeof(reviews) = 'array' AND jsonb_array_length(reviews) = 3))
);
CREATE UNIQUE INDEX review_generations_one_pending_idx
    ON reviewflow.review_generations(session_id) WHERE status = 'pending';
CREATE INDEX review_generations_session_created_idx
    ON reviewflow.review_generations(session_id,created_at);

CREATE TABLE reviewflow.review_selections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL UNIQUE REFERENCES reviewflow.review_sessions(id) ON DELETE CASCADE,
    generation_id uuid,
    option_id varchar(1),
    source varchar(10) NOT NULL CHECK (source IN ('ai','manual')),
    final_text varchar(2000) NOT NULL CHECK (length(trim(final_text)) > 0),
    is_edited boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (generation_id, session_id)
        REFERENCES reviewflow.review_generations(id, session_id) ON DELETE CASCADE,
    CHECK ((source = 'manual' AND generation_id IS NULL AND option_id IS NULL)
        OR (source = 'ai' AND generation_id IS NOT NULL
            AND option_id IS NOT NULL AND option_id IN ('1','2','3')))
);

CREATE TABLE reviewflow.analytics_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id uuid NOT NULL REFERENCES reviewflow.businesses(id),
    session_id uuid,
    event_type varchar(40) NOT NULL CHECK (event_type IN (
        'QR_OPENED','RATING_SELECTED','ATTRIBUTES_SELECTED','AI_GENERATION_STARTED',
        'AI_GENERATION_COMPLETED','REVIEW_SELECTED','REVIEW_EDITED','COPY_CLICKED',
        'COPY_SUCCEEDED','GOOGLE_OPENED','SESSION_COMPLETED')),
    occurred_at timestamptz NOT NULL DEFAULT now(),
    dedupe_key varchar(150),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
    FOREIGN KEY (session_id, business_id)
        REFERENCES reviewflow.review_sessions(id, business_id) ON DELETE SET NULL (session_id),
    UNIQUE (business_id, dedupe_key)
);
CREATE INDEX analytics_events_business_time_type_idx
    ON reviewflow.analytics_events(business_id,occurred_at,event_type);
CREATE INDEX analytics_events_session_idx ON reviewflow.analytics_events(session_id);

CREATE TABLE reviewflow.analytics_daily (
    business_id uuid NOT NULL REFERENCES reviewflow.businesses(id),
    day date NOT NULL,
    sessions integer NOT NULL DEFAULT 0 CHECK (sessions >= 0),
    rated_sessions integer NOT NULL DEFAULT 0 CHECK (rated_sessions >= 0),
    generated_sessions integer NOT NULL DEFAULT 0 CHECK (generated_sessions >= 0),
    selected_sessions integer NOT NULL DEFAULT 0 CHECK (selected_sessions >= 0),
    manual_sessions integer NOT NULL DEFAULT 0 CHECK (manual_sessions >= 0),
    copied_sessions integer NOT NULL DEFAULT 0 CHECK (copied_sessions >= 0),
    google_handoff_sessions integer NOT NULL DEFAULT 0 CHECK (google_handoff_sessions >= 0),
    rating_sum integer NOT NULL DEFAULT 0 CHECK (rating_sum >= 0),
    rating_count integer NOT NULL DEFAULT 0 CHECK (rating_count >= 0),
    PRIMARY KEY (business_id, day),
    CHECK (rating_sum BETWEEN rating_count AND rating_count * 5)
);

REVOKE ALL ON ALL TABLES IN SCHEMA reviewflow FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA reviewflow REVOKE ALL ON TABLES FROM PUBLIC;
