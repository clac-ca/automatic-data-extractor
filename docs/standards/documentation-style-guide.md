# Documentation Style Guide

## Goal

Keep docs clear for new users and consistent across pages.

## Audience Rule

Write so a technically capable reader can follow steps without prior ADE context.

## Writing Rules

- define terms before using abbreviations
- use short sentences and direct instructions
- avoid unexplained acronyms and internal shorthand
- avoid guessing user environment details

## Required Page Structure

For tutorials/how-to pages:

1. Goal
2. Before You Start
3. Steps
4. Verify
5. If Something Fails

For reference pages:

1. Purpose
2. Definitions (if needed)
3. Facts/tables
4. Examples

## Command Rules

- use fenced `bash` blocks
- include directory context (`cd backend`) when required
- label destructive commands clearly

## Accuracy Rules

- confirm command behavior with `--help`
- confirm defaults from current code/compose files
- update docs in the same PR as behavior changes
