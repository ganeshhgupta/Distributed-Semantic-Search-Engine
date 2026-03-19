import { motion } from "framer-motion";
import { useNavigate, Link } from "react-router-dom";
import { useCorpus, type CorpusDoc } from "../hooks/useCorpus";

const SAMPLE_SEARCHES = [
  { label: "Black holes & event horizons", query: "black holes event horizon singularity" },
  { label: "Roman Empire fall", query: "decline and fall of the Roman Empire causes" },
  { label: "DNA & genetics", query: "DNA replication gene expression genetics" },
  { label: "French Revolution", query: "French Revolution causes Bastille storming" },
  { label: "Quantum mechanics", query: "wave particle duality quantum superposition" },
  { label: "Climate change", query: "climate change global warming effects ecosystems" },
];

const WORKER_COLORS: Record<string, { bg: string; text: string; dot: string; border: string }> = {
  "search-worker-0": { bg: "bg-blue-50", text: "text-blue-600", dot: "bg-blue-500", border: "border-blue-100" },
  "search-worker-1": { bg: "bg-emerald-50", text: "text-emerald-600", dot: "bg-emerald-500", border: "border-emerald-100" },
  "search-worker-2": { bg: "bg-orange-50", text: "text-orange-600", dot: "bg-orange-500", border: "border-orange-100" },
};

const DOMAIN_ICONS: Record<string, string> = {
  "Science & Technology": "⚗️",
  "History & Society": "🏛️",
  "Culture & World": "🌍",
};

function DocCard({ doc, onSearch }: { doc: CorpusDoc; onSearch: (q: string) => void }) {
  const style = WORKER_COLORS[doc.worker_id] ?? { bg: "bg-slate-50", text: "text-slate-600", dot: "bg-slate-400", border: "border-slate-100" };
  const snippet = doc.text.replace(/^[^:]+:\s*/, "").slice(0, 220);

  return (
    <motion.div
      className={`bg-white rounded-[12px] border ${style.border} shadow-sm p-4
        hover:-translate-y-0.5 hover:shadow-md transition-all duration-200 cursor-pointer group`}
      onClick={() => onSearch(doc.title)}
      whileHover={{ scale: 1.005 }}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <h3 className="font-semibold text-slate-900 text-sm leading-snug line-clamp-1 flex-1">
          {doc.title}
        </h3>
        <span className={`shrink-0 inline-flex items-center gap-1 text-xs font-mono rounded-full px-2 py-0.5 ${style.bg} ${style.text}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
          {doc.worker_id.replace("search-", "")}
        </span>
      </div>
      <p className="text-slate-500 text-xs leading-relaxed line-clamp-3">{snippet}…</p>
      <p className="text-xs font-mono text-slate-300 mt-2">{doc.doc_id}</p>
      <div className="mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
        <span className="text-xs text-indigo-500 font-medium">Search this topic →</span>
      </div>
    </motion.div>
  );
}

export default function Corpus() {
  const navigate  = useNavigate();
  const { data, loading, error, refresh } = useCorpus(18);

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
      {/* Header */}
      <header className="sticky top-0 z-20 h-16 bg-white/80 backdrop-blur border-b border-slate-100
        flex items-center px-6 gap-4">
        <Link to="/" className="font-sans font-bold text-lg text-slate-900 tracking-tight hover:text-indigo-600 transition-colors">
          SearchOS
        </Link>
        <span className="text-slate-300">·</span>
        <span className="text-slate-500 text-sm">Corpus Browser</span>
        <nav className="ml-auto flex items-center gap-4 text-sm text-slate-500">
          <Link to="/search" className="hover:text-slate-800 transition-colors">Search</Link>
          <Link to="/system" className="hover:text-slate-800 transition-colors">System</Link>
        </nav>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-10">

        {/* Stats bar */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Corpus Browser</h1>
            <p className="text-slate-500 text-sm mt-1">
              {data ? (
                <span>
                  <span className="font-mono font-semibold text-slate-700">
                    {data.total_docs.toLocaleString()}
                  </span> Wikipedia chunks across{" "}
                  <span className="font-mono font-semibold text-slate-700">
                    {data.healthy_shards}
                  </span> shards — click any card to search
                </span>
              ) : "Loading corpus…"}
            </p>
          </div>
          <button
            onClick={refresh}
            className="text-sm text-slate-500 border border-slate-200 rounded-full px-4 py-1.5
              hover:bg-slate-50 transition-colors font-medium"
          >
            Shuffle sample
          </button>
        </div>

        {/* Shard domain cards */}
        {data && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-10">
            {data.shards.map((shard) => {
              const style = WORKER_COLORS[shard.worker_id] ?? { bg: "bg-slate-50", text: "text-slate-600", dot: "bg-slate-400", border: "border-slate-100" };
              const icon  = DOMAIN_ICONS[shard.domain?.label ?? ""] ?? "📄";
              return (
                <motion.div
                  key={shard.shard_id}
                  className={`rounded-[12px] border ${style.border} ${style.bg} p-5`}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: shard.shard_id * 0.05 }}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-2xl">{icon}</span>
                    <span className={`font-semibold text-sm ${style.text}`}>
                      {shard.domain?.label ?? `Shard ${shard.shard_id}`}
                    </span>
                  </div>
                  <p className="font-mono text-2xl font-bold text-slate-900 mb-1">
                    {(shard.total_docs ?? 0).toLocaleString()}
                  </p>
                  <p className="text-xs text-slate-500">chunks · {shard.worker_id}</p>
                  {shard.domain?.categories && (
                    <div className="flex flex-wrap gap-1 mt-3">
                      {shard.domain.categories.slice(0, 4).map((cat) => (
                        <span key={cat}
                          className="text-xs bg-white/70 rounded-full px-2 py-0.5 text-slate-500 border border-white">
                          {cat.replace(/_/g, " ")}
                        </span>
                      ))}
                    </div>
                  )}
                </motion.div>
              );
            })}
          </div>
        )}

        {/* Sample search chips */}
        <div className="mb-8">
          <p className="text-xs font-mono text-slate-400 uppercase tracking-wide mb-3">
            Try these searches
          </p>
          <div className="flex flex-wrap gap-2">
            {SAMPLE_SEARCHES.map(({ label, query }) => (
              <button
                key={label}
                onClick={() => handleSearch(query)}
                className="text-sm border border-slate-200 bg-white text-slate-700 rounded-full
                  px-4 py-1.5 hover:border-indigo-300 hover:text-indigo-600 hover:bg-indigo-50
                  transition-all duration-150 font-medium shadow-sm"
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Document grid */}
        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm font-medium text-slate-700">Random sample</p>
          <p className="text-xs text-slate-400 font-mono">{data?.documents.length ?? 0} docs shown</p>
        </div>

        {/* Loading */}
        {loading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 9 }).map((_, i) => (
              <div key={i} className="bg-white rounded-[12px] border border-slate-100 p-4 animate-pulse">
                <div className="h-4 bg-slate-100 rounded w-3/4 mb-3" />
                <div className="space-y-2">
                  <div className="h-3 bg-slate-100 rounded w-full" />
                  <div className="h-3 bg-slate-100 rounded w-5/6" />
                  <div className="h-3 bg-slate-100 rounded w-4/6" />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Error */}
        {error && !loading && (
          <div className="bg-red-50 border border-red-200 rounded-[12px] p-5 text-red-700 text-sm">
            <strong>Error loading corpus:</strong> {error}
            <br />
            <span className="text-xs text-red-400 mt-1 block">
              Make sure the coordinator and workers are running.
            </span>
          </div>
        )}

        {/* Doc cards */}
        {!loading && data && (
          <motion.div
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
            initial="hidden"
            animate="visible"
            variants={{ visible: { transition: { staggerChildren: 0.03 } } }}
          >
            {data.documents.map((doc) => (
              <motion.div
                key={doc.doc_id}
                variants={{ hidden: { opacity: 0, y: 10 }, visible: { opacity: 1, y: 0 } }}
                transition={{ duration: 0.2 }}
              >
                <DocCard doc={doc} onSearch={handleSearch} />
              </motion.div>
            ))}
          </motion.div>
        )}
      </main>
    </motion.div>
  );
}
