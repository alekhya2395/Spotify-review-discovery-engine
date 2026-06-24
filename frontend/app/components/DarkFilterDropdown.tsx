"use client";

import { ChevronDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";

type Props = {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
  format?: (v: string) => string;
};

export function DarkFilterDropdown({
  label,
  value,
  options,
  onChange,
  format = (v) => v,
}: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const display = value ? format(value) : "All";

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 px-3 py-1.5 bg-app-bg border border-app-border rounded text-sm text-app-text hover:border-gray-500 transition-colors"
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        <span className="text-app-muted">{label}</span>
        <span>{display}</span>
        <ChevronDown
          className={`w-4 h-4 text-app-muted ml-1 shrink-0 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <ul
          role="listbox"
          className="absolute right-0 z-50 mt-1 min-w-[200px] max-h-60 overflow-y-auto rounded border border-app-border bg-black shadow-xl py-1"
        >
          <li>
            <button
              type="button"
              role="option"
              aria-selected={!value}
              onClick={() => {
                onChange("");
                setOpen(false);
              }}
              className={`w-full text-left px-3 py-2 text-sm hover:bg-app-panel transition-colors ${
                !value ? "text-app-green" : "text-app-text"
              }`}
            >
              All
            </button>
          </li>
          {options.map((o) => (
            <li key={o}>
              <button
                type="button"
                role="option"
                aria-selected={value === o}
                onClick={() => {
                  onChange(o);
                  setOpen(false);
                }}
                className={`w-full text-left px-3 py-2 text-sm hover:bg-app-panel transition-colors ${
                  value === o ? "text-app-green" : "text-app-text"
                }`}
              >
                {format(o)}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
