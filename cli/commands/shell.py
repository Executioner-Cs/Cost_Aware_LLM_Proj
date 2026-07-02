"""orchestrator shell — launch immersive TUI."""


def cmd_shell():
    """Launch the immersive orchestrator shell (full-screen TUI)."""
    from cli.tui.app import OrchestratorApp

    app = OrchestratorApp()
    app.run()
