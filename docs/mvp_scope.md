# MVP Scope Definition: 3 Sites × 10 Tasks

**Version**: v1.0
**Last Updated**: 2025-11-16
**Purpose**: Define minimal viable product scope for initial implementation and validation

---

## 1. Site Selection (3 Core Sites)

### 1.1 Site #1: shop.local (E-commerce Platform)
**Rationale**:
- **High frequency**: Most common web agent use case
- **Complex interactions**: Search, filter, cart, checkout, reviews
- **State persistence**: Orders, wishlists, payment methods
- **Multi-step flows**: Browse → Add → Checkout → Track
- **Representative tasks**: B (Shopping), C (Returns), K (Social splits)

**Technical Requirements**:
- Product catalog (100-500 items)
- Search & filter engine
- Cart & checkout flow
- User account system
- Order history & tracking
- Payment method management
- Review & rating system

---

### 1.2 Site #2: bank.local (Banking & Finance)
**Rationale**:
- **Security-critical**: Authentication, transaction validation
- **State consistency**: Balance, transactions must be accurate
- **Cross-site impact**: Payment methods used by other sites
- **Error handling**: Overdraft, declined transactions
- **Representative tasks**: D (Finance), M (Crisis)

**Technical Requirements**:
- Account dashboard (checking, savings, credit cards)
- Transaction history
- Card management (activate, block, virtual cards)
- Payment automation (auto-pay, scheduled transfers)
- Security settings (2FA, alerts)
- Statement download

---

### 1.3 Site #3: gov.local (Government Services)
**Rationale**:
- **Workflow complexity**: Multi-stage approval processes
- **Document handling**: Upload, validation, download
- **Appointment booking**: Calendar, slots, confirmation
- **Long-term impact**: Permits, licenses, compliance
- **Representative tasks**: H (Government), A (Utilities)

**Technical Requirements**:
- Service catalog
- Document upload system (PDF, images)
- Appointment scheduling (calendar widget)
- Application status tracking
- Form validation (complex rules)
- Notification system

---

## 2. Task Selection (10 Tasks)

### Task Distribution Strategy
- **Difficulty levels**: 3 easy (L0), 4 medium (L1), 3 hard (L2)
- **Site coverage**: shop.local (5), bank.local (3), gov.local (2)
- **Dependencies**: 2 independent chains (B1→C2, D1→D4)
- **Interaction types**: All major patterns covered

### 2.1 Easy Tasks (L0): Single-site, linear flow, 5-15 steps

#### T1: B1 - Basic E-commerce Shopping
- **Site**: shop.local
- **Goal**: Search and purchase a product under budget
- **Steps**: 23 (see e2e_examples.md)
- **Memory ops**: 4 writes (order.last.*)
- **Key skills**: Search, filter, checkout
- **Success criteria**: Order confirmed, payment processed
- **Estimated dev time**: 2 days

#### T2: D1 - Check Account Balance & Recent Transactions
- **Site**: bank.local
- **Goal**: Login, verify balance >= $1000, export last 30 days transactions
- **Steps**: ~12
  1. Navigate to bank.local
  2. Login (username + password)
  3. Wait for dashboard
  4. Read balance from #account-balance
  5. Assert balance >= inputs.min_balance
  6. Click "View Transactions"
  7. Select date range (last 30 days)
  8. Click "Export CSV"
  9. Download transactions.csv
  10. Update memory: balance, last_transaction_date
- **Memory ops**: 2 writes (balance, last_check_time)
- **Assertions**: `json("env","accounts.checking.balance") >= 1000`
- **Estimated dev time**: 1.5 days

#### T3: H1 - Check Utility Bill & Due Date
- **Site**: gov.local (utility portal)
- **Goal**: Login to utility portal, check current bill amount and due date
- **Steps**: ~10
  1. Navigate to gov.local/utilities
  2. Login
  3. Select "View Bills"
  4. Read current bill amount
  5. Read due date
  6. Update memory
- **Memory ops**: 2 writes (bill.current.amount, bill.due_date)
- **Assertions**: `mem("bill.due_date") != ""`
- **Estimated dev time**: 1 day

---

### 2.2 Medium Tasks (L1): Multi-step, conditional logic, 15-35 steps

#### T4: C2 - Return & Refund
- **Site**: shop.local
- **Dependencies**: Requires T1 (B1) to have been completed
- **Goal**: Return a product from recent order
- **Steps**: 10 (see e2e_examples.md)
- **Memory ops**: 4 writes (returns.last.*)
- **Key skills**: Navigation from order history, form filling, reason selection
- **Success criteria**: Return approved, refund initiated
- **Estimated dev time**: 2 days

#### T5: B5 - Track Multiple Orders & Handle Delivery Issue
- **Site**: shop.local
- **Goal**: Check status of 3 recent orders, report delay if any order is overdue
- **Steps**: ~25
  1. Navigate to order history
  2. For each of 3 orders:
     - Read order ID, status, expected delivery
     - Compare expected vs current date
     - If overdue: click "Report Issue", select "Delivery Delay", submit
  3. Update memory with all order statuses
- **Memory ops**: 3 writes (orders.*.status)
- **Conditional logic**: IF overdue THEN report
- **Assertions**: `count(".order-issue-reported") >= 1` (if any overdue)
- **Estimated dev time**: 2.5 days

#### T6: D3 - Schedule Automatic Payment
- **Site**: bank.local
- **Goal**: Set up auto-pay for utility bill from checking account
- **Steps**: ~18
  1. Navigate to bank.local/autopay
  2. Click "Add New Auto-Pay"
  3. Select payee: "City Utilities"
  4. Select source: checking account
  5. Set amount: mem("bill.current.amount")
  6. Set frequency: "monthly"
  7. Set start date: mem("bill.due_date") - 3 days
  8. Review & confirm
  9. Verify auto-pay is active
- **Memory ops**: 3 writes (autopay.utility.id, autopay.utility.status, autopay.utility.next_date)
- **Cross-site data**: Uses bill amount from T3
- **Assertions**: `json("env","autopay.*.payee") == "utilities"`
- **Estimated dev time**: 2 days

#### T7: H2 - Submit Permit Application with Documents
- **Site**: gov.local
- **Goal**: Apply for parking permit by filling form and uploading documents
- **Steps**: ~20
  1. Navigate to gov.local/permits
  2. Select "Parking Permit"
  3. Fill personal info (from memory)
  4. Fill vehicle info (inputs)
  5. Upload: vehicle_registration.pdf
  6. Upload: proof_of_address.pdf
  7. Review application
  8. Submit
  9. Note application ID
  10. Download receipt
- **Memory ops**: 2 writes (permits.parking.application_id, permits.parking.state)
- **File uploads**: 2 PDFs
- **Assertions**: `text("#application-state") == "submitted"`
- **Estimated dev time**: 2.5 days

---

### 2.3 Hard Tasks (L2): Multi-site, complex logic, 35+ steps

#### T8: D4 - Credit Card Replacement & Binding Update
- **Site**: bank.local, shop.local, gov.local
- **Goal**: Replace expiring card and update all merchant bindings
- **Steps**: 50 (see e2e_examples.md)
- **Memory ops**: 3 writes + 3 cross-site verifications
- **Key skills**: Multi-site navigation, batch updates, state synchronization
- **Success criteria**: New card active, old card blocked, 3+ bindings updated
- **Estimated dev time**: 4 days

#### T9: M1 - Lost Bank Card Crisis Handling
- **Site**: bank.local, shop.local, gov.local (+ 2 more)
- **Goal**: Block lost card, issue virtual card, update 5+ merchants
- **Steps**: 62 (see e2e_examples.md)
- **Memory ops**: 4 writes + 5 binding updates
- **Key skills**: Emergency response, parallel updates, fallback strategy
- **Success criteria**: Card blocked, virtual card active, critical merchants updated
- **Estimated dev time**: 5 days

#### T10: K2-AA Split - Roommate Expense Sharing
- **Site**: shop.local, bank.local
- **Goal**: Review shared expenses (utilities, groceries) and split bills with roommate
- **Steps**: ~40
  1. Navigate to shop.local/orders
  2. Filter orders by tag: "shared" (last month)
  3. Calculate total shared expenses
  4. Navigate to bank.local/payments
  5. Create payment request to roommate
  6. Set amount: total / 2
  7. Add memo: "October shared expenses"
  8. Send request
  9. Wait for confirmation
  10. Update memory: settlements.2025-10.state = "sent"
- **Memory ops**: 3 writes (settlements.*.amount, settlements.*.state, settlements.*.members)
- **Cross-site data**: Order data from shop.local → Payment in bank.local
- **Math logic**: Sum orders, divide by member count
- **Assertions**: `json("env","settlements.2025-10.state") == "sent"`
- **Estimated dev time**: 3.5 days

---

## 3. Dependency Graph

```
Independent:
  T1: B1 (Shopping) ────┐
                         ├──→ T4: C2 (Return)
                         │
                         ├──→ T5: B5 (Track Orders)
                         │
                         └──→ T10: K2 (AA Split)

  T2: D1 (Check Balance) ──→ T6: D3 (Auto-Pay)
                           │
                           └──→ T8: D4 (Card Replacement) ──→ T9: M1 (Crisis)

  T3: H1 (Check Bill) ──────→ T6: D3 (Auto-Pay)

  T7: H2 (Permit Application) [independent]
```

**Critical Path**: T1 → T4 → T8 → T9 (longest chain: 4 tasks)

---

## 4. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
**Deliverables**:
- Basic Next.js/React scaffold for 3 sites
- Shared UI component library (Button, Input, Form, Table)
- SQLite database schema (users, products, accounts, orders, applications)
- Nginx routing config (shop.local, bank.local, gov.local)
- Basic auth system (username/password, session)

**Tasks**: Setup infrastructure for all 3 sites

---

### Phase 2: Easy Tasks Implementation (Week 3-4)
**Deliverables**:
- T1: B1 (Shopping) - Full e-commerce flow
- T2: D1 (Check Balance) - Banking dashboard
- T3: H1 (Check Bill) - Utility portal

**Focus**: Validate end-to-end flow, assertions DSL, memory system

---

### Phase 3: Medium Tasks (Week 5-7)
**Deliverables**:
- T4: C2 (Return)
- T5: B5 (Track Orders)
- T6: D3 (Auto-Pay)
- T7: H2 (Permit with Uploads)

**Focus**: Complex forms, file uploads, cross-task dependencies

---

### Phase 4: Hard Tasks & Integration (Week 8-10)
**Deliverables**:
- T8: D4 (Card Replacement)
- T9: M1 (Crisis Handling)
- T10: K2 (AA Split)

**Focus**: Multi-site coordination, batch updates, error recovery

---

### Phase 5: Testing & Refinement (Week 11-12)
**Deliverables**:
- DOM perturbation system (seed-based randomization)
- Data perturbation (price fluctuation, stock changes)
- Baseline agent evaluation (GPT-4, Claude)
- Bug fixes & edge cases
- Documentation

---

## 5. Technical Stack (MVP)

### Frontend (Per Site)
- **Framework**: Next.js 14 (App Router)
- **Styling**: Tailwind CSS
- **Components**: shadcn/ui (customized)
- **State**: React Context + localStorage (simulate sessions)

### Backend (Unified)
- **Runtime**: Node.js 20
- **Framework**: Express.js
- **Database**: SQLite (with migrations via Knex.js)
- **API**: RESTful + Env JSON API (`/env/*`)

### Agent Interface
- **Browser**: Playwright
- **Middleware**: Custom recorder (logs steps, screenshots)
- **Assertions**: Custom DSL interpreter (JavaScript)

### Infrastructure
- **Reverse Proxy**: Nginx (or Caddy for easier HTTPS)
- **Containers**: Docker Compose (3 frontend services + 1 backend + 1 DB)
- **Seed Control**: Environment variable `SEED=<int>`

---

## 6. Success Criteria for MVP

### Must Have
- ✅ All 10 tasks executable with oracle traces
- ✅ Assertions DSL working for all success criteria
- ✅ Memory system: read preconditions, write results, cross-task refs
- ✅ DOM perturbation: 3+ seed variations per task
- ✅ Env JSON API: all validations queryable
- ✅ Baseline metrics: SR, LH-F1, MemRet for 1 agent

### Should Have
- ✅ Data perturbation: prices ±20%, stock random
- ✅ Error recovery: timeout, network error, assertion fail
- ✅ Replay: deterministic from seed + trace
- ✅ Documentation: setup guide, API reference

### Nice to Have
- 🔲 Network perturbation: latency, packet loss
- 🔲 Visual regression tests
- 🔲 Multi-agent benchmarking (3+ agents)

---

## 7. Resource Estimation

### Development Time
- **Phase 1**: 2 weeks (1 senior dev)
- **Phase 2**: 2 weeks (1 senior dev)
- **Phase 3**: 3 weeks (1 senior dev + 1 mid-level)
- **Phase 4**: 3 weeks (1 senior dev + 1 mid-level)
- **Phase 5**: 2 weeks (1 senior dev)

**Total**: ~12 weeks (~3 months) with 1.5 FTE average

### Infrastructure Cost
- **Compute**: $0 (local dev) or $50/month (cloud VM)
- **Storage**: <10GB (SQLite + screenshots)
- **No external API costs** (all synthetic)

---

## 8. Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| DOM randomization too complex | High | Medium | Start with simple id/class suffix, expand gradually |
| Playwright stability issues | Medium | Low | Use headful mode for debugging, save traces |
| Assertions DSL edge cases | Medium | Medium | Start with subset (ALL, ANY, json, text), add more later |
| Cross-site state sync bugs | High | Medium | Centralize state in backend, use transactions |
| Time overrun | Medium | Medium | Prioritize T1-T7, make T8-T10 stretch goals |

---

## 9. Next Steps (Immediate)

1. **Set up Git repo** with monorepo structure:
   ```
   /backend       # Express + SQLite
   /sites
     /shop        # Next.js (shop.local)
     /bank        # Next.js (bank.local)
     /gov         # Next.js (gov.local)
   /shared        # UI components, types, utils
   /agent         # Playwright scripts, DSL interpreter
   /tasks         # TaskSpec JSONs, Oracle traces
   ```

2. **Create DB schema** (see schema_draft.sql below)

3. **Implement T1 (B1)** as proof-of-concept (PoC)

4. **Validate assertions DSL** with T1

5. **Expand to T2, T3** to cover all 3 sites

---

## Appendix A: Database Schema (Draft)

```sql
-- Users & Auth
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  email TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- E-commerce (shop.local)
CREATE TABLE products (
  id INTEGER PRIMARY KEY,
  sku TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  price REAL NOT NULL,
  category TEXT,
  stock INTEGER DEFAULT 0
);

CREATE TABLE orders (
  id TEXT PRIMARY KEY,  -- e.g., "O-10001"
  user_id INTEGER NOT NULL,
  total REAL NOT NULL,
  state TEXT NOT NULL,  -- confirmed, shipped, delivered
  shipping_speed TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE order_items (
  order_id TEXT NOT NULL,
  sku TEXT NOT NULL,
  quantity INTEGER NOT NULL,
  price REAL NOT NULL,
  FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE returns (
  id TEXT PRIMARY KEY,  -- e.g., "R-50001"
  order_id TEXT NOT NULL,
  reason TEXT,
  state TEXT NOT NULL,  -- submitted, approved, refunded
  refund_amount REAL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (order_id) REFERENCES orders(id)
);

-- Banking (bank.local)
CREATE TABLE accounts (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL,
  type TEXT NOT NULL,  -- checking, savings
  balance REAL NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE cards (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL,
  last4 TEXT NOT NULL,
  type TEXT NOT NULL,  -- physical, virtual
  state TEXT NOT NULL,  -- active, blocked, expired
  exp_date TEXT,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE transactions (
  id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL,
  amount REAL NOT NULL,
  type TEXT NOT NULL,  -- debit, credit
  description TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE autopay (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL,
  payee TEXT NOT NULL,
  account_id INTEGER NOT NULL,
  amount REAL,
  frequency TEXT,  -- monthly, weekly
  next_date DATE,
  state TEXT NOT NULL,  -- active, paused
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (account_id) REFERENCES accounts(id)
);

-- Government (gov.local)
CREATE TABLE applications (
  id TEXT PRIMARY KEY,  -- e.g., "APP-7788"
  user_id INTEGER NOT NULL,
  type TEXT NOT NULL,  -- parking_permit, residence_permit
  state TEXT NOT NULL,  -- submitted, processing, approved
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE appointments (
  id TEXT PRIMARY KEY,  -- e.g., "APT-9988"
  application_id TEXT,
  user_id INTEGER NOT NULL,
  date DATE NOT NULL,
  time TEXT NOT NULL,
  state TEXT NOT NULL,  -- booked, completed, cancelled
  FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Utilities (shared)
CREATE TABLE bills (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL,
  type TEXT NOT NULL,  -- electricity, water, gas
  amount REAL NOT NULL,
  due_date DATE NOT NULL,
  state TEXT NOT NULL,  -- unpaid, paid
  FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Merchant Bindings (cross-site)
CREATE TABLE merchant_bindings (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL,
  merchant TEXT NOT NULL,  -- shop_local, util_local, etc.
  card_last4 TEXT NOT NULL,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Memory KV Store
CREATE TABLE memory_kv (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,  -- JSON serialized
  ts DATETIME DEFAULT CURRENT_TIMESTAMP,
  source TEXT,
  confidence REAL DEFAULT 1.0
);
```

---

## Summary

**MVP Scope**: 3 sites × 10 tasks covering 70% of interaction patterns
**Development Time**: ~12 weeks
**Resource**: 1.5 FTE (1 senior + 0.5 mid-level)
**Infrastructure Cost**: <$50/month (or free on local)
**Risk**: Medium (manageable with phased approach)

This MVP will validate:
1. Technical feasibility of synthetic environment
2. Assertions DSL expressiveness
3. Memory system robustness
4. Baseline agent performance
5. Scalability path to 64 tasks

Once MVP is successful, expand to:
- 10 more sites (food, travel, health, etc.)
- 54 more tasks (total 64)
- Advanced perturbations (network, visual)
- Multi-agent benchmarking
