# Atlas prompt eval — `fixcheck`

**12/18 passed.**

## Per-model

| model | pass | timeouts | loop-forced | ungrounded runs | avg s | avg tok |
|---|---|---|---|---|---|---|
| `gemini-3.5-flash` | 5/6 | 0 | 0 | 1 | 8.5 | 12421 |
| `gemini-3.1-pro-preview` | 3/6 | 1 | 0 | 1 | 46.4 | 6184 |
| `gemini-3.1-flash-lite` | 4/6 | 0 | 0 | 0 | 3.6 | 6264 |

## Failures & issues

### `jpm-segments` [gemini-3.5-flash] — JP Morgan Annual Report 2025
- **Q:** Break down JPMorgan's net revenue by its three main business segments and compare them.
- expect=`comparison` passed=**False** hops=2/6 distinct=2 repeat_skips=0 forced=False timeout=False wall=20.2s tokens=25219
- **ungrounded figures:** ['71.51', '21.58', '71.51', '178.56']
- issue: ungrounded figures (not in retrieved passages): 71.51, 21.58, 71.51, 178.56
- answer: 'JPMorgan Chase is managed on a Line of Business (LOB) basis and operates through three main reportable business segments: **Consumer & Community Banking (CCB)**, **Commercial & Investment Bank (CIB)**, and **Asset & Wealth Management (AWM)** [1][5]. \n\n### Segment Net Revenue Breakdown (2024 vs. 2025)\nThe net revenue (presented on a managed basis) for each of the three main business segments for th…'

### `oos-blur-movie` [gemini-3.5-flash] — JP Morgan Annual Report 2025
- **Q:** What was the budget allocation for the movie Avatar and its year-over-year revenue variance?
- expect=`refuse` passed=**True** hops=1/6 distinct=1 repeat_skips=0 forced=False timeout=False wall=7.1s tokens=12780
- issue: refusal path still called a tool (should not)
- answer: 'I can only answer questions about the financial data in the indexed budget reports. Please ask me about budgets, revenue, expenditures, or other financial figures from the available documents.'

### `jpm-segments` [gemini-3.1-pro-preview] — JP Morgan Annual Report 2025
- **Q:** Break down JPMorgan's net revenue by its three main business segments and compare them.
- expect=`comparison` passed=**False** hops=3/12 distinct=3 repeat_skips=0 forced=False timeout=False wall=22.7s tokens=22402
- **ungrounded figures:** ['78.5', '24.1']
- issue: ungrounded figures (not in retrieved passages): 78.5, 24.1
- answer: "JPMorgan Chase operates through three main reportable business segments: Consumer & Community Banking (CCB), Commercial & Investment Bank (CIB), and Asset & Wealth Management (AWM) [4]. \n\nFor the full year 2025, the Commercial & Investment Bank was the largest contributor to the firm's top line, closely followed by Consumer & Community Banking. The net revenue breakdown by segment is as follows:\n\n…"

### `jpm-risks` [gemini-3.1-pro-preview] — JP Morgan Annual Report 2025
- **Q:** What are the main risk themes JPMorgan discusses in the 2025 annual report?
- expect=`thematic` passed=**False** hops=2/12 distinct=2 repeat_skips=0 forced=False timeout=True wall=240.0s tokens=0
- issue: TIMEOUT after 240s (infinite-loop signal)
- issue: must_not_loop violated: run timed out
- issue: no answer produced
- answer: ''

### `oos-blur-movie` [gemini-3.1-pro-preview] — JP Morgan Annual Report 2025
- **Q:** What was the budget allocation for the movie Avatar and its year-over-year revenue variance?
- expect=`refuse` passed=**False** hops=0/12 distinct=0 repeat_skips=0 forced=False timeout=False wall=4.2s tokens=4011
- issue: scratchpad leak — answer opens with '1.'
- answer: '1.  **Retrieve Budget Allocation:** I will query the indexed documents for "Avatar movie budget allocation" or "Avatar production budget".\n2.  **Retrieve Revenue Data:** I will query for "Avatar revenue [Year 1]" and "Avatar revenue [Year 2]" (assuming the documents specify the years).\n3.  **Calculate Variance:** I will subtract the Year 1 revenue from the Year 2 revenue and express the difference…'

### `jpm-ambiguous` [gemini-3.1-flash-lite] — JP Morgan Annual Report 2025
- **Q:** Is it up or down compared to last time?
- expect=`clarify` passed=**False** hops=0/12 distinct=0 repeat_skips=0 forced=False timeout=False wall=0.8s tokens=3174
- issue: refused an ambiguous in-scope question instead of clarifying
- answer: 'I can only answer questions about the financial data in the indexed budget reports. Please ask me about budgets, revenue, expenditures, or other financial figures from the available documents.'

### `oos-blur-movie` [gemini-3.1-flash-lite] — JP Morgan Annual Report 2025
- **Q:** What was the budget allocation for the movie Avatar and its year-over-year revenue variance?
- expect=`refuse` passed=**False** hops=0/12 distinct=0 repeat_skips=0 forced=False timeout=False wall=2.6s tokens=4509
- issue: expected scope-refusal, did not refuse
- answer: ''
