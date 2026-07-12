# Persona System

## Purpose

This is how a user (or the invoking Claude Code / Codex CLI session) expresses *what kind of testing they want*, without writing test scripts. It's the input that gives the Reasoning Engine an "expectation" to reason against — without it, there's nothing for Witness to compare observed behavior to.

## Why Personas Instead of Test Scripts

A traditional test script says exactly what to do: "click button A, then button B, then assert C." Witness's premise is that the useful part of testing isn't the literal sequence of clicks — it's the *intent* behind them, and the judgment applied to the outcome. A persona-based approach also matches how real bugs are found in practice: a real "confused new user" persona is far more likely to stumble into an edge case than a rigid, pre-written script ever would, precisely because the model is empowered to explore rather than follow a fixed path.

## Suggested Persona Shape

A persona should be small enough to write in a minute, but structured enough to give the Reasoning Engine something concrete to anchor to. Suggested fields:

```yaml
name: "First-time signup user"
role: >
  A person who has never used this product before, is moderately tech-savvy,
  and is trying to create an account and reach the main dashboard.
goal: >
  Successfully sign up with a new email and password, and land on a page
  that clearly confirms the account was created.
patience: medium   # low | medium | high — influences how many retries/detours before giving up
success_criteria: >
  The user sees an unambiguous confirmation of account creation and can
  navigate to the main app without errors.
known_constraints: >
  Assume no access to a real email inbox — if email verification is
  required, note this as a blocker rather than attempting to bypass it.
```

Not every field needs to be filled in by the user — sensible defaults (e.g., `patience: medium`) should exist so that a minimal persona like just a `goal` string is enough to get started. The richer fields exist for when a user wants more precise control.

## Suggested Built-In Persona Library

To make Witness immediately useful without requiring users to write personas from scratch, shipping a small library of common, reusable personas is worth prioritizing early. Some candidates:

- **First-time user**: no prior knowledge of the product, testing onboarding/signup flows.
- **Returning power user**: knows the product, testing efficiency/shortcuts and whether advanced features still work.
- **Adversarial/edge-case user**: deliberately provides unexpected input (empty fields, very long strings, special characters, rapid double-clicks) — this persona is where Witness's "acts like a real human, including a careless or mischievous one" framing really pays off, since most automated tests never simulate this kind of behavior.
- **Accessibility-conscious user**: navigates primarily via keyboard, checks for reasonable focus order and readable contrast — a good candidate for tighter integration with browser accessibility trees in the WebAdapter.
- **Interrupted user**: starts a flow, abandons it partway (closes a tab, kills a process), and comes back — tests for state recovery and idempotency.

These can live as simple, editable YAML/JSON files in the repo (e.g., `personas/first_time_user.yaml`), which also gives the community an easy, low-risk way to contribute new ones.

## Scoping a Persona to a Project

A persona is generic by design (the same "first-time user" persona is meaningful for a web app, a CLI tool, or a mobile app). The Reasoning Engine is responsible for translating a generic persona's goal into project-specific actions, in combination with the selected Adapter — this keeps personas reusable across wildly different project types, which is important given this project's stated goal of not being tied to any single kind of software.

## Multiple Personas, One Project

A single project will typically warrant testing with several personas (e.g., both "first-time user" and "adversarial user" against the same signup form). The orchestration layer should treat each persona run as an independent session with its own trace and its own section in the final report, rather than trying to interleave multiple personas' goals into a single confusing session.
