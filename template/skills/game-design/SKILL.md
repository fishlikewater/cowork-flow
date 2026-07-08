---
name: game-design
description: Use when working on game development tasks — architecture, engine selection, asset pipelines, performance analysis, or multiplayer networking.
---

# Game Design

Use this skill when the task involves game development: engine selection, game architecture, asset pipeline configuration, performance tuning, or multiplayer networking. It provides domain-specific guidelines that complement the general `cowork-implement` workflow.

## When to use

- Engine architecture decisions (ECS vs OOP, scene organization)
- Asset pipeline setup or optimization
- Performance profiling and optimization
- Multiplayer networking and synchronization
- Any task that references `.cowork-flow/spec/game/` guides

## Domain Guidelines

The following guidelines live in `.cowork-flow/spec/game/` and should be read before implementing game-related code:

| File | Covers |
|------|--------|
| `engine-guidelines.md` | ECS vs OOP, scene/level organization, plugin strategy |
| `asset-pipeline.md` | Asset directory layout, build stages, LOD policy, Git LFS |
| `performance-guidelines.md` | FPS targets, memory budgets, GC, draw calls, profiling workflow |
| `multiplayer-guidelines.md` | Network models, sync strategies, lag compensation, matchmaking |

## Usage

1. Read the relevant spec/game/ guide(s) first.
2. Read the task decision-anchor.md and implement.jsonl context.
3. Proceed with implementation through `cowork-implement` or directly (depending on scope).

## When NOT to use

- Pure backend/CRUD work with no game domain concerns
- Frontend UI that doesn't involve game-specific rendering or input
- General infrastructure tasks
