"""The unified self-improving harness (the runtime general agent).

A single offline model orchestrates Claude-built generic tools: at each
decision boundary it reads a MINIMAL, signature-targeted slice of the LLM-wiki
(not few-shot examples), chooses a tool OR writes code, runs it, reads the
frame feedback, and re-decides on stall — a retry loop that carries a game to
completion. See .wiki/wiki/architecture_self_improving_agent.md.
"""
