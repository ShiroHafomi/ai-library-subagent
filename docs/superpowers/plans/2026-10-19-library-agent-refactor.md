# Library Agent Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Safely refactor the library assistant to use four Deep Agents subagents and implement fail-closed MySQL borrow/return transactions.

**Architecture:** Main Agent delegates to specialized Vietnamese subagents and retains memory/checkpoint support. Business tools use static parameterized SQL and schema migration; transaction authority comes exclusively from application-owned trusted execution context, absent by default.

**Tech Stack:** Python 3.11+, Deep Agents, LangChain `@tool`, LangGraph `InMemorySaver`, Gemini via LangChain, MySQL Connector/Python, unittest.

**Spec:** `docs/superpowers/specs/2026-10-19-library-agent-refactor-design.md`

## Global Constraints

- Preserve MySQL, Gemini, Deep Agents, LangChain tools, and LangGraph short-term checkpointing.
- Never use LLM-provided `member_id` or `confirmed` as authorization evidence.
- Missing trusted identity, authorization, verified confirmation, or policy must prevent database writes.
- Use only the observed `books(id, title, author, category, is_available)` schema as the starting point.
- Do not drop or rewrite existing tables or data; migration only creates new tables.
- All database tests use mocks; do not connect to a real database.

## Review Focus

- Missing/malformed trusted context: reject before opening a DB connection; test in Task 2.
- Unsafe/untrusted loan policy values: reject before connecting; test in Task 2.
- Transaction exceptions after mutation begins: rollback and never report success; test in Tasks 2 and 3.
- Return racing with another return: lock the record, reject a no-longer-borrowed record; test in Task 3.
- A title containing SQL metacharacters: treat as ordinary bound search text; test in Task 4.

---

### Task 1: Trusted execution context and schema migration

**Files:**
- Create: `tools/transaction_context.py`
- Create: `database/migrations/001_create_member_borrow_tables.sql`
- Create: `database/migrations/__init__.py`
- Create: `database/migrations/runner.py`
- Test: `tests/test_transaction_context.py`
- Test: `tests/test_migrations.py`

**Interfaces:**
- Produces `TrustedTransactionContext`, `trusted_transaction_context(context)`, and `get_trusted_transaction_context()`.
- Context fields: authenticated actor identifier, authorized member identifier, application-verified confirmation, trusted `loan_days`, and trusted `max_active_loans`.
- Migration runner exposes `apply_migrations(connection_factory=get_connection)` and records applied migration versions in a new migration metadata table.

- [ ] Test valid context lookup, absent context lookup, and nested-context restoration.
- [ ] Test migration runner executes a new migration once, records version, and safely skips an already-recorded migration.
- [ ] Implement the immutable typed context and fail-closed accessor; validate positive policy limits and matching actor/member identity fields at construction.
- [ ] Add forward-only InnoDB SQL for `members(id, name, status)` and `borrow_records(id, member_id, book_id, borrowed_at, due_at, returned_at, status)` with foreign keys/indexes compatible with `books.id`; do not create/drop existing core tables.
- [ ] Implement migration tracking and execution with commit on success, rollback on error, and cursor/connection cleanup.
- [ ] Run `python -m unittest tests.test_transaction_context tests.test_migrations -v`.

### Task 2: Safe borrow tool

**Files:**
- Modify: `tools/borrow_tools.py`
- Test: `tests/test_borrow_tools.py`

**Interfaces:**
- `borrow_book(book_id: int) -> str`; no model-facing member, confirmation, or policy arguments.
- Reads trusted actor/member/confirmation/loan policy from `get_trusted_transaction_context()`.

- [ ] Test absent context, unauthorized context, unconfirmed context, and missing policy all reject without calling `get_connection`.
- [ ] Test active member + available book + below loan limit inserts record, updates availability, commits, and returns record ID only after commit.
- [ ] Test inactive/missing member, missing/unavailable book, and loan-limit reached all rollback and do not commit.
- [ ] Test an exception during insert/update rolls back and returns a non-success result.
- [ ] Implement context validation before DB connection, then use transaction and `SELECT ... FOR UPDATE` on member/book; count current borrowed records against trusted `max_active_loans`; use trusted `loan_days` for due date; insert record and mark book unavailable; commit last; rollback in every rejection/error after transaction start.
- [ ] Ensure cursor and connection cleanup is safe when failures occur.
- [ ] Run `python -m unittest tests.test_borrow_tools -v`.

### Task 3: Safe return tool

**Files:**
- Modify: `tools/return_tools.py`
- Test: `tests/test_return_tools.py`

**Interfaces:**
- `return_book(record_id: int) -> str`; no model-facing member or confirmation parameters.
- Checks trusted context and matches its authenticated member/authorization to the locked record.

- [ ] Test missing/unauthorized/unconfirmed trusted context rejects without DB connection.
- [ ] Test valid return locks record and book, updates the record, sets availability based on no remaining borrowed records, commits, and reports success after commit.
- [ ] Test missing record, wrong member, returned/invalid status, missing book, and concurrent duplicate return reject with rollback.
- [ ] Test exception during record/book update rolls back and never reports success.
- [ ] Implement static parameterized SQL and transaction locking for record and book; use `WHERE status='borrowed'` on guarded update and check rowcount; determine availability by checking remaining active records; commit last.
- [ ] Run `python -m unittest tests.test_return_tools -v`.

### Task 4: Agent prompts, book/policy tools, and coordinator

**Files:**
- Modify: `agents/main_agent.py`
- Modify: `agents/book_agent.py`
- Modify: `agents/policy_agent.py`
- Modify: `agents/borrow_agent.py`
- Modify: `agents/return_agent.py`
- Modify: `tools/book_tools.py`
- Modify: `tools/policy_agent.py`
- Test: `tests/test_main_agent.py`
- Test: `tests/test_book_tools.py`
- Test: `tests/test_policy_tools.py`

**Interfaces:**
- Exactly one `MAIN_SYSTEM_PROMPT`, entirely Vietnamese.
- Four registered subagent definitions; each has a Vietnamese system prompt and exactly its own business tool.
- Book tool uses optional `keyword`, title, author, category, and status filters mapped to actual schema columns.
- Policy tool remains `answer_policy(question)` backed by `data/policy.md`.

- [ ] Write tests for registered subagents, their correct tools, one Vietnamese main prompt, existing memory tools, and an InMemorySaver checkpointer.
- [ ] Write book-tool tests for keyword/title/author/category/status bound filters, empty results, and SQL-metacharacter handling.
- [ ] Write policy-tool tests confirming document retrieval and empty/missing-document behavior without database access.
- [ ] Remove duplicate imports/prompts and maintain delegation instruction for ambiguous references and safe handoff of previously resolved facts.
- [ ] Update borrow/return prompts to tell the model tools take only book/record identifiers, cannot grant authority, and may reject without trusted app context; ensure prompts are Vietnamese.
- [ ] Update `search_books` signature and static query construction for optional keyword and actual books columns; keep all values parameterized.
- [ ] Keep policy lookup behavior grounded only in the policy file and clearly disclose unsupported details.
- [ ] Run `python -m unittest tests.test_main_agent tests.test_book_tools tests.test_policy_tools -v`.

### Task 5: Full verification and documentation

**Files:**
- Modify: `CLAUDE.md` only if implementation commands or migration usage require documenting new behavior.
- All changed Python and tests.

- [ ] Run `python -m compileall -q agents tools database tests`.
- [ ] Run `python -m unittest discover -v`.
- [ ] Review all SQL for parameterization, static identifiers, row locks, and transaction cleanup; confirm tests never import/call a real DB connection unmocked.
- [ ] Report test output and explicitly identify unverified real MySQL/Gemini/auth-provider integration.
