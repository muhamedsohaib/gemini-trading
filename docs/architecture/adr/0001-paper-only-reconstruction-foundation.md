# ADR 0001: Paper-Only Reconstruction Foundation

- Status: Accepted
- Date: 2026-07-21

## Context

The public prototype exposed an administrative database credential, lacked automated validation, mixed research terminology with unvalidated behavior, and contained defects that could produce unsafe decisions.

## Decision

The project is reconstructed as an installable package. The public runtime supports only research and paper modes. The original prototype is quarantined as non-importable historical evidence. Secrets are prohibited, CI is mandatory, and known Version 0 defects are represented by passing regression tests.

## Consequences

- Demo and live execution require a separate approved design and promotion process.
- Existing prototype entry points are no longer supported.
- Pull requests must pass security, typing, test, and build gates.
- Repository history may be rewritten to remove exposed credentials.
