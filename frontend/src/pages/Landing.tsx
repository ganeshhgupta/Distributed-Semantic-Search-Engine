import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import SearchBar from "../components/SearchBar";

const SAMPLE_SEARCHES = [
  { label: "Black holes", query: "black holes event horizon singularity" },
  { label: "Roman Empire", query: "decline and fall of the Roman Empire" },
  { label: "DNA & genetics", query: "DNA replication gene expression genetics" },
  { label: "French Revolution", query: "French Revolution causes Bastille" },
  { label: "Quantum mechanics", query: "wave particle duality quantum superposition" },
  { label: "Climate change", query: "climate change global warming ecosystems" },
];

export default function Landing() {
  const navigate = useNavigate();

  const handleSearch = (query: string) => {
    navigate(`/search?q=${encodeURIComponent(query)}`);
  };

  return (
    <motion.div
      className="relative min-h-screen bg-white flex flex-col items-center justify-center overflow-hidden"
      initial={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.3 }}
    >
      {/* Blob */}
      <div className="absolute top-[-10%] right-[-10%] w-[600px] h-[600px]
        bg-indigo-100 rounded-full blur-3xl opacity-40 animate-blob pointer-events-none" />

      <div className="relative z-10 flex flex-col items-center px-4 w-full max-w-3xl">
        {/* Wordmark */}
        <h1 className="font-sans font-bold tracking-tight text-5xl text-slate-900 mb-2">
          SearchOS
        </h1>
        <p className="text-slate-500 text-lg mt-1 mb-10">
          Distributed semantic search. Self-hosted.
        </p>

        {/* Search bar */}
        <div className="w-[600px] max-w-full mb-5">
          <SearchBar onSearch={handleSearch} />
        </div>

        {/* Sample search chips */}
        <div className="flex flex-wrap justify-center gap-2 mb-8 max-w-xl">
          {SAMPLE_SEARCHES.map(({ label, query }) => (
            <button
              key={label}
              onClick={() => handleSearch(query)}
              className="text-sm border border-slate-200 text-slate-600 rounded-full px-4 py-1.5
                hover:border-indigo-300 hover:text-indigo-600 hover:bg-indigo-50
                transition-all duration-150 bg-white shadow-sm"
            >
              {label}
            </button>
          ))}
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-3 mb-16">
          <button
            onClick={() => navigate("/corpus")}
            className="bg-indigo-500 text-white rounded-full px-6 py-2 text-sm font-medium
              hover:bg-indigo-600 transition-colors shadow-sm"
          >
            Browse Corpus
          </button>
          <button
            onClick={() => navigate("/system")}
            className="border border-slate-300 text-slate-700 rounded-full px-6 py-2 text-sm font-medium
              hover:bg-slate-50 transition-colors"
          >
            View System
          </button>
        </div>

        {/* Footer stats */}
        <div className="grid grid-cols-3 gap-8 text-center max-w-xl">
          {[
            { label: "Architecture", value: "3 Shards" },
            { label: "Index", value: "FAISS IP" },
            { label: "Embeddings", value: "MiniLM-L6" },
          ].map(({ label, value }) => (
            <div key={label}>
              <p className="font-mono text-slate-400 text-xs uppercase tracking-wide">{label}</p>
              <p className="font-mono font-medium text-slate-700 mt-1">{value}</p>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}
