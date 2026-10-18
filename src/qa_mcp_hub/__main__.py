"""Module entry point owned by the Milestone 00 CLI.

Purpose: make ``python -m qa_mcp_hub`` behave like the ``qa-mcp`` console script.
Milestone: 00
Status: IMPLEMENTED
Ownership: package.module_entrypoint
Dependencies: Typer CLI package.
Expected tests: module and installed-wheel entry-point smoke tests.
"""

from qa_mcp_hub.cli.main import main

if __name__ == "__main__":
    main()
