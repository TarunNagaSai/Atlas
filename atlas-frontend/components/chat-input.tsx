"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import {
  ArrowUp,
  Check,
  ChevronDown,
  FileSpreadsheet,
  FileText,
  ImageIcon,
  Paperclip,
  Sparkles,
  Square,
  X,
} from "lucide-react";
import { TokenUsage } from "@/components/token-usage";
import {
  ACCEPT_ATTR,
  type AttachmentKind,
  classifyFile,
  formatBytes,
  MAX_ATTACHMENTS,
  validateFile,
} from "@/lib/attachments";
import { getDraft, setDraft } from "@/lib/session";
import { DEFAULT_MODEL, MODELS, type ModelId } from "@/lib/settings";
import { uid } from "@/lib/utils";

/** A file staged in the composer, with derived display metadata. */
interface StagedFile {
  id: string;
  file: File;
  kind: AttachmentKind;
  /** Object URL for image preview thumbnails; revoked on removal. */
  previewUrl?: string;
}

interface ChatInputProps {
  onSend: (text: string, model: ModelId, files: File[]) => void;
  /** Cancel the in-flight generation; shown as a Stop button while streaming. */
  onStop?: () => void;
  /** True while a turn is generating — swaps Send for Stop. */
  streaming?: boolean;
  disabled?: boolean;
  tokensUsed: number;
  /**
   * The active conversation id. Unsent composer text is drafted per chat under
   * this key, so switching conversations swaps in that chat's own in-progress
   * text (and a fresh chat starts empty).
   */
  draftKey: string | null;
}

/** Imperative handle so the parent can repopulate the field (e.g. on Stop). */
export interface ChatInputHandle {
  setText: (text: string) => void;
}

export const ChatInput = forwardRef<ChatInputHandle, ChatInputProps>(
  function ChatInput(
    {
      onSend,
      onStop,
      streaming,
      disabled,
      tokensUsed,
      draftKey,
    },
    ref,
  ) {
  const [value, setValue] = useState("");
  const [files, setFiles] = useState<StagedFile[]>([]);
  const [attachError, setAttachError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [selectedModel, setSelectedModel] = useState<ModelId>(DEFAULT_MODEL);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // dragenter/dragleave fire per child element; count depth so the overlay only
  // clears when the cursor actually leaves the composer (not a nested element).
  const dragDepth = useRef(0);
  // Latest draft key, readable inside handlers without re-subscribing them.
  const draftKeyRef = useRef(draftKey);
  draftKeyRef.current = draftKey;

  // Snap the textarea height to its content (capped), used after any
  // programmatic value change (draft restore, imperative setText).
  const resize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, []);

  // Swap in the active chat's saved draft whenever the conversation changes. The
  // previous chat's text is already persisted (saved on every keystroke), so
  // this only needs to load — the field then reflects the chat you switched to.
  useEffect(() => {
    setValue(getDraft(draftKey));
    requestAnimationFrame(resize);
  }, [draftKey, resize]);

  useEffect(() => {
    if (!dropdownOpen) return;
    const handler = (e: MouseEvent) => {
      if (!dropdownRef.current?.contains(e.target as Node)) setDropdownOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [dropdownOpen]);

  // Lets the parent drop text back into the field — e.g. restoring the prompt
  // when a turn is stopped before it produced anything — and resize/focus it.
  useImperativeHandle(ref, () => ({
    setText: (text: string) => {
      setValue(text);
      setDraft(draftKeyRef.current, text);
      textareaRef.current?.focus();
      requestAnimationFrame(resize);
    },
  }));

  // Revoke any outstanding image preview URLs when the composer unmounts.
  useEffect(() => {
    return () => {
      files.forEach((f) => f.previewUrl && URL.revokeObjectURL(f.previewUrl));
    };
    // Run only on unmount — per-file revocation on removal is handled inline.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const addFiles = useCallback((incoming: FileList | File[]) => {
    const picked = Array.from(incoming);
    if (!picked.length) return;

    setFiles((prev) => {
      const next = [...prev];
      let error: string | null = null;
      for (const file of picked) {
        if (next.length >= MAX_ATTACHMENTS) {
          error = `You can attach up to ${MAX_ATTACHMENTS} files per message.`;
          break;
        }
        // Skip exact duplicates (same name + size) silently.
        if (next.some((s) => s.file.name === file.name && s.file.size === file.size)) {
          continue;
        }
        const reason = validateFile(file);
        if (reason) {
          error = reason;
          continue;
        }
        const kind = classifyFile(file)!; // validateFile guarantees a known kind
        next.push({
          id: uid(),
          file,
          kind,
          previewUrl: kind === "image" ? URL.createObjectURL(file) : undefined,
        });
      }
      setAttachError(error);
      return next;
    });
  }, []);

  const removeFile = useCallback((id: string) => {
    setFiles((prev) => {
      const gone = prev.find((f) => f.id === id);
      if (gone?.previewUrl) URL.revokeObjectURL(gone.previewUrl);
      return prev.filter((f) => f.id !== id);
    });
    setAttachError(null);
  }, []);

  // The attachment notice (limit reached / rejected file) is transient — clear
  // it after a few seconds so it doesn't linger over the composer.
  useEffect(() => {
    if (!attachError) return;
    const t = setTimeout(() => setAttachError(null), 3_500);
    return () => clearTimeout(t);
  }, [attachError]);

  // Paperclip / drop entry point. At the cap we don't open the picker — we tell
  // the user why (one notice at a time) instead of silently doing nothing.
  const openPicker = useCallback(() => {
    if (files.length >= MAX_ATTACHMENTS) {
      setAttachError(`You can attach up to ${MAX_ATTACHMENTS} files at a time.`);
      return;
    }
    fileInputRef.current?.click();
  }, [files.length]);

  const onDragEnter = useCallback((e: React.DragEvent) => {
    if (!e.dataTransfer.types.includes("Files")) return;
    e.preventDefault();
    dragDepth.current += 1;
    setIsDragging(true);
  }, []);

  const onDragOver = useCallback((e: React.DragEvent) => {
    if (e.dataTransfer.types.includes("Files")) e.preventDefault();
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    if (!e.dataTransfer.types.includes("Files")) return;
    e.preventDefault();
    dragDepth.current -= 1;
    if (dragDepth.current <= 0) {
      dragDepth.current = 0;
      setIsDragging(false);
    }
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      if (!e.dataTransfer.types.includes("Files")) return;
      e.preventDefault();
      dragDepth.current = 0;
      setIsDragging(false);
      if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
    },
    [addFiles],
  );

  const submit = () => {
    const text = value.trim();
    if ((!text && files.length === 0) || disabled) return;
    onSend(text, selectedModel, files.map((f) => f.file));
    setValue("");
    setDraft(draftKeyRef.current, ""); // the turn is sent — clear its draft
    // The bytes have been handed off; drop the staged chips and free previews.
    files.forEach((f) => f.previewUrl && URL.revokeObjectURL(f.previewUrl));
    setFiles([]);
    setAttachError(null);
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const autoGrow = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value);
    setDraft(draftKeyRef.current, e.target.value); // persist per-chat draft
    const el = e.target;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  };

  const canSend = (!!value.trim() || files.length > 0) && !disabled;

  return (
    <div className="bg-[var(--background)] px-3 pb-[max(1rem,env(safe-area-inset-bottom))] pt-2 sm:px-4">
      <div className="mx-auto max-w-3xl">
        <div
          onDragEnter={onDragEnter}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          className={`relative flex flex-col gap-2 rounded-2xl border bg-[var(--surface)] p-2 shadow-[var(--shadow-md)] transition-colors focus-within:border-[var(--accent)] ${
            isDragging ? "border-[var(--accent)]" : "border-[var(--border)]"
          }`}
        >
          {/* Drop overlay — covers the composer while a file is dragged over it */}
          {isDragging && (
            <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-2xl border-2 border-dashed border-[var(--accent)] bg-[var(--surface)]/90 backdrop-blur-sm">
              <span className="flex items-center gap-2 text-sm font-medium text-[var(--accent)]">
                <Paperclip className="h-4 w-4" />
                Drop files to attach
              </span>
            </div>
          )}

          {/* Staged attachments — chips with a remove (×) button */}
          {files.length > 0 && (
            <div className="flex flex-wrap gap-2 px-1 pt-1">
              {files.map((f) => (
                <AttachmentChip key={f.id} file={f} onRemove={() => removeFile(f.id)} />
              ))}
            </div>
          )}

          {/* A type/size rejection from the picker — clears on the next pick */}
          {attachError && (
            <p className="px-1.5 text-xs text-[var(--danger,#e5484d)]">{attachError}</p>
          )}

          {/* Hidden native picker, driven by the paperclip */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={ACCEPT_ATTR}
            className="hidden"
            onChange={(e) => {
              if (e.target.files) addFiles(e.target.files);
              e.target.value = ""; // allow re-picking the same file
            }}
          />

          {/* Text input on top */}
          <textarea
            ref={textareaRef}
            value={value}
            onChange={autoGrow}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder="Ask about your filings, contracts, or reports…"
            className="max-h-[200px] w-full resize-none bg-transparent px-2 py-1.5 text-base text-[var(--foreground)] outline-none placeholder:text-[var(--subtle)] disabled:cursor-not-allowed sm:text-sm"
          />

          {/* Divider between text and controls (full bleed) */}
          <div className="-mx-2 h-px bg-[var(--border)]" />

          {/* Existing controls moved below */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <button
                type="button"
                aria-label="Attach files"
                title="Attach images, PDF, Word, or Excel"
                onClick={openPicker}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-[var(--subtle)] transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
              >
                <Paperclip className="h-[18px] w-[18px]" />
              </button>

              {/* Per-session token usage */}
              <TokenUsage tokensUsed={tokensUsed} />
            </div>

            <div className="flex items-center gap-2">
              {/* Model selector */}
              <div ref={dropdownRef} className="relative">
                <button
                  type="button"
                  onClick={() => setDropdownOpen((v) => !v)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1.5 text-xs font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--surface-2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
                >
                  <Sparkles className="h-3.5 w-3.5 text-[var(--accent)]" />
                  {MODELS.find((m) => m.id === selectedModel)?.tag}
                  <ChevronDown className={`h-3 w-3 text-[var(--subtle)] transition-transform ${dropdownOpen ? "rotate-180" : ""}`} />
                </button>

                {dropdownOpen && (
                  <div className="absolute bottom-full right-0 z-50 mb-1.5 min-w-[148px] overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--surface)] py-1 shadow-[var(--shadow-md)]">
                    {MODELS.map((m) => (
                      <button
                        key={m.id}
                        type="button"
                        onClick={() => { setSelectedModel(m.id); setDropdownOpen(false); }}
                        className="flex w-full items-center gap-2 px-3 py-2 text-xs transition-colors hover:bg-[var(--surface-2)]"
                      >
                        <Sparkles className="h-3 w-3 shrink-0 text-[var(--accent)]" />
                        <span className="flex-1 text-left text-[var(--foreground)]">{m.tag}</span>
                        {selectedModel === m.id && (
                          <Check className="h-3 w-3 text-[var(--accent)]" />
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {streaming ? (
                <button
                  type="button"
                  onClick={onStop}
                  aria-label="Stop generating"
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--accent)] text-[var(--accent-fg)] shadow-[var(--shadow-sm)] transition-all hover:bg-[var(--accent-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
                >
                  <Square
                    className="h-3.5 w-3.5"
                    fill="currentColor"
                    strokeWidth={0}
                  />
                </button>
              ) : (
                <button
                  type="button"
                  onClick={submit}
                  disabled={!canSend}
                  aria-label="Send message"
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--accent)] text-[var(--accent-fg)] shadow-[var(--shadow-sm)] transition-all hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:bg-[var(--surface-3)] disabled:text-[var(--subtle)] disabled:shadow-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
                >
                  <ArrowUp className="h-[18px] w-[18px]" strokeWidth={2.4} />
                </button>
              )}
            </div>
          </div>
        </div>

        <p className="mt-2 text-center text-xs text-[var(--subtle)]">
          Atlas grounds answers in your sources. Verify figures before relying
          on them.
        </p>
      </div>
    </div>
  );
  },
);

/** Per-kind icon tile shown on the chip when there's no image thumbnail. */
const KIND_ICON: Record<AttachmentKind, { Icon: typeof FileText; className: string }> = {
  image: { Icon: ImageIcon, className: "text-[var(--accent)]" },
  pdf: { Icon: FileText, className: "text-[#e5484d]" },
  word: { Icon: FileText, className: "text-[#4a7cf6]" },
  excel: { Icon: FileSpreadsheet, className: "text-[#16a34a]" },
};

/** A staged-file chip: thumbnail/icon + name + size, with a remove (×) button. */
function AttachmentChip({
  file,
  onRemove,
}: {
  file: StagedFile;
  onRemove: () => void;
}) {
  const { Icon, className } = KIND_ICON[file.kind];
  return (
    <div className="group/chip relative flex max-w-[220px] items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] py-1.5 pl-1.5 pr-2.5">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-[var(--surface-3)]">
        {file.previewUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={file.previewUrl}
            alt={file.file.name}
            className="h-full w-full object-cover"
          />
        ) : (
          <Icon className={`h-4 w-4 ${className}`} />
        )}
      </div>

      <div className="min-w-0">
        <p className="truncate text-xs font-medium text-[var(--foreground)]">
          {file.file.name}
        </p>
        <p className="text-[11px] text-[var(--subtle)]">{formatBytes(file.file.size)}</p>
      </div>

      <button
        type="button"
        onClick={onRemove}
        aria-label={`Remove ${file.file.name}`}
        className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--surface-3)] text-[var(--subtle)] opacity-0 shadow-[var(--shadow-sm)] transition-all hover:bg-[var(--surface)] hover:text-[var(--foreground)] focus-visible:opacity-100 group-hover/chip:opacity-100"
      >
        <X className="h-3 w-3" strokeWidth={2.5} />
      </button>
    </div>
  );
}
