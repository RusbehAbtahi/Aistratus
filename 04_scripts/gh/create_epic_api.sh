#!/bin/bash

# API-003 – Gateway Hardening & Per-User Throttling
gh issue create -t "API-003 · Gateway Hardening & Per-User Throttling" -l "api,story" -b "Parent: #49

### Context

The public HTTP API (\`/infer\`, \`/stop\`, \`/ping\`) must enforce **Cognito-JWT authentication** and protect against abuse (GUI retry loops, script attacks). Past audits flagged two risks: (1) route settings can be overwritten by stage-level imports, and (2) API Gateway’s default logging obscures the client \`sub\`, making forensic work tedious.

### Acceptance Criteria

1. **JWT Verification**
   - Requests without \`Authorization: Bearer <id token>\` → **401** in ≤ 150 ms.
   - Expired or malformed tokens → **403** with body \`{\"error\":\"invalid_token\"}\`.
   - JWKS cached ≤ 10 min; cache-miss latency ≤ 300 ms (cold).
2. **Per-User Throttling**
   - Burst ≤ 5 req/s, rate ≤ 20 req/min **per Cognito \`sub\`**.
   - Exceeding limits returns **429** and header \`Retry-After: 60\`.
   - CloudWatch metric \`ApiRateLimitBreaches\` increments on every 429.
3. **Immutable Route Settings**
   - Terraform resource \`aws_apigatewayv2_route_settings\` applied to each route with explicit \`throttling_burst_limit\` and \`throttling_rate_limit\`.
   - A Terraform **post-apply test** (\`tests/api_route_settings_test.py\`, using boto3) asserts the burst/rate limits match the Terraform values.
4. **Positive & Negative Tests** (CI job \`api_hardening_spec\`)
   - Postman/newman collection runs:
     - valid token ✓200,
     - missing token ✓401,
     - tampered signature ✓403,
     - 6 rapid calls ✓1×429.
5. **Documentation**
   - \`docs/api/jwt_auth.md\` explains Cognito pool IDs, import script, and provides \`curl\` examples for each failure mode.

### Technical Notes / Steps

- **Terraform**
  \`\`\`hcl
  resource \"aws_apigatewayv2_route_settings\" \"infer_rl\" {
    api_id                = aws_apigatewayv2_api.edge.id
    stage_name            = aws_apigatewayv2_stage.prod.name
    route_key             = \"POST /infer\"
    throttling_burst_limit = 5
    throttling_rate_limit  = 20
  }
  # repeat for /stop and /ping …
  \`\`\`
- **Authorizer** (\`modules/auth/cognito.tf\`) generates pool + app-client; output the issuer URL and JWKs URI for \`openapi.yaml\` security schema.
- **Contract Tests**
  \`\`\`bash
  newman run tests/postman/api_hardening.postman_collection.json \\
         --env-var ISSUER_URL=\$COGNITO_ISSUER \\
         --env-var CLIENT_ID=\$COGNITO_APP_ID
  \`\`\`
- **CI Hook**: GitHub Action \`api_hardening.yml\` blocks merge unless all Postman tests pass and \`pytest tests/api_route_settings_test.py\` is green.
- **Patch:** Document in \`docs/api/jwt_auth.md\` the exact steps for manual rollback using:
  \`\`\`bash
  terraform apply -refresh-only -replace=aws_apigatewayv2_route_settings.<resource_name>
  \`\`\`
  (Specify the actual resource names explicitly.)

- **Cost**: extra CloudWatch metrics ≈ €0.05/mo; JWT authorizer execution ≈ €0.40/mo at 50 req/day.
"

# API-004 – CORS & Structured JSON Access Logging
gh issue create -t "API-004 · CORS & Structured JSON Access Logging" -l "api,story" -b "Parent: #49

### Context

Frontend (Tkinter GUI and future mobile) is served from \`localhost\` and potentially file URLs; all other origins must be rejected. Audit RISK-note highlighted that default access logs are unstructured and retention unspecified.

### Acceptance Criteria

1. **CORS Policy**
   - Allowed origins: \`http://localhost:*\` and \`capacitor://*\`.
   - Allowed methods: \`POST, GET, OPTIONS\`; headers: \`Authorization, Content-Type\`.
   - Pre-flight (\`OPTIONS\`) returns **204** under 100 ms.
2. **Structured Logging**
   - Enable JSON access logging with fields \`requestId, ip, route, status, jwtSub, latencyMs, userAgent\`.
   - Logs shipped to CloudWatch group \`/apigw/tinyllama-access\` with \`retention_in_days = 30\`.
3. **Cost Estimate** comment in Terraform: ≤ 100 MB/mo ≈ €0.00 (free tier); flag alert at 70 MB.
4. **Smoke Test**
   - CI sends \`OPTIONS /infer\` from disallowed origin → **403**.
   - Logs must contain \`origin\":\"evil.com\"\` and \`status\":403\`.

### Technical Notes

- **Terraform snippet for CORS on HTTP API Stage:**
  \`\`\`hcl
  cors_configuration {
    allow_origins = [\"http://localhost:*\", \"capacitor://*\"]
    allow_methods = [\"GET\",\"POST\",\"OPTIONS\"]
    allow_headers = [\"Authorization\",\"Content-Type\"]
  }
  \`\`\`
- **Patch:** Add the explicit full JSON format to the Terraform snippet for access logging to match acceptance criteria explicitly:
  \`\`\`hcl
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_access.arn
    format = jsonencode({
      requestId  = \"\$context.requestId\"
      ip         = \"\$context.identity.sourceIp\"
      route      = \"\$context.routeKey\"
      status     = \"\$context.status\"
      jwtSub     = \"\$context.authorizer.claims.sub\"
      latencyMs  = \"\$context.responseLatency\"
      userAgent  = \"\$context.identity.userAgent\"
    })
  }
  \`\`\`
- Access-log format: \`\$context.requestId \$context.identity.sourceIp ...\`
- Add CloudWatch Insights query (\`queries/api_5xx.cwi\`) committed under \`observability/\`.
"

# API-005 – GUI Login Button → Cognito OAuth Flow
gh issue create -t "API-005 · GUI Login Button → Cognito OAuth Flow" -l "api,story" -b "Parent: #49

### Context

The Tkinter GUI now has a **“Login”** button (see \`gui_view.py\`). Pressing it must open the Cognito Hosted-UI, complete the OAuth code flow, and store the ID token in memory; no AWS keys are ever written to disk.

### Acceptance Criteria

1. **Desktop Flow**
   - Button click opens system browser at \`\${COGNITO_DOMAIN}/oauth2/authorize?...&redirect_uri=http://127.0.0.1:8765/callback\`.
   - Local HTTP server (embedded in \`auth_controller.py\`) listens once, captures \`code\`, exchanges for tokens via \`grant_type=authorization_code\`.
   - On success, AppState.auth_status → \`ok\`; lamp turns green within 3 s.
2. **Token Handling**
   - Store \`id_token\` in memory only; **no refresh token** stored.
   - Automatically refresh by re-login when a 401 appears.
3. **Security**
   - \`PKCE\` (S256) required.
   - Loopback redirect uses random, non-privileged port; listener shuts down after 30 s.
4. **Tests**
   - \`tests/gui/test_auth_controller.py\` mocks Cognito endpoints and asserts state lamp transitions (\`off→pending→ok\`).
   - Integration test on CI uses headless Chrome + local Cognito stub.
5. **Docs**
   - \`docs/gui/login_flow.md\` includes sequence diagram and troubleshooting tips (e.g., Keychain pop-ups on macOS).

### Technical Notes

- env vars in GUI: \`COGNITO_DOMAIN\`, \`COGNITO_CLIENT_ID\`.
- Python code for PKCE and auth_url construction.
- Idle logout: when AppState detects no user activity for 60 min, clear token.
"
