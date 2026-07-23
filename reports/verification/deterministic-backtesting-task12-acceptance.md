# Task 12 Deterministic Acceptance Evidence

- Tested branch head: `ae18706d79bb3a02069a138378e1b62d21cfcf67`
- GitHub Actions run: `30021138715`
- Runtime: Python 3.12 on GitHub-hosted Ubuntu 24.04
- Workflow: safe read-only CLI backtest, provider-free replay, independent verification, tamper detection, diagnostic non-promotion, and live-mode rejection.
- Result: passed.

## Focused test output

```text
.....                                                                    [100%]
================================ tests coverage ================================
_______________ coverage: platform linux, python 3.12.13-final-0 _______________

Name                                                      Stmts   Miss  Cover   Missing
---------------------------------------------------------------------------------------
src/gemini_trading/__init__.py                                1      0   100%
src/gemini_trading/cli/__init__.py                            0      0   100%
src/gemini_trading/cli/main.py                               77      9    88%   21, 116, 120, 122-123, 127-132
src/gemini_trading/cli/market_data.py                        80     57    29%   24-27, 31-39, 46-54, 58, 69, 79-106, 110-114, 118-126, 132-139
src/gemini_trading/cli/research.py                          137     23    83%   52, 55, 61, 67, 74, 81, 87, 90-91, 93, 101-102, 109, 165-166, 171, 174, 181, 204-205, 218, 224, 289
src/gemini_trading/data/__init__.py                           0      0   100%
src/gemini_trading/data/datasets/__init__.py                  0      0   100%
src/gemini_trading/data/datasets/canonical_writer.py         40      5    88%   38, 66, 86, 134, 148
src/gemini_trading/data/errors.py                            28      9    68%   20-23, 33-37
src/gemini_trading/data/ingestion/__init__.py                 0      0   100%
src/gemini_trading/data/ingestion/replay.py                 122     89    27%   68, 72, 80-107, 114-149, 156-205, 219-252
src/gemini_trading/data/ingestion/retry.py                   19     10    47%   17-20, 29-34
src/gemini_trading/data/ingestion/service.py                125     84    33%   51, 55, 59-61, 65-67, 97-107, 114-127, 140, 159-300
src/gemini_trading/data/normalization/__init__.py             0      0   100%
src/gemini_trading/data/normalization/binance_klines.py      57     41    28%   19, 23-38, 42-48, 54-64, 74-105
src/gemini_trading/data/providers/__init__.py                 0      0   100%
src/gemini_trading/data/providers/base.py                    16      0   100%
src/gemini_trading/data/providers/binance_spot.py            66     45    32%   28, 32-33, 37-47, 51-55, 62-77, 92-95, 98-103, 111-125
src/gemini_trading/data/providers/http.py                    19     11    42%   12-14, 21-36
src/gemini_trading/data/storage/__init__.py                   0      0   100%
src/gemini_trading/data/storage/base.py                       5      0   100%
src/gemini_trading/data/storage/local_immutable.py          180    112    38%   33-35, 49, 54-55, 59, 63-64, 68, 76, 100, 104, 115-124, 128-131, 135-140, 144-147, 151-157, 161-167, 171-186, 190-195, 228, 235-237, 240-246, 249-252, 255-256, 259-289, 311-316, 326-331
src/gemini_trading/data/validation/__init__.py                0      0   100%
src/gemini_trading/data/validation/candles.py                50     13    74%   27, 30, 32, 34, 43, 55, 62, 64, 68, 72, 77, 83, 90
src/gemini_trading/data/verification/__init__.py              0      0   100%
src/gemini_trading/data/verification/service.py             149    109    27%   57-66, 70-73, 77-80, 84-87, 91-97, 101-107, 111-114, 118-126, 130-159, 163-184, 188-203, 226-295
src/gemini_trading/domain/__init__.py                         0      0   100%
src/gemini_trading/domain/account.py                         90     17    81%   9, 15, 20, 23, 57, 60, 62, 65, 67-70, 72, 74, 81, 102, 105
src/gemini_trading/domain/candle.py                          35      5    86%   33, 35, 37, 47, 51
src/gemini_trading/domain/dataset.py                        117     30    74%   17, 22, 29, 59-66, 95-104, 131, 133, 150-156
src/gemini_trading/domain/experiment.py                      62      7    89%   17, 23, 79, 81, 83, 85, 93
src/gemini_trading/domain/fill.py                            45      5    89%   13, 19, 24, 49, 59
src/gemini_trading/domain/instrument.py                      22      2    91%   12, 34
src/gemini_trading/domain/order.py                           87     15    83%   11, 17, 22, 24, 26, 98, 100, 102, 104, 106, 110, 112, 116, 120, 122
src/gemini_trading/domain/time.py                             4      1    75%   10
src/gemini_trading/domain/timeframe.py                       14      0   100%
src/gemini_trading/execution/__init__.py                      0      0   100%
src/gemini_trading/execution/simulator/__init__.py            0      0   100%
src/gemini_trading/execution/simulator/costs.py              32      3    91%   13, 18, 55
src/gemini_trading/execution/simulator/fills.py              93     30    68%   29, 33-39, 100, 102, 104, 106, 109-115, 122, 134-144, 148, 151, 154-157
src/gemini_trading/execution/simulator/liquidity.py          11      2    82%   8, 22
src/gemini_trading/execution/simulator/precision.py          19      2    89%   10, 31
src/gemini_trading/research/__init__.py                       0      0   100%
src/gemini_trading/research/accounting.py                    96     24    75%   17, 28, 30, 32, 34, 36, 52, 61, 70-74, 80, 117, 136, 140, 144, 154, 156, 158, 161, 163, 165, 168, 170
src/gemini_trading/research/artifacts.py                    123     23    81%   169, 185, 187, 189, 192, 196, 201-205, 217, 219, 221, 226, 228, 299, 311-312, 331-334
src/gemini_trading/research/config.py                        51      6    88%   15, 20, 59, 61, 65, 84
src/gemini_trading/research/contracts.py                     35      6    83%   25, 27, 41, 43, 46-47
src/gemini_trading/research/dataset_reader.py               139     38    73%   67, 70, 76, 82, 89, 96, 102, 106-107, 114, 117-118, 120, 127-128, 157-158, 160, 170, 172, 174, 180-181, 202-203, 205, 207, 214, 224, 226, 228, 230, 240-241, 256-259
src/gemini_trading/research/engine.py                       200     42    79%   38, 43, 98, 100, 102, 104, 106, 108, 110, 112, 115, 148, 171, 196-199, 207, 218-226, 233, 238, 240, 242-245, 248-255, 262, 297, 299-300, 302, 304, 306, 308, 310, 312, 361, 365
src/gemini_trading/research/errors.py                        10      0   100%
src/gemini_trading/research/fixture_strategy.py              30      2    93%   22, 24
src/gemini_trading/research/identity.py                      16      0   100%
src/gemini_trading/research/metrics.py                       83      2    98%   62, 75
src/gemini_trading/research/replay.py                       196     61    69%   64-65, 67, 70, 77, 84, 91, 97, 100-101, 103, 112, 115, 119, 122, 159-160, 162, 171, 244-245, 247, 254, 275-276, 283, 286, 289, 292, 296, 299, 302, 305, 309, 312, 322-323, 325, 332-353, 357, 380-381, 384, 387, 390, 394-395, 397, 401, 405-406, 408
src/gemini_trading/research/serialization.py                 24      3    88%   13, 22, 31
src/gemini_trading/research/verification.py                 120     28    77%   35, 41-42, 44, 47, 50, 57, 64, 68, 71, 75, 79, 122-123, 127, 129, 132, 135, 138, 142, 147, 149, 155-156, 158, 169, 173, 181
src/gemini_trading/safety/__init__.py                         0      0   100%
src/gemini_trading/safety/execution_mode.py                  21      0   100%
src/gemini_trading/safety/regression_guards.py               63     63     0%   3-105
src/gemini_trading/safety/repository_policy.py               30     30     0%   3-45
---------------------------------------------------------------------------------------
TOTAL                                                      3039   1064    65%
5 passed in 1.67s
```

## Safety boundary

No credentials, private endpoints, paper broker, demo adapter, live exchange submission, leverage, futures, shorting, or production strategy were exercised or introduced.
