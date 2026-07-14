# ADR-0004: MCP server integrations are recommended now, wired up when needed

**Status:** Accepted
**Sprint:** 0
**Deciders:** Fraz Ahmed

## Context

The architecture brief for this project asks for Model Context Protocol (MCP) integration recommendations covering local filesystem, Git, ChromaDB, LanceDB, SQLite, PostgreSQL, a PDF parser, local embeddings, and Ollama. These integrations have very different maturity levels: filesystem and Git MCP servers are well-established and low-risk to configure immediately; database- and vector-store-specific MCP servers are less standardized, and several of the underlying technologies (ChromaDB vs. LanceDB, SQLite vs. PostgreSQL) are explicitly undecided per `docs/architecture/00-repository-architecture.md`.

## Decision

Sprint 0 documents the full MCP integration design (`docs/architecture/01-claude-code-workspace.md`) but does not configure any project-specific MCP servers in `.claude/settings.json` yet, beyond what the Claude Code environment already provides by default. Each MCP integration is wired up in the sprint that first needs it, and only after the underlying technology choice it depends on (vector store, database) has actually been made.

## Rationale

1. **Configuring an MCP server for a database that doesn't exist yet, or that might not be the final choice, creates dead configuration** that either errors or silently does nothing — the same failure mode ADR-0003 identifies for premature hooks.
2. **Security posture scales with what's actually connected.** An MCP server with filesystem or database access is a real expansion of what a Claude Code session can read and modify. Wiring these up only when there is a concrete task that needs them keeps the blast radius of any single session bounded to what that sprint's work actually requires, which is directly relevant to the platform's own privacy-preserving design philosophy.
3. **Sequencing MCP adoption to the technology decisions it depends on is itself good architecture practice**, and is documented as such here so the reasoning is visible rather than assumed.

## Consequences

- The full MCP recommendation table lives in the workspace design doc as guidance for future sprints, not as active configuration.
- Each future sprint that introduces a new storage technology (vector store in Sprint 1, relational database in Sprint 2) must revisit this ADR and either configure the corresponding MCP server or explicitly note why it is deferred further.

## Alternatives considered

- **Configure all recommended MCP servers now against placeholder/local defaults:** rejected for the dead-configuration and unnecessary-attack-surface reasons above.
- **Skip MCP design entirely until needed:** rejected — the brief explicitly asks for this analysis now, and doing the security/workflow thinking up front (even if activation is deferred) is itself valuable planning output, consistent with the project's plan-before-code operating style.
