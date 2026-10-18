"""Scaffold for outbound URL allowlisting.

Purpose: Reserve scheme, host, port, and redirect checks bound to a connection.
Owning Milestone: 02
Status: SCAFFOLDED
Ownership: security.url_allowlist
Dependencies: Provider connection models, profiles, and normalized URL parsing.
Expected tests: Schemes, host confusion, redirects, private targets, and ports.
"""
