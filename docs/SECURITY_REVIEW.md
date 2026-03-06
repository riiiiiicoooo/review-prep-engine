# Security Review: Review Prep Engine

**Date:** 2026-03-06
**Scope:** Full codebase review of `review-prep-engine`
**Reviewer:** Automated security audit

---

## Executive Summary

This review covers the entire Review Prep Engine codebase, a wealth management platform that aggregates sensitive client financial data from CRM systems (Salesforce), custodians (Schwab, Fidelity), and financial planning software. The application handles highly sensitive PII including Social Security numbers, dates of birth, health notes, account balances, and assets under management (AUM).

**27 findings** were identified across 7 categories:

| Severity | Count |
|----------|-------|
| CRITICAL | 3     |
| HIGH     | 11    |
| MEDIUM   | 9     |
| LOW      | 4     |

The most urgent issues are the complete absence of authentication on all API endpoints, wildcard CORS with credentials enabled, and path traversal vulnerabilities in the storage layer that could allow arbitrary file deletion via `shutil.rmtree`.

---

## Table of Contents

1. [Hardcoded Secrets and API Keys](#1-hardcoded-secrets-and-api-keys)
2. [Client PII Protection](#2-client-pii-protection)
3. [Authentication and Authorization on API Endpoints](#3-authentication-and-authorization-on-api-endpoints)
4. [Input Validation](#4-input-validation)
5. [Data Exposure in Logs and Error Messages](#5-data-exposure-in-logs-and-error-messages)
6. [Infrastructure Misconfigurations](#6-infrastructure-misconfigurations)
7. [Dependency Vulnerabilities](#7-dependency-vulnerabilities)

---

## 1. Hardcoded Secrets and API Keys

### Finding 1.1 - Partial JWT Token in `.env.example`

**Severity:** HIGH
**File:** `F:\Portfolio\Portfolio\review-prep-engine\.env.example`, line 9
**Description:** The `.env.example` file contains a partial JWT token structure for `SUPABASE_LOCAL_KEY`. While truncated with `...`, the header portion `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9` is a real Base64-encoded JWT header. If a developer copies this file and uses the default value, or if a real key was partially committed, it leaks token structure information.

**Code Evidence:**
```
SUPABASE_LOCAL_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Fix:** Replace with an obviously fake placeholder that cannot be confused with a real token:
```
SUPABASE_LOCAL_KEY=replace-with-your-local-supabase-key
```

---

### Finding 1.2 - Empty Default API Key in MCP Server

**Severity:** HIGH
**File:** `F:\Portfolio\Portfolio\review-prep-engine\mcp\server.py`, line 379
**Description:** The MCP server initializes with a default empty string for `API_KEY`. If the environment variable is not set, the server runs with no API key at all, meaning all downstream API calls from the MCP tools are unauthenticated.

**Code Evidence:**
```python
api_key = os.getenv("API_KEY", "")
```

**Fix:** Fail fast if the API key is not set:
```python
api_key = os.getenv("API_KEY")
if not api_key:
    raise RuntimeError("API_KEY environment variable is required")
```

---

### Finding 1.3 - Non-Null Assertion on Service Role Key

**Severity:** MEDIUM
**File:** `F:\Portfolio\Portfolio\review-prep-engine\trigger-jobs\briefing_generation.ts`, line 54
**Description:** The Trigger.dev job uses TypeScript non-null assertion (`!`) on `process.env.SUPABASE_SERVICE_ROLE_KEY`. If the environment variable is missing at runtime, this will pass `undefined` to the Supabase client instead of failing with a clear error. The service role key bypasses all Row Level Security policies.

**Code Evidence:**
```typescript
const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);
```

**Fix:** Validate environment variables at startup:
```typescript
const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
if (!supabaseUrl || !supabaseKey) {
  throw new Error("Missing required SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY");
}
const supabase = createClient(supabaseUrl, supabaseKey);
```

---

### Finding 1.4 - Placeholder Secrets in `.env.example` Encourage Weak Defaults

**Severity:** LOW
**File:** `F:\Portfolio\Portfolio\review-prep-engine\.env.example`, lines 94-95
**Description:** The JWT and session secrets use descriptive but weak placeholder values. Developers may forget to replace them or use similarly weak values in production.

**Code Evidence:**
```
JWT_SECRET=your-jwt-secret-key-change-in-production
SESSION_SECRET=your-session-secret-key-change-in-production
```

**Fix:** Add a startup validation check in the application that verifies secrets are not the default placeholder values and meet minimum entropy requirements (e.g., at least 32 characters of random data).

---

## 2. Client PII Protection

> **Note:** This application handles wealth management client data, not employee HR data. The PII at risk includes: Social Security numbers, dates of birth, health notes, account balances, AUM, engagement scores, and attrition risk assessments.

### Finding 2.1 - SSN Stored as Plain TEXT Column

**Severity:** HIGH
**File:** `F:\Portfolio\Portfolio\review-prep-engine\supabase\migrations\001_initial_schema.sql`, line 104
**Description:** The `ssn_encrypted` column is defined as `TEXT` type. Despite the column name suggesting encryption, there is no database-level encryption enforced. The column name implies application-level encryption should be applied before storage, but there is no evidence of encryption logic in any importer or data access code. If data is written without encryption, SSNs are stored in plaintext.

**Code Evidence:**
```sql
ssn_encrypted TEXT,
```

**Fix:**
1. Implement application-level encryption (e.g., AES-256-GCM) before writing SSNs to the database.
2. Add a CHECK constraint or trigger to verify the value is not plaintext (e.g., must start with an encryption prefix).
3. Consider using PostgreSQL's `pgcrypto` extension for database-level encryption:
```sql
ssn_encrypted BYTEA,  -- Store as encrypted bytes, not text
```
4. Add a dedicated encryption/decryption service layer and audit all access to this column.

---

### Finding 2.2 - Health Notes Stored Without Access Controls in Application Layer

**Severity:** MEDIUM
**File:** `F:\Portfolio\Portfolio\review-prep-engine\src\client_profiler.py`, line 129
**Description:** The `HouseholdMember` model includes a `health_notes` field for long-term care planning. This is protected health information (PHI) that may be subject to HIPAA considerations when used in financial planning. The field is returned in full client summaries with no field-level access control or redaction capability.

**Code Evidence:**
```python
health_notes: Optional[str] = None  # For LTC planning
```

**Fix:**
1. Implement field-level access control so `health_notes` is only returned when the requesting user has explicit PHI access permissions.
2. Add a redaction layer that masks or omits PHI fields by default, requiring an explicit scope to include them.
3. Encrypt `health_notes` at rest with a separate encryption key from other PII.

---

### Finding 2.3 - Client Financial Data in Attrition Alert Emails

**Severity:** MEDIUM
**File:** `F:\Portfolio\Portfolio\review-prep-engine\emails\attrition_alert.tsx`
**Description:** The attrition alert email template includes detailed client AUM, engagement scores, and risk factors. Emails are typically stored in plaintext on mail servers and may be forwarded. Sending detailed financial metrics over email creates a data exposure surface.

**Fix:**
1. Replace detailed financial figures in email bodies with summary-level information (e.g., "AUM: above $1M" instead of exact figures).
2. Include a secure link to view full details in the authenticated application instead of embedding data in the email.
3. Mark emails as confidential and add appropriate disclaimers.

---

### Finding 2.4 - Data Directory Not in `.gitignore`

**Severity:** MEDIUM
**File:** `F:\Portfolio\Portfolio\review-prep-engine\.gitignore`
**Description:** The `.gitignore` file does not exclude the `data/` directory, which is where the JSON store persists all client household data including financial details, PII, and engagement scores. If a developer runs the application locally, the `data/` directory will be created and could be accidentally committed to version control.

**Code Evidence:**
The `storage/json_store.py` writes to `./data/households/` by default, but `data/` is not listed in `.gitignore`.

**Fix:** Add to `.gitignore`:
```
data/
```

---

## 3. Authentication and Authorization on API Endpoints

### Finding 3.1 - Zero Authentication on All API Endpoints

**Severity:** CRITICAL
**File:** `F:\Portfolio\Portfolio\review-prep-engine\api\app.py`, lines 206-490
**Description:** Every API endpoint in the application has zero authentication. There is no JWT validation, no API key middleware, no session checking, and no auth dependency injection. All client financial data, briefings, action items, household details, and dashboard metrics are accessible to any caller without any form of identity verification. This is the most critical finding in this review.

Affected endpoints include:
- `GET /api/households` - Lists all client households with financial data
- `GET /api/households/{id}` - Full household detail including PII
- `GET /api/households/{id}/briefing` - Complete review briefing
- `GET /api/households/{id}/action-items` - Client action items
- `POST /api/households/{id}/action-items/{item_id}/update` - Modify action items
- `GET /api/dashboard/upcoming-reviews` - All upcoming review data

**Code Evidence:**
```python
@app.get("/api/households")
async def get_households():
    """Get all households with summary data."""
    # No auth check whatsoever
    households = store.get_all_households()
    ...

@app.get("/api/households/{household_id}")
async def get_household(household_id: str):
    """Get detailed household data."""
    # No auth check whatsoever
    household = store.get_household(household_id)
    ...
```

**Fix:**
1. Implement JWT-based authentication using Supabase Auth (already in the stack):
```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        # Verify JWT with Supabase
        user = supabase.auth.get_user(token)
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

@app.get("/api/households")
async def get_households(user=Depends(verify_token)):
    ...
```
2. Add tenant-level authorization to ensure users can only access data within their organization.
3. Add role-based access control (RBAC) for different advisor permission levels.

---

### Finding 3.2 - Wildcard CORS with Credentials Enabled

**Severity:** CRITICAL
**File:** `F:\Portfolio\Portfolio\review-prep-engine\api\app.py`, lines 40-46
**Description:** The CORS middleware allows all origins (`*`) while simultaneously enabling `allow_credentials=True`. This combination is explicitly dangerous because it allows any website on the internet to make authenticated cross-origin requests to this API. If authentication were to be added later, any malicious website could make requests using the user's cookies/credentials. Per the CORS specification, browsers should reject this combination, but some configurations may still be vulnerable.

**Code Evidence:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Fix:** Restrict origins to known frontend domains:
```python
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

---

### Finding 3.3 - n8n Workflows Use Anon Key for Write Operations

**Severity:** HIGH
**File:** `F:\Portfolio\Portfolio\review-prep-engine\n8n\crm_daily_sync.json`
**File:** `F:\Portfolio\Portfolio\review-prep-engine\n8n\review_reminder.json`
**Description:** Both n8n workflows use `SUPABASE_ANON_KEY` for server-side operations including POST and PATCH requests to Supabase. The anon key is designed for client-side use with Row Level Security (RLS) enforcement. Using it for server-side write operations means either: (a) RLS blocks the writes and the workflows fail silently, or (b) RLS policies are overly permissive to accommodate the anon key, weakening security for all clients.

**Code Evidence (crm_daily_sync.json):**
```json
"headerParametersUi": {
  "parameter": [
    {
      "name": "apikey",
      "value": "={{$env.SUPABASE_ANON_KEY}}"
    },
    {
      "name": "Authorization",
      "value": "=Bearer {{$env.SUPABASE_ANON_KEY}}"
    }
  ]
}
```

**Fix:** Use `SUPABASE_SERVICE_ROLE_KEY` for all server-side n8n workflow operations:
```json
"value": "={{$env.SUPABASE_SERVICE_ROLE_KEY}}"
```
Ensure service role key is stored securely in n8n's credential store, not as a plain environment variable.

---

### Finding 3.4 - Missing RLS Policies for Write Operations

**Severity:** HIGH
**File:** `F:\Portfolio\Portfolio\review-prep-engine\supabase\migrations\001_initial_schema.sql`
**Description:** While RLS is enabled on all tables and SELECT policies are defined for most tables using `tenant_id` checks, many tables are missing INSERT, UPDATE, and DELETE policies. Without explicit write policies, RLS defaults to denying all write operations for non-superuser roles. While this is safe by default, it means the application likely requires the service role key (which bypasses RLS entirely) for all write operations, negating the security benefit of RLS.

**Fix:**
1. Define explicit INSERT, UPDATE, and DELETE policies for each table scoped to the user's `tenant_id`.
2. Create a Supabase function that extracts `tenant_id` from the JWT:
```sql
CREATE POLICY "Users can insert into own tenant"
  ON households FOR INSERT
  WITH CHECK (tenant_id = auth.jwt() ->> 'tenant_id');

CREATE POLICY "Users can update own tenant data"
  ON households FOR UPDATE
  USING (tenant_id = auth.jwt() ->> 'tenant_id');
```
3. Minimize use of service role key to only administrative batch operations.

---

### Finding 3.5 - No Tenant Validation in MCP Server

**Severity:** MEDIUM
**File:** `F:\Portfolio\Portfolio\review-prep-engine\mcp\server.py`, lines 294-304
**Description:** The MCP server's `call_tool` handler accepts a `tenant_id` parameter in tool arguments but performs no validation that the caller is authorized for that tenant. Any caller can specify any `tenant_id` and access data across tenants.

**Code Evidence:**
```python
@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool invocations."""
    if name == "generate_briefing":
        return await _generate_briefing(arguments)  # tenant_id passed but never validated
```

**Fix:** Add tenant validation before processing any tool call:
```python
@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    tenant_id = arguments.get("tenant_id")
    if not tenant_id or not await validate_tenant_access(tenant_id):
        return [TextContent(type="text", text=json.dumps({"error": "Unauthorized tenant access"}))]
    ...
```

---

## 4. Input Validation

### Finding 4.1 - Path Traversal in JSON Storage Layer

**Severity:** CRITICAL
**File:** `F:\Portfolio\Portfolio\review-prep-engine\storage\json_store.py`, line 262
**Description:** The `household_id` is used directly in filesystem path construction with no sanitization. An attacker who can control the `household_id` value (via the unauthenticated API) could use path traversal sequences (e.g., `../../etc`) to read or write files anywhere on the filesystem. Combined with the `delete_household` method at line 478 which calls `shutil.rmtree`, this could allow arbitrary directory deletion.

**Code Evidence:**
```python
household_dir = self.store_dir / "households" / household.id
```

And the delete method:
```python
def delete_household(self, household_id: str) -> bool:
    household_dir = self.store_dir / "households" / household_id
    if household_dir.exists():
        shutil.rmtree(household_dir)  # Deletes entire directory tree
        return True
    return False
```

**Fix:**
1. Validate that `household_id` contains only safe characters:
```python
import re

def _sanitize_id(self, household_id: str) -> str:
    if not re.match(r'^[a-zA-Z0-9_-]+$', household_id):
        raise ValueError(f"Invalid household_id format: {household_id}")
    return household_id

def _household_dir(self, household_id: str) -> Path:
    safe_id = self._sanitize_id(household_id)
    resolved = (self.store_dir / "households" / safe_id).resolve()
    # Verify the resolved path is still within the store directory
    if not str(resolved).startswith(str(self.store_dir.resolve())):
        raise ValueError("Path traversal detected")
    return resolved
```
2. Use UUID format validation since household IDs should be UUIDs per the database schema.

---

### Finding 4.2 - No Input Validation on API Path Parameters

**Severity:** HIGH
**File:** `F:\Portfolio\Portfolio\review-prep-engine\api\app.py`, line 271
**Description:** The `household_id` path parameter is accepted as a raw string with no format validation. Since household IDs are UUIDs in the database schema, the API should validate the format to prevent injection attacks and path traversal through the storage layer.

**Code Evidence:**
```python
@app.get("/api/households/{household_id}")
async def get_household(household_id: str):
    """Get detailed household data."""
    household = store.get_household(household_id)
```

**Fix:**
```python
from uuid import UUID

@app.get("/api/households/{household_id}")
async def get_household(household_id: UUID):
    """Get detailed household data."""
    household = store.get_household(str(household_id))
```

---

### Finding 4.3 - XSS in HTML Briefing Generation

**Severity:** HIGH
**File:** `F:\Portfolio\Portfolio\review-prep-engine\trigger-jobs\briefing_generation.ts`, lines 524-578
**Description:** The `generateBriefingHtml` function directly interpolates client data into HTML strings using template literals. Client names, goals, notes, and financial data are inserted without HTML entity escaping. If any client data contains HTML/JavaScript (e.g., a client name like `<script>alert('xss')</script>`), it will execute when the briefing HTML is rendered in a browser or email client.

**Code Evidence:**
```typescript
function generateBriefingHtml(briefingContent: Record<string, any>): string {
  return `<html>...<h1>${briefingContent.title}</h1>...`;
}
```

**Fix:**
1. Use a proper HTML templating library with auto-escaping (e.g., `handlebars`, `ejs` with escaping enabled, or `DOMPurify` for sanitization).
2. At minimum, implement an escape function:
```typescript
function escapeHtml(unsafe: string): string {
  return unsafe
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
```
3. Apply escaping to all interpolated values in the HTML template.

---

### Finding 4.4 - XSS in n8n Email Body Construction

**Severity:** HIGH
**File:** `F:\Portfolio\Portfolio\review-prep-engine\n8n\crm_daily_sync.json`
**Description:** The CRM daily sync workflow constructs HTML email bodies by directly interpolating CRM data (contact names, notes, interaction summaries) into HTML without sanitization. If CRM data contains malicious HTML, it will be rendered in the advisor's email client.

**Fix:** Use n8n's built-in expression sanitization or pass data through an HTML escaping function node before constructing email HTML.

---

### Finding 4.5 - No Path Validation in CSV Importers

**Severity:** MEDIUM
**File:** `F:\Portfolio\Portfolio\review-prep-engine\importers\custodial_import.py`
**File:** `F:\Portfolio\Portfolio\review-prep-engine\importers\crm_import.py`
**File:** `F:\Portfolio\Portfolio\review-prep-engine\importers\planning_import.py`
**Description:** All three CSV importers accept a file path parameter and open it directly without validating that the path is within an expected directory. While these importers are likely run from the command line and not directly from the API, if they were ever exposed as an API endpoint, this would enable arbitrary file reading.

**Code Evidence:**
```python
with open(csv_file, 'r') as f:
    reader = csv.DictReader(f)
```

**Fix:**
```python
import os

def _validate_import_path(csv_file: str, allowed_dir: str) -> str:
    real_path = os.path.realpath(csv_file)
    if not real_path.startswith(os.path.realpath(allowed_dir)):
        raise ValueError(f"File path outside allowed directory: {csv_file}")
    return real_path
```

---

### Finding 4.6 - No Path Validation in Briefing Renderer Export

**Severity:** MEDIUM
**File:** `F:\Portfolio\Portfolio\review-prep-engine\export\briefing_renderer.py`
**Description:** The `export_markdown` and `export_text` methods write to an arbitrary `output_path` without validating that it is within an expected directory. This could allow writing files to arbitrary locations if the path is user-controlled.

**Fix:** Validate that the output path resolves to within an expected export directory before writing.

---

## 5. Data Exposure in Logs and Error Messages

### Finding 5.1 - PII Logged in Briefing Generation Job

**Severity:** HIGH
**File:** `F:\Portfolio\Portfolio\review-prep-engine\trigger-jobs\briefing_generation.ts`, lines 76-79
**Description:** The briefing generation Trigger.dev job logs client household names and AUM values. These logs are typically stored in Trigger.dev's cloud infrastructure and may be accessible to operations staff or retained indefinitely.

**Code Evidence:**
```typescript
logger.info(`Processing household: ${household.name}, AUM: $${household.aum}`);
```

**Fix:** Log only non-PII identifiers:
```typescript
logger.info(`Processing household: ${household.id}, review_type: ${reviewType}`);
```

---

### Finding 5.2 - Advisor Email Logged in Briefing Job

**Severity:** MEDIUM
**File:** `F:\Portfolio\Portfolio\review-prep-engine\trigger-jobs\briefing_generation.ts`, line 634
**Description:** The advisor's email address is logged when sending the briefing notification. Email addresses are PII and should not appear in application logs.

**Code Evidence:**
```typescript
logger.info(`Sending briefing to advisor: ${advisorEmail}`);
```

**Fix:**
```typescript
logger.info(`Sending briefing notification for household: ${householdId}`);
```

---

### Finding 5.3 - Error Messages Expose Internal Details

**Severity:** MEDIUM
**File:** `F:\Portfolio\Portfolio\review-prep-engine\api\app.py`, line 192
**File:** `F:\Portfolio\Portfolio\review-prep-engine\mcp\server.py`, lines 331, 344, 371
**Description:** Error responses include raw exception messages that may contain internal implementation details, file paths, database schema information, or connection strings. These details help attackers understand the system architecture.

**Code Evidence (api/app.py):**
```python
raise HTTPException(status_code=404, detail=f"Household {household_id} not found")
```

**Code Evidence (mcp/server.py):**
```python
return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
```

**Fix:**
1. Return generic error messages to clients:
```python
raise HTTPException(status_code=404, detail="Resource not found")
```
2. Log the detailed error internally:
```python
logger.error(f"Household lookup failed for {household_id}: {str(e)}")
raise HTTPException(status_code=404, detail="Resource not found")
```

---

### Finding 5.4 - Importer Prints Warnings with Data Details

**Severity:** LOW
**File:** `F:\Portfolio\Portfolio\review-prep-engine\importers\custodial_import.py`, line 155
**Description:** The custodial importer uses `print()` for warnings that may contain account data or error details. Print statements go to stdout, which may be captured in container logs or redirected to log aggregation services.

**Fix:** Replace `print()` with structured logging using the `logging` module, and ensure logged messages do not contain PII.

---

## 6. Infrastructure Misconfigurations

### Finding 6.1 - Dockerfile Runs as Root

**Severity:** HIGH
**File:** `F:\Portfolio\Portfolio\review-prep-engine\Dockerfile`
**Description:** The Dockerfile does not include a `USER` directive, meaning the application runs as root inside the container. If the container is compromised (e.g., via the path traversal vulnerability), the attacker has root access to the container filesystem and potentially to the host via container escape.

**Code Evidence:**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Fix:**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### Finding 6.2 - Dockerfile `COPY . .` May Include Secrets

**Severity:** HIGH
**File:** `F:\Portfolio\Portfolio\review-prep-engine\Dockerfile`
**Description:** The `COPY . .` directive copies the entire project directory into the image, which may include `.env` files, `data/` directory with client data, `.git/` history, and other sensitive files. Even if `.env` is in `.gitignore`, it may exist on the build machine.

**Fix:**
1. Add a `.dockerignore` file:
```
.env
.env.local
.env.*
data/
.git/
.gitignore
node_modules/
.vscode/
.idea/
docs/
sample_data/
__pycache__/
*.pyc
```
2. Use multi-stage builds to minimize the final image content.

---

### Finding 6.3 - Server Binds to 0.0.0.0

**Severity:** MEDIUM
**File:** `F:\Portfolio\Portfolio\review-prep-engine\api\app.py`, line 508
**File:** `F:\Portfolio\Portfolio\review-prep-engine\docker-compose.yml`, line 7
**File:** `F:\Portfolio\Portfolio\review-prep-engine\Makefile`, line 20
**Description:** The API server binds to `0.0.0.0`, making it accessible on all network interfaces. While necessary inside Docker containers, the `Makefile` target for local development also binds to all interfaces, exposing the unauthenticated API to the local network.

**Code Evidence (Makefile):**
```makefile
api:
	uvicorn api.app:app --reload --host 0.0.0.0 --port 8000
```

**Fix:** For local development, bind to localhost only:
```makefile
api:
	uvicorn api.app:app --reload --host 127.0.0.1 --port 8000
```

---

### Finding 6.4 - No Security Headers

**Severity:** MEDIUM
**File:** `F:\Portfolio\Portfolio\review-prep-engine\api\app.py`
**File:** `F:\Portfolio\Portfolio\review-prep-engine\vercel.json`
**Description:** Neither the FastAPI application nor the Vercel configuration sets security headers such as `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security` (HSTS), or `Referrer-Policy`.

**Fix:** Add security headers middleware to FastAPI:
```python
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        return response

app.add_middleware(SecurityHeadersMiddleware)
```

---

### Finding 6.5 - No Rate Limiting

**Severity:** MEDIUM
**File:** `F:\Portfolio\Portfolio\review-prep-engine\api\app.py`
**Description:** The API has no rate limiting on any endpoint. Combined with the lack of authentication, this allows unlimited data scraping of all client financial data and unlimited briefing generation requests.

**Fix:** Add rate limiting middleware:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/api/households")
@limiter.limit("30/minute")
async def get_households(request: Request):
    ...
```

---

### Finding 6.6 - Docker Compose Exposes Data Volume

**Severity:** MEDIUM
**File:** `F:\Portfolio\Portfolio\review-prep-engine\docker-compose.yml`, line 9
**Description:** The Docker Compose configuration mounts `./data:/app/data`, which binds the local data directory (containing all client JSON files) into the container. If the container is compromised, the attacker gains access to the host filesystem's data directory.

**Code Evidence:**
```yaml
volumes:
  - ./data:/app/data
```

**Fix:** For production, use named Docker volumes instead of bind mounts:
```yaml
volumes:
  - app_data:/app/data

volumes:
  app_data:
```

---

### Finding 6.7 - Swagger/OpenAPI Documentation Exposed

**Severity:** LOW
**File:** `F:\Portfolio\Portfolio\review-prep-engine\api\app.py`
**Description:** FastAPI automatically serves interactive API documentation at `/docs` (Swagger UI) and `/redoc`. In production, this exposes the complete API schema, all endpoints, request/response models, and parameter details to anyone.

**Fix:** Disable docs in production:
```python
import os

docs_url = "/docs" if os.getenv("ENVIRONMENT") != "production" else None
redoc_url = "/redoc" if os.getenv("ENVIRONMENT") != "production" else None

app = FastAPI(
    title="Review Prep Engine",
    docs_url=docs_url,
    redoc_url=redoc_url,
)
```

---

## 7. Dependency Vulnerabilities

### Finding 7.1 - Minimal Dependency List with No Security Packages

**Severity:** MEDIUM
**File:** `F:\Portfolio\Portfolio\review-prep-engine\requirements.txt`
**Description:** The `requirements.txt` lists only 4 packages. There are no security-related dependencies such as authentication libraries, rate limiting, input sanitization, or security header middleware. This confirms that security features are entirely absent from the application.

**Code Evidence:**
```
fastapi==0.115.0
uvicorn==0.30.0
pydantic==2.10.0
python-multipart==0.0.6
```

**Fix:** Add security-related dependencies:
```
python-jose[cryptography]==3.3.0  # JWT validation
slowapi==0.1.9                     # Rate limiting
bleach==6.1.0                      # HTML sanitization
python-dotenv==1.0.1               # Env file loading
```

---

### Finding 7.2 - No Dependency Vulnerability Scanning

**Severity:** LOW
**File:** Project root (no `safety` or `pip-audit` configuration found)
**Description:** There is no evidence of dependency vulnerability scanning in the project. No `safety` configuration, no `pip-audit` setup, no GitHub Dependabot configuration, and no CI/CD security scanning pipeline.

**Fix:**
1. Add `pip-audit` to development dependencies and CI:
```bash
pip install pip-audit
pip-audit
```
2. Create a `.github/dependabot.yml` for automated dependency updates.
3. Add security scanning to the CI pipeline.

---

### Finding 7.3 - External CDN Dependency in Dashboard

**Severity:** LOW
**File:** `F:\Portfolio\Portfolio\review-prep-engine\dashboard\dashboard.jsx`
**Description:** The dashboard loads Google Fonts via an external CDN link. If the CDN is compromised or the resource is modified, it could inject malicious CSS or content into the dashboard. While low risk, it introduces a third-party dependency without subresource integrity (SRI) hashes.

**Fix:** Either self-host the font files or add SRI hashes to the link tag.

---

## Prioritized Remediation Plan

### Immediate (Week 1) - Critical Findings
1. **Add authentication to all API endpoints** (Finding 3.1)
2. **Fix wildcard CORS** (Finding 3.2)
3. **Fix path traversal in JSON storage** (Finding 4.1)

### Short-Term (Week 2-3) - High Findings
4. Fix empty API key default in MCP server (Finding 1.2)
5. Remove JWT token fragment from `.env.example` (Finding 1.1)
6. Add `.dockerignore` and non-root user to Dockerfile (Findings 6.1, 6.2)
7. Fix XSS in HTML generation (Findings 4.3, 4.4)
8. Switch n8n workflows to service role key (Finding 3.3)
9. Add RLS write policies (Finding 3.4)
10. Implement SSN encryption (Finding 2.1)
11. Remove PII from logs (Findings 5.1, 5.2)
12. Validate API path parameters (Finding 4.2)

### Medium-Term (Week 4-6) - Medium Findings
13. Add rate limiting (Finding 6.5)
14. Add security headers (Finding 6.4)
15. Add `data/` to `.gitignore` (Finding 2.4)
16. Fix error message information leaks (Finding 5.3)
17. Add tenant validation to MCP server (Finding 3.5)
18. Bind to localhost for local development (Finding 6.3)
19. Add health notes access controls (Finding 2.2)
20. Reduce PII in alert emails (Finding 2.3)
21. Add path validation to importers and renderer (Findings 4.5, 4.6)
22. Use named Docker volumes (Finding 6.6)
23. Add security dependencies (Finding 7.1)

### Ongoing
24. Set up dependency vulnerability scanning (Finding 7.2)
25. Validate environment variables at startup (Finding 1.3)
26. Disable Swagger in production (Finding 6.7)
27. Self-host or SRI-hash external resources (Finding 7.3)
28. Replace print statements with structured logging (Finding 5.4)
29. Validate placeholder secrets at startup (Finding 1.4)

---

## Appendix: Files Reviewed

| File | Path |
|------|------|
| FastAPI Application | `api/app.py` |
| Client Profiler Models | `src/client_profiler.py` |
| Review Assembler | `src/review_assembler.py` |
| Engagement Scorer | `src/engagement_scorer.py` |
| Custodial Importer | `importers/custodial_import.py` |
| CRM Importer | `importers/crm_import.py` |
| Planning Importer | `importers/planning_import.py` |
| JSON Storage Layer | `storage/json_store.py` |
| Briefing Renderer | `export/briefing_renderer.py` |
| Dashboard UI | `dashboard/dashboard.jsx` |
| Briefing Generation Job | `trigger-jobs/briefing_generation.ts` |
| Engagement Batch Job | `trigger-jobs/engagement_batch.ts` |
| Review Reminder Email | `emails/review_reminder.tsx` |
| Attrition Alert Email | `emails/attrition_alert.tsx` |
| CRM Daily Sync Workflow | `n8n/crm_daily_sync.json` |
| Review Reminder Workflow | `n8n/review_reminder.json` |
| Database Schema | `supabase/migrations/001_initial_schema.sql` |
| MCP Server | `mcp/server.py` |
| MCP Tool Schemas | `mcp/tool_schemas.json` |
| Sample Data Loader | `sample_data/load_sample.py` |
| Dockerfile | `Dockerfile` |
| Docker Compose | `docker-compose.yml` |
| Vercel Config | `vercel.json` |
| Makefile | `Makefile` |
| Requirements | `requirements.txt` |
| Git Ignore | `.gitignore` |
| Environment Example | `.env.example` |
