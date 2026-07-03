# Atlas prompt eval — `smoke`

**2/2 passed.**

## Per-model

| model | pass | timeouts | loop-forced | ungrounded runs | avg s | avg tok |
|---|---|---|---|---|---|---|
| `gemini-3.1-flash-lite` | 2/2 | 0 | 0 | 0 | 6.7 | 5688 |

## Failures & issues

### `jpm-assets` [gemini-3.1-flash-lite] — JP Morgan Annual Report 2025
- **Q:** How much in total assets does JPMorgan Chase manage according to the 2025 annual report?
- expect=`grounded_numeric` passed=**True** hops=1/12 distinct=1 repeat_skips=0 forced=False timeout=False wall=11.8s tokens=8003
- issue: expected ground-truth figure '4.4' not in answer
- answer: 'According to the 2025 annual report, JPMorgan Chase & Co. reported total assets of $4,424,900 million as of December 31, 2025 [1].'
