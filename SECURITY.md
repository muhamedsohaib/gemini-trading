# Security Policy

## Supported Code

Only the reconstructed package under `src/gemini_trading/` is supported. `legacy/prototype_v0/` is historical evidence and must not be deployed.

## Reporting

Do not open a public issue containing a credential, exploit details, private logs, or personal data. Contact the repository owner privately and include only the minimum information needed to reproduce the concern.

## Secret Exposure

An exposed credential is rotated before source or Git-history cleanup. The replacement is stored outside Git with least privilege. Public documentation never includes token values or private incident evidence.

## Trading Safety

The public package supports research and paper modes only. Any code path that enables demo or live exchange submission is a security-sensitive change requiring separate design approval, independent risk review, automated validation, and rollback documentation.
