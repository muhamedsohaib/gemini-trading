# Market Data Core Verified Plan Amendments

## Status

Approved on 2026-07-23. These amendments are normative and take precedence over conflicting text in `2026-07-23-market-data-core-verified.md`.

## Amendment 1: Repository policy exception

Preserve the existing public exception name:

```python
RepositoryPolicyViolation
```

Task 1 must not introduce or reference `RepositoryPolicyError`. Generated market-data paths must be rejected by raising `RepositoryPolicyViolation` with a message containing `generated market data must not be tracked`.

## Amendment 2: Exact Binance timestamp conversion

Provider millisecond timestamps must not pass through `float`. Replace any planned conversion equivalent to:

```python
datetime.fromtimestamp(value / 1000, tz=UTC)
```

with exact integer arithmetic:

```python
UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
converted = UNIX_EPOCH + timedelta(milliseconds=value)
```

The normalizer tests must include a millisecond timestamp whose exact value would expose avoidable floating-point conversion risk.
