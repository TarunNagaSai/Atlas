"use client";

import { track } from "@vercel/analytics";
import { Github, Globe, Linkedin } from "lucide-react";

const STATS = [
  { value: "4+", label: "Experience" },
  { value: "4", label: "AI projects" },
  { value: "4", label: "Apps" },
  { value: "3", label: "Websites" },
];

const LINKS = [
  { href: "https://tarun.avipra.com", label: "Website", icon: "globe" },
  { href: "https://github.com/TarunNagaSai", label: "GitHub", icon: "github" },
  { href: "https://www.linkedin.com/in/tarun-naga-sai/", label: "LinkedIn", icon: "linkedin" },
  { href: "https://medium.com/@tarunnagasai007", label: "Medium", icon: "medium" },
] as const;

function MediumIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path d="M13.54 12a6.8 6.8 0 01-6.77 6.82A6.8 6.8 0 010 12a6.8 6.8 0 016.77-6.82A6.8 6.8 0 0113.54 12zm7.42 0c0 3.54-1.51 6.42-3.38 6.42-1.87 0-3.39-2.88-3.39-6.42s1.52-6.42 3.39-6.42 3.38 2.88 3.38 6.42M24 12c0 3.17-.53 5.75-1.19 5.75-.66 0-1.19-2.58-1.19-5.75s.53-5.75 1.19-5.75C23.47 6.25 24 8.83 24 12z" />
    </svg>
  );
}

const ICON_MAP = {
  globe: Globe,
  github: Github,
  linkedin: Linkedin,
  medium: MediumIcon,
};

export function DeveloperTab() {
  return (
    <div className="space-y-5">
      {/* Identity */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <img
              src="/avatar.jpg"
              alt="Tarun NagaSai"
              className="h-14 w-14 shrink-0 rounded-full object-cover object-top ring-1 ring-[var(--border)] scale-110"
            />
            <div>
              <p className="text-sm font-semibold text-[var(--foreground)]">Tarun NagaSai</p>
              <p className="mt-0.5 text-xs text-[var(--accent)]">AI Product Engineer</p>
              <p className="mt-0.5 text-xs text-[var(--subtle)]">Visakhapatnam, India · Freelance</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => { track("hire_me_clicked"); window.location.href = "mailto:tarunnagasai@icloud.com"; }}
            className="shrink-0 flex h-8 items-center justify-center rounded-lg bg-[var(--accent)] px-3 text-xs font-semibold text-[var(--accent-fg)] shadow-sm transition-colors hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)]"
          >
            Hire Me
          </button>
        </div>
        <p className="mt-3 text-xs leading-relaxed text-[var(--subtle)]">
          I help people build AI systems that hold up in the real world, with guardrails clients can trust.
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-2">
        {STATS.map((s) => (
          <div
            key={s.label}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-2 py-3 text-center"
          >
            <p className="text-base font-semibold text-[var(--foreground)]">{s.value}</p>
            <p className="mt-0.5 text-[10px] leading-tight text-[var(--subtle)]">{s.label}</p>
          </div>
        ))}
      </div>

      {/* What I do */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3">
        <p className="text-sm font-medium text-[var(--foreground)]">
          I bridge the gap between AI and User by architecting complete software lifecycle.
        </p>
        <p className="mt-2 text-xs leading-relaxed text-[var(--subtle)]">
          Building an AI is just one side of the story. For it to reach users, it needs a product around it — the app, the backend, the interface, the database, the security, the production monitoring, and the continuous deployments. I build that whole journey.
        </p>
      </div>

      {/* Links */}
      <div className="flex items-center justify-center gap-3 pb-1">
        {LINKS.map(({ href, label, icon }) => {
          const Icon = ICON_MAP[icon];
          return (
            <a
              key={label}
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={label}
              className="flex h-9 w-9 items-center justify-center rounded-lg text-[var(--subtle)] transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--foreground)]"
            >
              <Icon className="h-5 w-5" />
            </a>
          );
        })}
      </div>
    </div>
  );
}
