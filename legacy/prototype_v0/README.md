# Gemini Trading Prototype Version 0

This directory preserves the original prototype logic for historical comparison and regression analysis.

## Restrictions

- It is not an installable package.
- It is excluded from production and paper execution paths.
- It must not contain credentials.
- It must not be imported by `src/gemini_trading`.
- It may contain known logic defects documented by the reconstruction audit.

## Known Defects

- Downtrend text is truncated and can route into uptrend logic.
- Candle completion is not enforced consistently.
- Future-label trailing rows can receive false ranging labels.
- Allocation exploration is random and is not functioning reinforcement learning.
- Position state, duplicate-decision prevention, true risk sizing, and executable exits are absent.
- Chronos and Kronos placeholders are empty.

The reconstructed package must prove improvements through automated regression tests rather than deleting unfavorable history.
