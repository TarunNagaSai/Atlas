# Book overviews

One plain-text file per book describing the book *itself* — what it is, what it
contains, who filed/authored it, key dates. These answer meta-questions ("what is
this book?", "who is it by?", "what data does it hold?") that no single content
page covers.

Each file is ingested into the same pgvector store as a chunk tagged
`metadata.kind = "overview"`, under the **same `book_id`** as the book's content
(the id is derived from `title`, so the title here must match the book exactly).

## Files

| File | Book title (must match exactly) |
|------|---------------------------------|
| `jio-ipo.txt`            | `JIO IPO`           |
| `annualreport-2025.txt`  | `annualreport-2025` |

## Ingest

```bash
uv run python -c "
from app.rag.pipeline import IngestionPipeline
r = IngestionPipeline().ingest(
    source='data/overviews/jio-ipo.txt', title='JIO IPO', kind='overview', persist=True)
print(r.persisted, r.n_chunks, r.note)
"
```
