export interface SampleChunk {
  loc: string;
  approx_tokens: number;
  preview: string;
}

/** Response shape of POST /documents/upload (mirrors the backend IngestReport). */
export interface UploadResponse {
  source: string;
  n_documents: number;
  n_chunks: number;
  sample_chunks: SampleChunk[];
  embedded_sample: number;
  embed_dim: number | null;
  persisted: boolean;
  note: string;
}
