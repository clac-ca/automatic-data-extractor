# 080 – Migration and Rollout

**Work Package ID:** 080  
**Initiative:** `ade-web-refactor`  
**Owner:** \<Tech Lead, ade-web>  
**Status:** In progress  
**Last Updated:** 2025-11-29  

**Related documents:**

- `010-WORK-PACKAGE.md`
- `020-ARCHITECTURE.md`
- `030-UX-FLOWS.md`
- `040-DESIGN-SYSTEM.md`
- `050-RUN-STREAMING-SPEC.md`
- `060-NAVIGATION.md`
- `070-TEST-PLAN.md`

---

## 0. Repo Layout & Archive Strategy

We will **archive the current `apps/ade-web` as read-only** and stand up the new app in a clean directory:

- **Move existing app → `apps/ade-web-legacy/`.** Preserve its source for reference; stop using it for new development.
- **Rename package metadata** inside the legacy app to `ade-web-legacy` to avoid npm/yarn name collisions with the new app.
- **New app lives at `apps/ade-web/`** following the structure in `020-ARCHITECTURE.md`. Fresh Vite/TypeScript config, strict mode on by default.
- **Build/serve commands (`ade build`, `ade start`) target the new app only.** CI/dev scripts should no longer run lint/tests/builds for `apps/ade-web-legacy` except when explicitly invoked (e.g., `npm run build` inside legacy for debugging).
- **Static asset path remains unchanged:** new app still emits to `apps/ade-api/src/ade_api/web/static` so backend integration stays stable.
- **Guardrails:** Add README note in `apps/ade-web-legacy` marking it archived; ensure navigation/streaming code in the new app does not import from legacy.

This strategy lets us cut over without losing reference history and keeps the new architecture uncluttered.

## 1. Purpose and Objectives

This document defines **how** the refactored `ade-web` application will be deployed to production and gradually rolled out to users with minimal risk and downtime.

Primary objectives:

1. Safely migrate from the legacy `ade-web` implementation to the refactored version.
2. Minimize user-visible disruption (ideally zero downtime).
3. Provide clear, actionable **runbooks** for:
   - Cutover to the new version
   - Rollback to the old version (if needed)
4. Ensure observability, monitoring, and alerting are in place before user traffic is shifted.
5. Align all stakeholders on communication, responsibilities, and timelines.

---

## 2. In Scope / Out of Scope

### 2.1 In Scope

- Deployment of refactored `ade-web` to:
  - Development / integration environments
  - Staging / pre-production
  - Production
- Migration of configuration, environment variables, and secrets required by the new web app.
- Any data migration steps required for the frontend to function correctly (e.g., changes to local persistence format or backend compatibility).
- Traffic migration strategy (e.g., feature flags, canary, blue/green).
- Rollback strategy and testing.
- Monitoring, logging, and alerting for the new deployment paths.

### 2.2 Out of Scope

- Major backend data schema migrations unrelated to `ade-web` refactor.
- New product features not directly tied to the refactor.
- Long-term decommissioning of legacy infrastructure (may be covered by a separate work package once stability is confirmed).

---

## 3. Assumptions and Constraints

### 3.1 Assumptions

- All core functional and regression tests pass in CI as defined in `040-TESTING-AND-QA.md`.
- Observability and dashboards for key metrics exist as per `050-OBSERVABILITY.md`.
- The refactored `ade-web` can coexist with the legacy version at least at the infrastructure level (e.g., via different routes, hosts, or feature flags).
- Required infrastructure (environments, CD pipelines, feature-flagging service, etc.) is available and stable.
- The rollout can be scheduled in a maintenance window agreed with stakeholders (if needed).

### 3.2 Constraints

- Change-freeze windows must be respected (e.g., month-end, critical business events).
- Rollback must be **possible within 15–30 minutes**, with a clearly documented path.
- The rollout must support gradual exposure of the new UI (e.g., internal users → beta users → general population).

---

## 4. Environments, Dependencies, and Entry Criteria

### 4.1 Environments

- **DEV / Integration**
  - Purpose: rapid iteration, integration testing.
  - Access: engineers only.
- **STAGING / Pre-production**
  - Purpose: end-to-end validation, performance testing, UAT.
  - Access: engineers + selected business users.
- **PRODUCTION**
  - Purpose: live user traffic.
  - Access: restricted to authorized personnel as per operational policy.

### 4.2 Dependencies

- CI/CD pipelines for `ade-web` refactor are configured and stable.
- Backend APIs required by the refactored web app are deployed and backward compatible.
- Feature flag system (if used) is integrated in both frontend and backend.
- Secrets/config management (e.g., Vault/KMS/Environment variables) supports both legacy and new variants.

### 4.3 Entry Criteria for Migration

The migration and rollout process may begin once:

- ✅ All critical and high severity bugs for the refactor are closed or explicitly waived.  
- ✅ Test coverage thresholds defined in `040-TESTING-AND-QA.md` are met.  
- ✅ Performance benchmarks show no significant regression vs legacy (`p95` and `p99` latencies within agreed budgets).  
- ✅ All required dashboards and alerts are in place and validated.  
- ✅ Stakeholders approve the rollout plan and timeline.

---

## 5. Migration Strategy

We will use a **phased rollout with the ability to quickly rollback**. The strategy combines:

- **Blue/Green deployment** at the infrastructure level:
  - Legacy = **Blue**
  - Refactored = **Green**
- **Gradual traffic shifting** using:
  - Feature flags, or
  - Load balancer / routing rules.

### 5.1 High-Level Phases

1. **Phase 1 – Foundation**
   - Deploy refactored `ade-web` to DEV and STAGING.
   - Validate functionality, performance, accessibility, and observability.
2. **Phase 2 – Shadow / Dark Launch (optional)**
   - Run the refactored UI behind a feature flag or on a separate domain.
   - Route mirrored or limited traffic to validate behavior without impacting users.
3. **Phase 3 – Controlled Rollout**
   - Gradually enable refactored UI to:
     - Internal staff / QA
     - Beta users
     - Small targeted percentage of general users (e.g., 5% → 25% → 50%).
4. **Phase 4 – Full Cutover**
   - Promote refactored version to 100% of production traffic.
   - Keep legacy deployment hot but unused for a defined observation period.
5. **Phase 5 – Legacy Decommissioning**
   - After a stable period (e.g., 2–4 weeks) with no major incidents, decommission legacy `ade-web`.

---

## 6. Detailed Rollout Plan

### 6.1 Pre-Rollout Checklist (Staging)

**Owner:** Tech Lead / QA Lead

- [ ] Refactored `ade-web` deployed to STAGING via standard pipeline.
- [ ] All smoke tests pass (start-up, login, core flows).
- [ ] Regression tests (manual and automated) executed and reported.
- [ ] Performance tests executed; results reviewed and signed off.
- [ ] Security checks (static/dynamic analysis, dependency scanning) pass or are approved.
- [ ] Monitoring dashboards:
  - [ ] HTTP error rates (4xx, 5xx).
  - [ ] Latency (p50, p90, p95, p99).
  - [ ] Frontend errors (e.g., JS errors, console errors).
- [ ] Alerts configured and verified (e.g., by simulating errors).
- [ ] Runbook (this document) reviewed and approved by:
  - [ ] Engineering
  - [ ] SRE/Operations
  - [ ] Product / Business Owner

### 6.2 Controlled Production Rollout

**Owner:** Release Manager / On-call Engineer

Suggested steps (adjust as needed to your tooling):

#### Step 1 – Deploy Green (Refactored) in Production (No Traffic)

- [ ] Deploy new `ade-web` to production environment as “Green”.
- [ ] Ensure it runs on separate hosts / containers / pods with no public traffic.
- [ ] Run production smoke tests directly against Green:
  - Health endpoints
  - Core flows (e.g., login, dashboard view, common user journeys)
- [ ] Verify logs and metrics for Green environment.

#### Step 2 – Internal Users and Staff

- [ ] Enable access to Green via:
  - Internal feature flag, or
  - Alternate URL (e.g., `ade-web-new.internal`), or
  - Whitelisted IP range.
- [ ] Ask internal users to test key flows and report any issues.
- [ ] Track all issues in a central place (e.g., JIRA/Linear board for `ade-web-refactor`).
- [ ] Fix any critical issues before proceeding.

#### Step 3 – Limited External Rollout (Canary)

- [ ] Enable refactored `ade-web` for a small percentage of live traffic (e.g., 5%).
  - Implementation options:
    - Feature flag targeting a random user bucket.
    - Load balancer rules (e.g., based on cookies or random fraction).
- [ ] Monitor:
  - Error rates vs Blue (legacy).
  - Latency and resource utilization.
  - User behavior metrics (drop-offs, conversion where applicable).
- [ ] Keep this state for an agreed observation window (e.g., 1–2 hours).
- [ ] If stable, gradually increase to 25%, 50%, 75% traffic, each time:
  - Re-running smoke checks.
  - Examining dashboards.
  - Confirming no severe user reports.

#### Step 4 – 100% Cutover

- [ ] Shift all traffic to Green (refactored `ade-web`).
- [ ] Keep Blue (legacy) running but not serving public traffic.
- [ ] Mark the milestone in logs/monitoring (for later forensics).
- [ ] Continue heightened monitoring for the “stability window” (e.g., 24–72 hours).

---

## 7. Cutover Runbook (Production)

The following is a **step-by-step runbook** for the final production cutover.

### 7.1 Roles and Responsibilities

- **Release Manager (RM):** Owns the deployment and communication.
- **Tech Lead (TL):** Approves go/no-go decisions, coordinates debugging if issues arise.
- **SRE / On-call Engineer:** Manages infrastructure changes, monitors systems.
- **QA Lead:** Verifies core functionality post-deploy.
- **Product Owner (PO):** Signs off on business readiness and final go-live.

### 7.2 Timeline Example (Adjust to Local Time)

> Actual timestamps to be updated prior to rollout.

- **T-60 min**
  - RM: Confirms the change is on the calendar and that on-call engineers are available.
  - SRE: Verifies backup / snapshot status for relevant components (if any).
- **T-45 min**
  - TL/RM: Confirms no open critical incidents or active incidents involving `ade-web`.
- **T-30 min**
  - QA: Completes last-minute smoke test on STAGING.
  - RM: Sends “deployment starting” notice to relevant channels.
- **T-10 min**
  - SRE: Prepares pipeline or scripts for switching traffic.
  - TL: Reiterates rollback criteria and decision thresholds.
- **T (Cutover)**
  - SRE: Shift agreed portion of traffic from Blue to Green (e.g., 5% or 25%).
  - QA: Execute **Production Smoke Test Script** (see Appendix A).
  - All: Monitor dashboards and logs.
- **T+30 min**
  - TL/RM: Review metrics and user feedback.
  - If acceptable, increase traffic share (e.g., to 50%).
- **T+1h, T+2h, ...**
  - Repeat: Increase traffic, revalidate, and monitor until 100% traffic is on Green.
- **T+24–72h**
  - Stability window. No major changes unless critical.
  - After window, TL/PO sign off on decommissioning Blue (separate change).

---

## 8. Rollback Strategy

Rollback must be **simple, documented, and tested**.

### 8.1 Rollback Triggers

Rollback is considered if any of the following occur after cutover:

- Sustained increase in error rate beyond agreed threshold (e.g., 2x baseline, or >1% 5xx).
- Significant latency degradation (e.g., p95 latency increases by >50%).
- Critical business KPIs are impacted (e.g., login failures, transaction failures, unacceptable drop in completion rates).
- Unacceptable user experience issues (e.g., widespread rendering failures).
- Security or compliance issues discovered in the new version.

### 8.2 Rollback Mechanism

Preferred mechanisms (exact method depends on infrastructure):

1. **Routing-based rollback (fastest)**
   - Adjust load balancer / gateway configuration:
     - Set traffic allocation back to 0% Green, 100% Blue.
   - Confirm:
     - Blue is still healthy and serving correctly.
     - Upstream/downstream dependencies are compatible.

2. **Release-based rollback**
   - Use deployment tool (e.g., Helm, Argo, GitOps, CI/CD) to:
     - Redeploy last known good version of `ade-web`.
   - Validate with smoke tests.

### 8.3 Rollback Runbook (Routing-based)

- [ ] RM announces decision to rollback in main channel + incident channel (if opened).
- [ ] SRE updates traffic rules to route all requests back to Blue.
- [ ] QA runs **Rollback Smoke Test Script** (mirror of Production Smoke Test Script against Blue).
- [ ] TL confirms:
  - Error rates returned to normal.
  - No new incident conditions triggered.
- [ ] RM documents in change log:
  - Time of rollback.
  - Primary reason (with links to tickets, dashboards).
  - Next steps.

### 8.4 Post-Rollback Actions

- Open or update an incident / root cause analysis (RCA) ticket.
- Attach relevant logs, metric snapshots, and user reports.
- Prioritize and fix issues before planning another rollout attempt.
- Update this runbook based on lessons learned.

---

## 9. Monitoring, Metrics, and Alerts

### 9.1 Key Technical Metrics

- **Availability**
  - HTTP 5xx rate, 4xx anomalies.
- **Performance**
  - p50, p90, p95, p99 latency for:
    - Key endpoints (e.g., `/login`, `/dashboard`, primary flows).
- **Resource Utilization**
  - CPU, memory usage for Green vs Blue deployments.
- **Frontend Metrics**
  - JS error rate.
  - Page load time (LCP, FID, CLS if using web vitals).
  - SPA navigation errors, if applicable.

### 9.2 Business / Product Metrics

- Login success rate.
- Key funnel completion rates (e.g., complete transaction, submit form).
- Session duration / bounce rate (if tracked).
- User-reported issues (e.g., via support or in-app feedback).

### 9.3 Alerting

Before rollout:

- [ ] Alerts configured for:
  - High error rate (5xx, application errors).
  - Significant latency degradation.
  - Significant drop in key business KPIs (if supported).
- [ ] Alert thresholds agreed and documented.
- [ ] Alert channels tested (e.g., Slack, email, PagerDuty).

---

## 10. Communication Plan

### 10.1 Stakeholders

- Engineering team (`ade-web`)
- SRE/Operations
- Product management
- Customer support
- Key business stakeholders

### 10.2 Communication Channels

- Internal chat (e.g., Slack) for real-time progress.
- Email or internal announcements for broader updates.
- Incident management system for high-severity issues.

### 10.3 Communication Milestones

- **Pre-rollout announcement**
  - What will change, expected impact, maintenance window (if any).
- **Start of deployment**
  - “Deployment starting” message with link to this runbook and dashboards.
- **Intermediate updates**
  - When traffic percentages change (e.g., at 25%, 50%, 75%).
- **Go/No-Go decisions**
  - After major checkpoints, with supporting metrics.
- **Completion**
  - Confirm rollout completed successfully, status of legacy Blue environment.
- **Post-incident / rollback (if needed)**
  - Summary of issues, root cause, and remediation plan.

---

## 11. Risks and Mitigations

| Risk                                             | Likelihood | Impact | Mitigation                                                                 |
|--------------------------------------------------|------------|--------|----------------------------------------------------------------------------|
| Uncaught critical bug in refactored UI          | Medium     | High   | Aggressive testing, canary rollout, quick rollback path.                  |
| Backend incompatibility with new frontend        | Low–Med    | High   | Contract tests, backward compatible APIs, early integration in STAGING.   |
| Performance regression under real load           | Medium     | High   | Load testing, gradual rollout, close monitoring of latency & resource use.|
| Feature flag / routing misconfiguration          | Low        | High   | Configuration reviews, dry runs in lower envs, automated tests.           |
| Insufficient logging/metrics for debugging       | Medium     | Medium | Observability work package, logging guidelines, pre-rollout validation.   |
| Rollback fails or is slow                        | Low–Med    | High   | Rehearse rollback in STAGING, clear and simple rollback steps.           |
| Poor communication causing confusion             | Medium     | Medium | Clear communication schedule, designated RM, prepared announcement templates. |

---

## 12. Acceptance Criteria / Definition of Done

This work package is considered **complete** when:

1. ✅ Refactored `ade-web` is deployed to production and serving **100%** traffic.  
2. ✅ Legacy Blue environment is no longer serving user traffic and has a clear decommissioning plan.  
3. ✅ No open P0 or P1 issues directly caused by the refactor remain.  
4. ✅ Monitoring dashboards show stable error rates and latency at or better than pre-refactor baselines over the stability window.  
5. ✅ Rollback procedure has been:
   - Validated in staging, and
   - Either used successfully or confirmed to be immediately usable.  
6. ✅ Stakeholders (Engineering, SRE, Product, Support) sign off on the rollout.  
7. ✅ This runbook is updated with:
   - Any deviations from the plan.
   - Lessons learned and improvements for future rollouts.  

---

## Appendix A – Production Smoke Test Script (Example)

These tests should be executed **after each major traffic shift** (e.g., 5%, 25%, 50%, 100%).

1. **Availability**
   - Confirm the main URL loads successfully.
   - Check that no obvious errors appear on the landing page.

2. **Authentication**
   - Login with a test account.
   - Logout and re-login successfully.

3. **Core Flows**
   - Navigate to primary dashboard / home after login.
   - Execute at least one core user action (e.g., create/update an entity, submit a form).
   - Verify results are persisted and displayed correctly.

4. **Navigation & Routing**
   - Navigate between main sections.
   - Use browser back/forward.
   - Refresh key pages and ensure state is sensible.

5. **Error Handling**
   - Trigger a known validation error (e.g., invalid input).
   - Check that error messages are clear and not broken.

6. **Performance (Quick Check)**
   - Subjective: pages should load within a reasonable time; no obvious slowdowns.
   - Confirm key performance metrics on dashboards are within thresholds.

7. **Cross-Browser / Device (If feasible)**
   - Run a small set of checks in at least one alternative browser/device combo.

---

## Appendix B – Rollback Smoke Test Script

If rollback is performed, repeat the **Production Smoke Test Script** against the **legacy Blue** environment to confirm that:

- Users can successfully use the system as before.
- No new regressions have been introduced by the rollback itself.
