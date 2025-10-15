# Shared module placeholder

This directory will collect standalone UI primitives (buttons, tables, pipes, directives)
that multiple features consume. Keep implementations dumb and stateless; prefer injecting
services from `core/` or feature folders rather than duplicating logic here.
