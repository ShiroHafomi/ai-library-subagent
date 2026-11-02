# AI Library Assistant

Vietnamese library assistant using Deep Agents, LangChain/LangGraph, Gemini, MySQL, and Chroma RAG. The Main Agent delegates book lookup, policy questions, borrow requests, and return requests to specialized agents.

## Requirements and setup

- Python 3.11+
- MySQL reachable with schema selected by `DB_NAME`
- Gemini API key (`GEMINI_API_KEY` or `GOOGLE_API_KEY`)

Install dependencies and configure a local `.env` (never commit it):

```bash
pip install -r requirements.txt
python main.py
```

Configure the MySQL connection variables expected by `database/connection.py` (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`) and the Gemini key. For book search, also configure `DB_READONLY_USER` and `DB_READONLY_PASSWORD` as a separate MySQL account with `SELECT` permission only on `books`. The SQL toolkit may execute model-generated read queries, so database grants—not the system prompt—are the security boundary. Do not grant that account write privileges or access to unrelated tables.

The CLI initializes only the `books` and `user_memories` tables. Policy RAG uses Chroma; index the policy corpus with `python -m scripts.index_documents` before policy queries. The sample `data/policy.md` is demo content, not an authoritative source of loan duration or loan limits.

## Borrow and return security status

The Book Agent and Borrow Agent share LangChain `SQLDatabase` / `SQLDatabaseToolkit` tools for advisory book-catalog reads. The toolkit metadata is restricted to `books` and uses a separate `DB_READONLY_USER`; the query tool accepts model-generated SQL and calls `SQLDatabase.run_no_throw`, so MySQL SELECT-only grants are the actual write-prevention boundary. Borrow's catalog search is not authoritative: `borrow_book` must re-read and lock the selected book inside its write transaction. Borrow's member status and active-loan count reads also stay on that transaction cursor. Return's `find_active_loans` remains a parameterized application tool scoped by trusted `member_id`, since exposing the raw SQL toolkit over circulation tables could reveal other members' records. Return's record/book locks and active-book count likewise stay inside the atomic return transaction. These transaction-critical reads cannot be moved to toolkit calls that execute independently of the transaction. Both workflows keep writes in narrow LangChain `@tool` wrappers backed by parameterized application SQL; no arbitrary write-SQL tool is exposed to the LLM.

**The CLI circulation workflow is local-demo-only, not multi-user authentication.** Set `DEMO_MEMBER_ID` in the trusted local `.env` to an existing `members.id` (the example uses `01`); the application rejects missing or invalid values and does not infer a fallback member. This setting assigns every user of that local CLI process to the same demo member, so do not expose the process as a shared or production service. A member number typed in chat, conversation history, or an LLM tool argument is never used as identity. The application scopes identity to one agent invocation; the transaction tools accept writes only for the exact action/resource confirmed by `/confirm`. `/cancel`, `/new`, and any unrelated new user turn clear a pending confirmation. The demo currently supplies sample limits of 14 loan days and 3 active loans; these are demonstration values, not authoritative library policy. A production integration must replace the local configuration with authenticated identity, authorization, and approved policy from an application-owned boundary.

### Circulation schema prerequisite

`database/init_db.py` does not create circulation tables and the repository has no migration runner. The additive migration `database/migrations/001_create_member_borrow_tables.sql` defines `members` and `borrow_records` and references the existing `books(id)` key. It does not create member accounts or authenticate anyone.

Before applying the migration, an authorized database operator must:

1. Verify `DB_NAME` and the intended MySQL server/environment.
2. Back up the target database and review the migration SQL.
3. Apply it through the organization's controlled database change process.
4. Provision members through an authorized administrative process.

The application does not automatically run this migration. Missing tables or absent trusted context should be treated as a reason the transaction cannot proceed—not as a successful operation. Never apply this migration to production merely to run unit tests.

## Run tests

```bash
python -m unittest discover -v
```

The existing circulation tests use mocks. They verify transaction decisions but do not prove a live MySQL deployment, migration application, Gemini connectivity, or concurrent behavior against a real database. Use a dedicated disposable test database for any integration/concurrency testing; never point destructive tests at production.

## Common issues

- **Gemini key missing:** configure `GEMINI_API_KEY` or `GOOGLE_API_KEY` in the local environment.
- **Book lookup permission denied:** use a separate `DB_READONLY_USER` with `SELECT` on `books`; do not use an administrator account.
- **Policy retrieval returns no indexed content:** run `python -m scripts.index_documents` and verify the Chroma data path.
- **Borrow/return disabled because `DEMO_MEMBER_ID` is missing or invalid:** set it to the ID of an existing member for local demo use. This does not authenticate multiple CLI users; never derive the value from chat or model output.
- **Circulation tables are missing:** follow the reviewed operator migration process above; ordinary startup intentionally does not apply schema changes.

## Data and secret handling

Keep `.env`, credentials, local database files, Chroma indexes, caches, virtual environments, and generated archives out of source control and public release archives. Review archive contents before sharing.
