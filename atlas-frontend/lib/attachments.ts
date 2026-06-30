/**
 * Chat attachments — client-side helpers for the inline base64 flow.
 *
 * Files ride along inside the `POST /chat/stream` JSON body as base64 (no
 * separate upload endpoint); Gemini reads images/PDFs natively while .docx/.xlsx
 * are text-extracted server-side. See docs/frontend-attachments.md in the backend.
 *
 * Everything here mirrors the server's contract: the same size cap, the same
 * supported types, and the same data-URL-prefix stripping — so the UI fails fast
 * with a friendly message instead of round-tripping a doomed request.
 */

/** One attachment as sent to the backend (base64 has the `data:…,` prefix stripped). */
export interface Attachment {
  filename: string;
  mime_type?: string;
  data: string;
}

/** Keep in sync with the server's MAX_ATTACHMENT_MB (default 4). */
export const MAX_ATTACHMENT_MB = 4;
export const MAX_ATTACHMENT_BYTES = MAX_ATTACHMENT_MB * 1024 * 1024;

/** How many files we let a single message carry (matches the doc's ≤ 3 guidance). */
export const MAX_ATTACHMENTS = 3;

/** Coarse category, used to pick the chip icon and (for images) show a thumbnail. */
export type AttachmentKind = "image" | "pdf" | "word" | "excel";

/** Allowed MIME types → kind. HEIC/HEIF often arrive with an empty `type`, so the
 * extension table below is the real fallback. */
const MIME_KINDS: Record<string, AttachmentKind> = {
  "image/png": "image",
  "image/jpeg": "image",
  "image/webp": "image",
  "image/heic": "image",
  "image/heif": "image",
  "application/pdf": "pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "word",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "excel",
};

/** Allowed extensions → kind. */
const EXT_KINDS: Record<string, AttachmentKind> = {
  png: "image",
  jpg: "image",
  jpeg: "image",
  webp: "image",
  heic: "image",
  heif: "image",
  pdf: "pdf",
  docx: "word",
  xlsx: "excel",
};

/** The `accept` attribute for the file `<input>` (matches the supported types). */
export const ACCEPT_ATTR =
  "image/png,image/jpeg,image/webp,image/heic,image/heif,application/pdf,.docx,.xlsx";

function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot === -1 ? "" : name.slice(dot + 1).toLowerCase();
}

/** The kind of a file, or null if it isn't a supported type. */
export function classifyFile(file: File): AttachmentKind | null {
  return MIME_KINDS[file.type] ?? EXT_KINDS[extensionOf(file.name)] ?? null;
}

/**
 * Validate a file before encoding. Returns a human-readable error string, or
 * null if the file is acceptable. Checks type and size — the two things the
 * server rejects with a 400, surfaced here so the user finds out instantly.
 */
export function validateFile(file: File): string | null {
  if (classifyFile(file) === null) {
    // Legacy .xls is the common offender — call it out specifically.
    if (extensionOf(file.name) === "xls") {
      return "Legacy .xls isn't supported — re-save as .xlsx.";
    }
    return "Unsupported file type. Use an image, PDF, .docx, or .xlsx.";
  }
  if (file.size > MAX_ATTACHMENT_BYTES) {
    return `${file.name} is ${formatBytes(file.size)}; max is ${MAX_ATTACHMENT_MB} MB.`;
  }
  if (file.size === 0) {
    return `${file.name} is empty.`;
  }
  return null;
}

/** "1.2 MB", "934 KB" — compact size label for the chip. */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${Math.round(kb)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

/**
 * Read a File into an Attachment. `FileReader.readAsDataURL` yields
 * `data:<mime>;base64,<payload>`; the server wants only the payload, so the
 * `data:…,` prefix is stripped (sending it whole fails as `bad_encoding`).
 */
export function fileToAttachment(file: File): Promise<Attachment> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("Failed to read file"));
    reader.onload = () => {
      const result = reader.result as string; // "data:<mime>;base64,AAAA…"
      const data = result.slice(result.indexOf(",") + 1);
      resolve({ filename: file.name, mime_type: file.type || undefined, data });
    };
    reader.readAsDataURL(file);
  });
}
