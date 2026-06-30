export class MissingApiKeyError extends Error {
  constructor() {
    super("A Gemini API key is required to chat.");
    this.name = "MissingApiKeyError";
  }
}

export class InvalidApiKeyError extends Error {
  constructor(message = "Your Gemini API key was rejected.") {
    super(message);
    this.name = "InvalidApiKeyError";
  }
}

export function isApiKeyError(err: unknown): boolean {
  return err instanceof MissingApiKeyError || err instanceof InvalidApiKeyError;
}

export class AttachmentError extends Error {
  /** Stable code: too_large | unsupported_type | bad_encoding | empty. */
  readonly code: string;
  constructor(code: string, message: string) {
    super(message);
    this.name = "AttachmentError";
    this.code = code;
  }
}
