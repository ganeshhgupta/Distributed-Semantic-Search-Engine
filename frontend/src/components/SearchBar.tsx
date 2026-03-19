import { FormEvent, useEffect, useRef, useState } from "react";

interface SearchBarProps {
  initialQuery?: string;
  onSearch: (query: string) => void;
  loading?: boolean;
  compact?: boolean;
}

export default function SearchBar({
  initialQuery = "",
  onSearch,
  loading = false,
  compact = false,
}: SearchBarProps) {
  const [value, setValue] = useState(initialQuery);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setValue(initialQuery);
  }, [initialQuery]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (value.trim() && !loading) {
      onSearch(value.trim());
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Search across the corpus…"
          disabled={loading}
          className={`
            w-full rounded-full border border-slate-200 bg-white shadow-md
            px-6 py-3 text-base text-slate-900 placeholder-slate-400
            transition-all duration-200 outline-none
            focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:border-indigo-300
            disabled:opacity-60 disabled:cursor-not-allowed
            ${compact ? "pr-12" : "pr-28"}
          `}
        />
        {compact ? (
          <button
            type="submit"
            disabled={loading || !value.trim()}
            aria-label="Search"
            className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center justify-center
              w-8 h-8 rounded-full bg-indigo-500 text-white hover:bg-indigo-600
              disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? (
              <Spinner size={14} />
            ) : (
              <svg width="14" height="14" viewBox="0 0 20 20" fill="none">
                <circle cx="9" cy="9" r="6" stroke="currentColor" strokeWidth="2" />
                <path d="M13.5 13.5L17 17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            )}
          </button>
        ) : (
          <button
            type="submit"
            disabled={loading || !value.trim()}
            className="absolute right-2 top-1/2 -translate-y-1/2
              bg-indigo-500 text-white rounded-full px-5 py-1.5 text-sm font-medium
              hover:bg-indigo-600 disabled:opacity-40 disabled:cursor-not-allowed
              transition-colors"
          >
            {loading ? "Searching…" : "Search"}
          </button>
        )}
      </div>
    </form>
  );
}

function Spinner({ size = 16 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className="animate-spin"
    >
      <circle
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="3"
        strokeDasharray="31.4"
        strokeDashoffset="10"
        strokeLinecap="round"
      />
    </svg>
  );
}
