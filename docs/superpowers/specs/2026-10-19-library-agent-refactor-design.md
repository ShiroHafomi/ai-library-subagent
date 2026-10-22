# Library Agent Refactor Design

## Goal

Refactor the library assistant into a Deep Agents coordinator with Book, Policy, Borrow, and Return subagents; retain Gemini, MySQL, LangGraph short-term memory, and existing long-term memory tools while ensuring no model-controlled input can authorize persistent transactions.

## Existing constraints

- The current MySQL initializer creates only `books(id, title, author, category, is_available)` and `user_memories`.
- No migration framework, `members` table, `borrow_records` table, or trusted authentication/authorization mechanism exists.
- `data/policy.md` explicitly identifies itself as demo data; its sample loan duration is not a trusted production policy source.
- Existing working-tree changes to borrow/return agents/tools and main-agent coordination must be preserved and corrected in place.

## Design

- Main Agent uses one Vietnamese system prompt, Deep Agents delegation to all four Vietnamese subagents, existing memory tools, and `InMemorySaver` keyed by `thread_id`. Main Agent does not access business SQL.
- Book lookup stays a parameterized MySQL tool (`search_books`), supporting actual `books` columns and availability. Policy lookup stays the document-backed `answer_policy` tool and may not invent absent rules.
- Borrow and return tools use dedicated MySQL transactions. SQL identifiers are static; values are parameterized. The borrow path locks member and book rows, validates active status, availability, trusted policy loan duration and active-loan limit, inserts the record, updates book availability, then commits. The return path locks the active borrow record then its book row, verifies the trusted actor is authorized for the member, marks the record returned, recalculates availability from remaining active loans, then commits. Every failure rolls back; success is returned only after commit.
- Transaction authority is an application-owned `ContextVar` value, not an LLM-visible tool argument. A trusted context includes authenticated actor/member identity, explicit authorization, an application-verified confirmation token/flag, and trusted policy settings. The context manager is intended only for a future authenticated application boundary; current CLI does not set it. Missing or invalid context, policy, or identity fails closed before opening a database connection. `member_id` and `confirmed` are not tool parameters and never establish authority.
- Add a forward-only, non-destructive, versioned SQL migration creating InnoDB `members` and `borrow_records` tables compatible with existing `books.id`; do not mutate or drop existing data/tables. Migration application is explicit and idempotent.
- Tests use mocks only for MySQL transaction behavior, including failure/rollback and concurrent-safe row-lock query patterns. No test connects to a real database or performs production writes.

## Verification

Run syntax/import checks and all unit tests. Verify fail-closed paths do not connect to MySQL, transactions commit only on success and roll back on all post-start errors, double-return is rejected, and four subagents/tools are registered correctly. Real DB integration, Gemini invocation, and authentic identity/authorization remain unverified until configured.
