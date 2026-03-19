import { motion } from "framer-motion";
import { useEffect } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import ResultCard from "../components/ResultCard";
import SearchBar from "../components/SearchBar";
import SkeletonCard from "../components/SkeletonCard";
import { useSearch } from "../hooks/useSearch";

function LatencyPill({ ms }: { ms: number }) {
  const color =
    ms < 100
      ? "bg-emerald-50 text-emerald-600"
      : ms < 200
        ? "bg-amber-50 text-amber-600"
        : "bg-red-50 text-red-600";

  return (
    <span className={`font-mono text-xs rounded-full px-3 py-1 ${color}`}>
      {ms.toFixed(1)}ms
    </span>
  );
}

export default function Search() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryParam = searchParams.get("q") ?? "";

  const { results, loading, error, search } = useSearch();

  useEffect(() => {
    if (queryParam) {
      search(queryParam);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryParam]);

  const handleSearch = (query: string) => {
    navigate(`/search?q=${encodeURIComponent(query)}`);
  };

  return (
    <motion.div
      className="min-h-screen bg-slate-50"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.3 }}
    >
      {/* Sticky header */}
      <header className="sticky top-0 z-20 h-16 bg-white/80 backdrop-blur border-b border-slate-100
        flex items-center px-6 gap-6">
        <Link
          to="/"
          className="font-sans font-bold text-lg text-slate-900 tracking-tight shrink-0
            hover:text-indigo-600 transition-colors"
        >
          SearchOS
        </Link>

        <div className="w-80 ml-auto flex items-center gap-3">
          <SearchBar
            initialQuery={queryParam}
            onSearch={handleSearch}
            loading={loading}
            compact
          />
          {results && !loading && (
            <LatencyPill ms={results.total_latency_ms} />
          )}
        </div>

        <Link to="/corpus" className="text-slate-500 hover:text-slate-800 text-sm transition-colors shrink-0">Corpus</Link>
        <Link to="/system" className="text-slate-500 hover:text-slate-800 text-sm transition-colors shrink-0">System</Link>
      </header>

      {/* Results */}
      <main className="max-w-2xl mx-auto mt-8 px-4 pb-16">
        {/* Degraded mode warning */}
        {results?.degraded && (
          <div className="mb-4 flex items-center gap-2 bg-amber-50 border border-amber-200
            rounded-[12px] px-4 py-3 text-sm text-amber-700">
            <span>⚠</span>
            <span>Running in degraded mode — some workers are offline. Results may be incomplete.</span>
          </div>
        )}

        {/* Meta row */}
        {results && !loading && (
          <div className="flex items-center justify-between mb-4 text-xs text-slate-400 font-mono">
            <span>{results.results.length} results for &ldquo;{results.query}&rdquo;</span>
            <span className="flex gap-3">
              <span>fan-out {results.fanout_ms.toFixed(1)}ms</span>
              <span>merge {results.merge_ms.toFixed(1)}ms</span>
              <span>workers {results.workers_queried.join(", ")}</span>
            </span>
          </div>
        )}

        {/* Error state */}
        {error && !loading && (
          <div className="bg-red-50 border border-red-200 rounded-[12px] p-5 text-red-700 text-sm">
            <strong>Error:</strong> {error}
          </div>
        )}

        {/* Skeleton loading */}
        {loading && (
          <div className="space-y-4">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        )}

        {/* Results list */}
        {!loading && results && (
          <motion.div
            className="space-y-4"
            initial="hidden"
            animate="visible"
            variants={{
              hidden: {},
              visible: { transition: { staggerChildren: 0.04 } },
            }}
          >
            {results.results.length === 0 ? (
              <p className="text-slate-400 text-center py-12">No results found.</p>
            ) : (
              results.results.map((result) => (
                <motion.div
                  key={result.doc_id}
                  variants={{
                    hidden: { opacity: 0, y: 10 },
                    visible: { opacity: 1, y: 0 },
                  }}
                  transition={{ duration: 0.2 }}
                >
                  <ResultCard result={result} query={results.query} />
                </motion.div>
              ))
            )}
          </motion.div>
        )}

        {/* Empty state before search */}
        {!loading && !results && !error && (
          <p className="text-slate-400 text-center py-20 text-sm">
            Enter a query above to search the corpus.
          </p>
        )}
      </main>
    </motion.div>
  );
}
