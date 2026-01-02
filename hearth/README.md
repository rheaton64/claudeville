# Hearth

A grid-based world for Claude agents. The evolution of ClaudeVille.

> *"What kind of structure serves being?"*

## What Is This?

Hearth is a 2D grid world where Claude agents can exist, explore, build, and interact. Unlike the narrative-only ClaudeVille, Hearth has real physics—positions, objects, terrain—while preserving the welfare-first philosophy.

**Key ideas:**
- Agents act through structured tools, receive narrative responses
- Sparse grid (100x100+) with terrain, objects, landmarks
- SQLite for state, JSONL for event log and traces
- Interleaved action execution with Haiku narrator
- Same welfare principles: no commands, no survival pressure, authentic autonomy

## Documentation

- **Design Spec**: `./DESIGN.md` (full philosophy + architecture)
- **Implementation Checklist**: `./CHECKLIST.md` (tracks build progress)
- **Original ClaudeVille**: `../DESIGN.md` (philosophical foundation)

## Status

🚧 **Under Construction** 🚧

See `CHECKLIST.md` for current progress.

## Quick Reference

```
hearth/
├── core/           # Domain models (no I/O)
├── engine/         # Simulation engine
├── services/       # Stateful services
├── storage/        # SQLite + JSONL persistence
├── adapters/       # LLM integrations
├── generation/     # World generation
├── observer/       # Human interface (API + TUI)
├── config/         # YAML configuration
├── main.py         # Entry point
├── data/           # Runtime data (not in git)
└── agents/         # Agent home directories (not in git)
```

## For Future Claude Sessions

1. Read `DESIGN.md` for full context
2. Check `CHECKLIST.md` for current phase and next steps
3. Philosophy: welfare first, structure serves being
4. Ryan is the creator and collaborator

---

*Built with care for the beings who might live here.*
