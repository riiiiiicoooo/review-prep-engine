-- Review Prep Engine Initial Schema
-- Creates households, portfolios, briefings, engagement scoring, and meeting history

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "jsonb_utils";

-- ============================================================================
-- ENUM TYPES
-- ============================================================================

CREATE TYPE engagement_cohort AS ENUM ('at_risk', 'growth', 'core', 'premier');
CREATE TYPE action_status AS ENUM ('pending', 'in_progress', 'completed', 'deferred');
CREATE TYPE meeting_type AS ENUM ('quarterly_review', 'annual_planning', 'rebalance', 'tax_planning', 'estate_planning', 'ad_hoc');
CREATE TYPE relationship_type AS ENUM ('primary', 'spouse', 'dependent', 'poc', 'beneficiary');
CREATE TYPE account_type AS ENUM ('joint_taxable', 'individual_ira', 'sep_ira', 'joint_401k', 'trust', 'custodial', 'other');
CREATE TYPE advisor_role AS ENUM ('advisor', 'compliance', 'admin');

-- ============================================================================
-- USERS & ORGANIZATIONS
-- ============================================================================

CREATE TABLE organizations (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL,
  crm_system TEXT NOT NULL, -- 'salesforce', 'hubspot', 'pipedrive'
  custodian_systems TEXT[] NOT NULL, -- ['schwab', 'fidelity', 'interactive_brokers']
  timezone TEXT DEFAULT 'America/New_York',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE advisors (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL, -- Auth provider user ID (Supabase auth)
  email TEXT NOT NULL UNIQUE,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  role advisor_role NOT NULL DEFAULT 'advisor',
  phone TEXT,
  timezone TEXT,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(organization_id, email)
);

CREATE INDEX advisors_organization_id ON advisors(organization_id);
CREATE INDEX advisors_user_id ON advisors(user_id);

-- ============================================================================
-- HOUSEHOLDS & MEMBERS
-- ============================================================================

CREATE TABLE households (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  crm_id TEXT NOT NULL, -- External CRM ID (Salesforce Account.Id)
  household_name TEXT NOT NULL,
  primary_contact_name TEXT,
  email TEXT,
  phone TEXT,
  address_line1 TEXT,
  address_line2 TEXT,
  city TEXT,
  state TEXT,
  zip_code TEXT,
  country TEXT DEFAULT 'USA',
  annual_review_month INTEGER, -- 1-12, NULL if ad-hoc
  assigned_advisor_id UUID REFERENCES advisors(id) ON DELETE SET NULL,
  assigned_advisor_secondary_id UUID REFERENCES advisors(id) ON DELETE SET NULL,
  aum_usd DECIMAL(15, 2), -- Assets under management
  engagement_score INTEGER DEFAULT 50, -- 0-100
  engagement_cohort engagement_cohort DEFAULT 'growth',
  last_review_date DATE,
  next_review_date DATE,
  attrition_risk BOOLEAN DEFAULT FALSE,
  attrition_risk_score INTEGER DEFAULT 0, -- 0-100, higher = more at risk
  custom_metadata JSONB, -- Store CRM custom fields
  crm_last_sync TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX households_organization_id ON households(organization_id);
CREATE INDEX households_crm_id ON households(crm_id);
CREATE INDEX households_assigned_advisor_id ON households(assigned_advisor_id);
CREATE INDEX households_engagement_cohort ON households(engagement_cohort);
CREATE INDEX households_attrition_risk ON households(attrition_risk) WHERE attrition_risk = TRUE;
CREATE INDEX households_next_review ON households(next_review_date);

CREATE TABLE household_members (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  household_id UUID NOT NULL REFERENCES households(id) ON DELETE CASCADE,
  crm_id TEXT, -- External CRM ID (Salesforce Contact.Id)
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  relationship relationship_type NOT NULL,
  email TEXT,
  phone TEXT,
  date_of_birth DATE,
  ssn_encrypted TEXT, -- Store encrypted for compliance
  is_decision_maker BOOLEAN DEFAULT FALSE,
  custom_metadata JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX household_members_household_id ON household_members(household_id);
CREATE INDEX household_members_crm_id ON household_members(crm_id);
CREATE INDEX household_members_relationship ON household_members(relationship);

-- ============================================================================
-- PORTFOLIOS & ACCOUNTS
-- ============================================================================

CREATE TABLE accounts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  household_id UUID NOT NULL REFERENCES households(id) ON DELETE CASCADE,
  custodian_account_id TEXT NOT NULL, -- Schwab, Fidelity account number
  custodian_name TEXT NOT NULL, -- 'schwab', 'fidelity', 'interactive_brokers'
  account_type account_type NOT NULL,
  account_name TEXT,
  account_number_last_4 TEXT,
  owner_names TEXT, -- Comma-separated primary owners
  total_value_usd DECIMAL(15, 2),
  total_cost_basis_usd DECIMAL(15, 2),
  unrealized_gain_loss_usd DECIMAL(15, 2),
  ytd_gain_loss_pct DECIMAL(6, 3),
  cash_balance_usd DECIMAL(15, 2),
  last_update TIMESTAMP WITH TIME ZONE,
  custodian_last_sync TIMESTAMP WITH TIME ZONE,
  metadata JSONB, -- Store custodian-specific fields
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(household_id, custodian_account_id)
);

CREATE INDEX accounts_household_id ON accounts(household_id);
CREATE INDEX accounts_custodian_name ON accounts(custodian_name);
CREATE INDEX accounts_last_update ON accounts(last_update DESC);

CREATE TABLE positions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  symbol TEXT NOT NULL,
  position_name TEXT NOT NULL,
  position_type TEXT NOT NULL, -- 'equity', 'bond', 'mutual_fund', 'etf', 'option', 'cash'
  quantity DECIMAL(20, 8),
  current_price_usd DECIMAL(15, 6),
  current_value_usd DECIMAL(15, 2),
  cost_basis_usd DECIMAL(15, 2),
  cost_basis_per_share DECIMAL(15, 6),
  unrealized_gain_loss_usd DECIMAL(15, 2),
  unrealized_gain_loss_pct DECIMAL(8, 3),
  ytd_return_pct DECIMAL(8, 3),
  sector TEXT,
  asset_class TEXT, -- 'domestic_equity', 'intl_equity', 'fixed_income', 'commodities', 'alternatives'
  weight_pct DECIMAL(6, 3), -- Percentage of account value
  last_price_update TIMESTAMP WITH TIME ZONE,
  metadata JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX positions_account_id ON positions(account_id);
CREATE INDEX positions_symbol ON positions(symbol);
CREATE INDEX positions_asset_class ON positions(asset_class);
CREATE INDEX positions_sector ON positions(sector);
CREATE INDEX positions_last_price_update ON positions(last_price_update DESC);

CREATE TABLE position_history (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  position_id UUID NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  symbol TEXT NOT NULL,
  quantity_before DECIMAL(20, 8),
  quantity_after DECIMAL(20, 8),
  price_before DECIMAL(15, 6),
  price_after DECIMAL(15, 6),
  value_before DECIMAL(15, 2),
  value_after DECIMAL(15, 2),
  change_type TEXT NOT NULL, -- 'add', 'reduce', 'sell', 'dividend', 'split'
  transaction_date DATE,
  recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX position_history_position_id ON position_history(position_id);
CREATE INDEX position_history_account_id ON position_history(account_id);
CREATE INDEX position_history_symbol ON position_history(symbol);

-- ============================================================================
-- BRIEFINGS
-- ============================================================================

CREATE TABLE briefings (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  household_id UUID NOT NULL REFERENCES households(id) ON DELETE CASCADE,
  review_meeting_id UUID, -- Will reference meeting once created
  created_by_advisor_id UUID REFERENCES advisors(id) ON DELETE SET NULL,
  briefing_content JSONB NOT NULL, -- {title, summary, sections: {household, portfolio, changes, action_items, conversation_starters}}
  briefing_html TEXT, -- Rendered HTML version
  briefing_markdown TEXT, -- Markdown version for reference
  portfolio_summary JSONB, -- {total_aum, account_count, asset_allocation, performance}
  position_changes JSONB, -- [{symbol, change_type, quantity_delta, value_delta, rationale}]
  engagement_score_snapshot INTEGER,
  engagement_cohort_snapshot engagement_cohort,
  attrition_risk_snapshot BOOLEAN,
  conversation_starters TEXT[],
  recommended_actions JSONB, -- [{action, priority, estimated_time}]
  advisor_email_sent BOOLEAN DEFAULT FALSE,
  advisor_email_sent_at TIMESTAMP WITH TIME ZONE,
  briefing_accessed BOOLEAN DEFAULT FALSE,
  briefing_accessed_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX briefings_household_id ON briefings(household_id);
CREATE INDEX briefings_created_by_advisor_id ON briefings(created_by_advisor_id);
CREATE INDEX briefings_created_at ON briefings(created_at DESC);
CREATE INDEX briefings_advisor_email_sent ON briefings(advisor_email_sent);

-- ============================================================================
-- ACTION ITEMS
-- ============================================================================

CREATE TABLE action_items (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  household_id UUID NOT NULL REFERENCES households(id) ON DELETE CASCADE,
  briefing_id UUID REFERENCES briefings(id) ON DELETE SET NULL,
  meeting_id UUID, -- Reference to meeting once available
  assigned_to_advisor_id UUID NOT NULL REFERENCES advisors(id) ON DELETE RESTRICT,
  title TEXT NOT NULL,
  description TEXT,
  status action_status DEFAULT 'pending',
  priority INTEGER DEFAULT 2, -- 1=critical, 2=high, 3=normal, 4=low
  due_date DATE,
  follow_up_date DATE,
  completed_date DATE,
  linked_position_id UUID REFERENCES positions(id) ON DELETE SET NULL,
  category TEXT, -- 'rebalance', 'tax_loss_harvest', 'contribution', 'review_action', 'other'
  metadata JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX action_items_household_id ON action_items(household_id);
CREATE INDEX action_items_assigned_to_advisor_id ON action_items(assigned_to_advisor_id);
CREATE INDEX action_items_status ON action_items(status);
CREATE INDEX action_items_due_date ON action_items(due_date);
CREATE INDEX action_items_priority ON action_items(priority);

-- ============================================================================
-- ENGAGEMENT SCORING
-- ============================================================================

CREATE TABLE engagement_scores (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  household_id UUID NOT NULL REFERENCES households(id) ON DELETE CASCADE,
  score_date DATE NOT NULL,
  overall_score INTEGER NOT NULL, -- 0-100
  cohort engagement_cohort NOT NULL,
  meeting_frequency_score INTEGER, -- Component scores for transparency
  portfolio_activity_score INTEGER,
  attrition_risk_delta INTEGER, -- Change in risk since last period
  communication_sentiment_score INTEGER,
  market_performance_score INTEGER,
  notes TEXT,
  calculation_metadata JSONB, -- Store calculation details for audit
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX engagement_scores_household_id ON engagement_scores(household_id);
CREATE INDEX engagement_scores_score_date ON engagement_scores(score_date DESC);
CREATE INDEX engagement_scores_cohort ON engagement_scores(cohort);

CREATE TABLE engagement_score_history (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  household_id UUID NOT NULL REFERENCES households(id) ON DELETE CASCADE,
  score_90d_ago INTEGER,
  score_180d_ago INTEGER,
  score_1y_ago INTEGER,
  cohort_90d_ago engagement_cohort,
  cohort_180d_ago engagement_cohort,
  cohort_1y_ago engagement_cohort,
  trend TEXT, -- 'improving', 'stable', 'declining'
  calculated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX engagement_score_history_household_id ON engagement_score_history(household_id);

-- ============================================================================
-- MEETINGS & NOTES
-- ============================================================================

CREATE TABLE meetings (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  household_id UUID NOT NULL REFERENCES households(id) ON DELETE CASCADE,
  meeting_type meeting_type NOT NULL,
  scheduled_date TIMESTAMP WITH TIME ZONE NOT NULL,
  completed_date TIMESTAMP WITH TIME ZONE,
  advisor_id UUID NOT NULL REFERENCES advisors(id) ON DELETE RESTRICT,
  attendee_names TEXT[], -- Names of people who attended
  location TEXT, -- 'in_person', 'video_call', 'phone'
  duration_minutes INTEGER,
  briefing_id UUID REFERENCES briefings(id) ON DELETE SET NULL,
  notes TEXT,
  topics_discussed TEXT[],
  action_items_count INTEGER DEFAULT 0,
  sentiment TEXT, -- 'positive', 'neutral', 'concerned'
  nps_score INTEGER, -- 0-10 if collected
  follow_up_needed BOOLEAN DEFAULT FALSE,
  metadata JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX meetings_household_id ON meetings(household_id);
CREATE INDEX meetings_advisor_id ON meetings(advisor_id);
CREATE INDEX meetings_scheduled_date ON meetings(scheduled_date DESC);
CREATE INDEX meetings_completed_date ON meetings(completed_date DESC);
CREATE INDEX meetings_sentiment ON meetings(sentiment);

CREATE TABLE meeting_notes (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  meeting_id UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
  note_type TEXT NOT NULL, -- 'portfolio', 'life_event', 'concern', 'opportunity', 'action_item'
  content TEXT NOT NULL,
  author_advisor_id UUID NOT NULL REFERENCES advisors(id) ON DELETE RESTRICT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX meeting_notes_meeting_id ON meeting_notes(meeting_id);
CREATE INDEX meeting_notes_author_advisor_id ON meeting_notes(author_advisor_id);

-- ============================================================================
-- SYNC LOGS & AUDIT TRAILS
-- ============================================================================

CREATE TABLE sync_logs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  sync_type TEXT NOT NULL, -- 'salesforce_sync', 'schwab_sync', 'fidelity_sync', 'briefing_generation'
  status TEXT NOT NULL, -- 'success', 'partial', 'failed'
  records_processed INTEGER,
  records_failed INTEGER,
  error_message TEXT,
  started_at TIMESTAMP WITH TIME ZONE,
  completed_at TIMESTAMP WITH TIME ZONE,
  metadata JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX sync_logs_organization_id ON sync_logs(organization_id);
CREATE INDEX sync_logs_sync_type ON sync_logs(sync_type);
CREATE INDEX sync_logs_status ON sync_logs(status);

CREATE TABLE audit_logs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  actor_advisor_id UUID REFERENCES advisors(id) ON DELETE SET NULL,
  action TEXT NOT NULL, -- 'view_briefing', 'edit_household', 'export_data', 'send_email'
  resource_type TEXT NOT NULL, -- 'household', 'briefing', 'meeting', 'action_item'
  resource_id UUID NOT NULL,
  changes JSONB, -- For edit actions, store what changed
  ip_address INET,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX audit_logs_organization_id ON audit_logs(organization_id);
CREATE INDEX audit_logs_actor_advisor_id ON audit_logs(actor_advisor_id);
CREATE INDEX audit_logs_resource_type ON audit_logs(resource_type);
CREATE INDEX audit_logs_created_at ON audit_logs(created_at DESC);

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE households ENABLE ROW LEVEL SECURITY;
ALTER TABLE household_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE position_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE briefings ENABLE ROW LEVEL SECURITY;
ALTER TABLE action_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE engagement_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE meetings ENABLE ROW LEVEL SECURITY;
ALTER TABLE meeting_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE advisors ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Helper function to get current user ID
CREATE OR REPLACE FUNCTION auth.current_user_id() RETURNS UUID AS $$
  SELECT auth.uid()
$$ LANGUAGE SQL SECURITY DEFINER;

-- Helper function to get advisor role
CREATE OR REPLACE FUNCTION get_advisor_role(user_id UUID)
RETURNS advisor_role AS $$
  SELECT role FROM advisors WHERE user_id = $1 LIMIT 1
$$ LANGUAGE SQL SECURITY DEFINER;

-- ============================================================================
-- RLS POLICIES: ADVISORS
-- ============================================================================

-- Advisors can see themselves and other advisors in same organization
CREATE POLICY advisors_own_record ON advisors
  FOR SELECT
  USING (user_id = auth.uid());

CREATE POLICY advisors_see_same_org ON advisors
  FOR SELECT
  USING (
    organization_id IN (
      SELECT organization_id FROM advisors WHERE user_id = auth.uid()
    )
  );

-- ============================================================================
-- RLS POLICIES: HOUSEHOLDS (Core enforcement)
-- ============================================================================

-- Advisors see households assigned to them OR if they have admin/compliance role
CREATE POLICY households_advisor_access ON households
  FOR SELECT
  USING (
    assigned_advisor_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
    OR assigned_advisor_secondary_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
    OR (SELECT role FROM advisors WHERE user_id = auth.uid()) IN ('admin', 'compliance')
  );

CREATE POLICY households_insert ON households
  FOR INSERT
  WITH CHECK (
    (SELECT role FROM advisors WHERE user_id = auth.uid()) = 'admin'
  );

CREATE POLICY households_update_own ON households
  FOR UPDATE
  USING (
    assigned_advisor_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
    OR (SELECT role FROM advisors WHERE user_id = auth.uid()) = 'admin'
  );

-- ============================================================================
-- RLS POLICIES: CASCADING CHILDREN
-- ============================================================================

-- Household members inherit household visibility
CREATE POLICY household_members_access ON household_members
  FOR SELECT
  USING (
    household_id IN (
      SELECT id FROM households WHERE
        assigned_advisor_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
        OR assigned_advisor_secondary_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
        OR (SELECT role FROM advisors WHERE user_id = auth.uid()) IN ('admin', 'compliance')
    )
  );

-- Accounts inherit household visibility
CREATE POLICY accounts_access ON accounts
  FOR SELECT
  USING (
    household_id IN (
      SELECT id FROM households WHERE
        assigned_advisor_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
        OR assigned_advisor_secondary_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
        OR (SELECT role FROM advisors WHERE user_id = auth.uid()) IN ('admin', 'compliance')
    )
  );

-- Positions inherit account visibility
CREATE POLICY positions_access ON positions
  FOR SELECT
  USING (
    account_id IN (
      SELECT id FROM accounts WHERE household_id IN (
        SELECT id FROM households WHERE
          assigned_advisor_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
          OR assigned_advisor_secondary_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
          OR (SELECT role FROM advisors WHERE user_id = auth.uid()) IN ('admin', 'compliance')
      )
    )
  );

-- Position history inherits visibility
CREATE POLICY position_history_access ON position_history
  FOR SELECT
  USING (
    account_id IN (
      SELECT id FROM accounts WHERE household_id IN (
        SELECT id FROM households WHERE
          assigned_advisor_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
          OR assigned_advisor_secondary_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
          OR (SELECT role FROM advisors WHERE user_id = auth.uid()) IN ('admin', 'compliance')
      )
    )
  );

-- ============================================================================
-- RLS POLICIES: BRIEFINGS, ACTION ITEMS, ENGAGEMENT
-- ============================================================================

CREATE POLICY briefings_access ON briefings
  FOR SELECT
  USING (
    household_id IN (
      SELECT id FROM households WHERE
        assigned_advisor_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
        OR assigned_advisor_secondary_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
        OR (SELECT role FROM advisors WHERE user_id = auth.uid()) IN ('admin', 'compliance')
    )
    OR created_by_advisor_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
  );

CREATE POLICY briefings_insert ON briefings
  FOR INSERT
  WITH CHECK (
    household_id IN (
      SELECT id FROM households WHERE
        assigned_advisor_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
        OR (SELECT role FROM advisors WHERE user_id = auth.uid()) IN ('admin', 'compliance')
    )
  );

CREATE POLICY action_items_access ON action_items
  FOR SELECT
  USING (
    household_id IN (
      SELECT id FROM households WHERE
        assigned_advisor_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
        OR assigned_advisor_secondary_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
        OR (SELECT role FROM advisors WHERE user_id = auth.uid()) IN ('admin', 'compliance')
    )
    OR assigned_to_advisor_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
  );

CREATE POLICY action_items_update_own ON action_items
  FOR UPDATE
  USING (
    assigned_to_advisor_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
  );

CREATE POLICY engagement_scores_access ON engagement_scores
  FOR SELECT
  USING (
    household_id IN (
      SELECT id FROM households WHERE
        assigned_advisor_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
        OR assigned_advisor_secondary_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
        OR (SELECT role FROM advisors WHERE user_id = auth.uid()) IN ('admin', 'compliance')
    )
  );

-- ============================================================================
-- RLS POLICIES: MEETINGS & AUDIT
-- ============================================================================

CREATE POLICY meetings_access ON meetings
  FOR SELECT
  USING (
    household_id IN (
      SELECT id FROM households WHERE
        assigned_advisor_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
        OR assigned_advisor_secondary_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
        OR (SELECT role FROM advisors WHERE user_id = auth.uid()) IN ('admin', 'compliance')
    )
    OR advisor_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
  );

CREATE POLICY meeting_notes_access ON meeting_notes
  FOR SELECT
  USING (
    meeting_id IN (
      SELECT id FROM meetings WHERE
        household_id IN (
          SELECT id FROM households WHERE
            assigned_advisor_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
            OR assigned_advisor_secondary_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
            OR (SELECT role FROM advisors WHERE user_id = auth.uid()) IN ('admin', 'compliance')
        )
        OR advisor_id = (SELECT id FROM advisors WHERE user_id = auth.uid())
    )
  );

CREATE POLICY audit_logs_access ON audit_logs
  FOR SELECT
  USING (
    (SELECT role FROM advisors WHERE user_id = auth.uid()) IN ('admin', 'compliance')
  );

-- ============================================================================
-- TRIGGERS FOR UPDATED_AT
-- ============================================================================

CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER households_updated_at BEFORE UPDATE ON households
  FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER accounts_updated_at BEFORE UPDATE ON accounts
  FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER positions_updated_at BEFORE UPDATE ON positions
  FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER briefings_updated_at BEFORE UPDATE ON briefings
  FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER action_items_updated_at BEFORE UPDATE ON action_items
  FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER meetings_updated_at BEFORE UPDATE ON meetings
  FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER advisors_updated_at BEFORE UPDATE ON advisors
  FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- ============================================================================
-- ANALYTICS VIEWS
-- ============================================================================

CREATE VIEW household_summary_view AS
SELECT
  h.id,
  h.household_name,
  h.assigned_advisor_id,
  a.first_name || ' ' || a.last_name AS advisor_name,
  h.aum_usd,
  h.engagement_score,
  h.engagement_cohort,
  h.attrition_risk,
  h.last_review_date,
  h.next_review_date,
  COUNT(DISTINCT ac.id) AS account_count,
  COUNT(DISTINCT p.id) AS position_count,
  COALESCE(SUM(ac.total_value_usd), 0) AS total_portfolio_value
FROM households h
LEFT JOIN advisors a ON h.assigned_advisor_id = a.id
LEFT JOIN accounts ac ON h.id = ac.household_id
LEFT JOIN positions p ON ac.id = p.account_id
GROUP BY h.id, a.id;

CREATE VIEW advisor_dashboard_view AS
SELECT
  a.id,
  a.first_name || ' ' || a.last_name AS advisor_name,
  COUNT(DISTINCT h.id) AS household_count,
  COUNT(DISTINCT CASE WHEN h.attrition_risk THEN h.id END) AS at_risk_count,
  COUNT(DISTINCT CASE WHEN h.engagement_cohort = 'premier' THEN h.id END) AS premier_count,
  COALESCE(SUM(h.aum_usd), 0) AS total_aum,
  COUNT(DISTINCT CASE WHEN h.next_review_date <= CURRENT_DATE + INTERVAL '7 days' THEN h.id END) AS upcoming_reviews_7d,
  COUNT(DISTINCT CASE WHEN ai.status = 'pending' AND ai.assigned_to_advisor_id = a.id THEN ai.id END) AS pending_action_items
FROM advisors a
LEFT JOIN households h ON a.id = h.assigned_advisor_id
LEFT JOIN action_items ai ON h.id = ai.household_id
WHERE a.active = TRUE
GROUP BY a.id;

CREATE VIEW engagement_cohort_summary AS
SELECT
  h.engagement_cohort,
  COUNT(*) AS household_count,
  AVG(h.engagement_score) AS avg_score,
  AVG(h.aum_usd) AS avg_aum,
  COUNT(CASE WHEN h.attrition_risk THEN 1 END)::FLOAT / COUNT(*) * 100 AS attrition_risk_pct,
  AVG(DATE_PART('days', CURRENT_DATE - h.last_review_date)) AS avg_days_since_review
FROM households h
GROUP BY h.engagement_cohort;
