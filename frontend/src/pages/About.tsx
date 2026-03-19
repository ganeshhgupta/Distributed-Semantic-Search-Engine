import { motion } from "framer-motion";
import { Link } from "react-router-dom";

const section = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0 },
};

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-block font-mono text-xs bg-indigo-50 text-indigo-600 border border-indigo-100
      rounded-full px-3 py-0.5">
      {children}
    </span>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-slate-900 font-bold text-xl mb-4 flex items-center gap-2">
      {children}
    </h2>
  );
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-white rounded-[14px] border border-slate-100 shadow-sm p-6 ${className}`}>
      {children}
    </div>
  );
}

const ARCHITECTURE = [
  {
    label: "Coordinator",
    color: "bg-indigo-500",
    text: "text-indigo-600",
    border: "border-indigo-100",
    bg: "bg-indigo-50",
    desc: "Embeds the query using MiniLM-L6-v2, fans out to all healthy workers in parallel, merges results, and tracks metrics.",
  },
  {
    label: "search-worker-0",
    color: "bg-blue-500",
    text: "text-blue-600",
    border: "border-blue-100",
    bg: "bg-blue-50",
    desc: "Shard 0 — Science & Technology. Hosts a FAISS IndexFlatIP over 300 Wikipedia chunks (Physics, Biology, CS, Astronomy…).",
  },
  {
    label: "search-worker-1",
    color: "bg-emerald-500",
    text: "text-emerald-600",
    border: "border-emerald-100",
    bg: "bg-emerald-50",
    desc: "Shard 1 — History & Society. Covers World War II, Ancient Rome, French Revolution, Cold War, Renaissance…",
  },
  {
    label: "search-worker-2",
    color: "bg-orange-500",
    text: "text-orange-600",
    border: "border-orange-100",
    bg: "bg-orange-50",
    desc: "Shard 2 — Culture & World. Covers Geography, Philosophy, Literature, Film, Economics, Mythology…",
  },
];

const DECISIONS = [
  {
    q: "Why FAISS IndexFlatIP, not HNSW?",
    a: "Exact nearest-neighbor search. At 300 docs/shard, brute force is faster than graph traversal and gives provably correct results — no approximation error. At millions of docs, you'd switch to HNSW or IVF.",
  },
  {
    q: "Why consistent hashing if all workers get every query?",
    a: "The ring determines shard ownership during document indexing — each document hashes to exactly one shard, preventing duplication. At query time, all shards are searched in parallel because semantic search has no natural partition key.",
  },
  {
    q: "Why pre-compute embeddings at Docker build time?",
    a: "sentence-transformers consumes ~450 MB RAM. Render free tier allows ~512 MB. Loading the model at runtime would OOM the worker. Baking embeddings into the image means workers only need FAISS + NumPy at runtime (~120 MB).",
  },
  {
    q: "Why three separate worker services instead of one?",
    a: "To demonstrate fault isolation. If worker-1 crashes, the coordinator detects it within 10 seconds and continues serving from the remaining two shards in degraded mode. A monolith would go down entirely.",
  },
  {
    q: "Why Wikipedia as the corpus?",
    a: "Free, rich, diverse, and semantically meaningful. SQuAD/synthetic corpora produce nonsense semantic matches. Wikipedia chunks produce coherent, human-readable results that actually demonstrate what semantic search does better than keyword search.",
  },
];

export default function About() {
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
        <Link to="/" className="font-sans font-bold text-lg text-slate-900 tracking-tight
          hover:text-indigo-600 transition-colors">
          SearchOS
        </Link>
        <span className="text-slate-300 text-sm">·</span>
        <span className="text-slate-500 text-sm">About this project</span>
        <div className="ml-auto flex items-center gap-4">
          <Link to="/search" className="text-slate-500 hover:text-slate-800 text-sm transition-colors">Search</Link>
          <Link to="/corpus" className="text-slate-500 hover:text-slate-800 text-sm transition-colors">Corpus</Link>
          <Link to="/system" className="text-slate-500 hover:text-slate-800 text-sm transition-colors">System</Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-12 space-y-12">

        {/* Hero */}
        <motion.div variants={section} initial="hidden" animate="visible" transition={{ duration: 0.3 }}>
          <div className="flex flex-wrap gap-2 mb-5">
            <Tag>Python · FastAPI</Tag>
            <Tag>FAISS · sentence-transformers</Tag>
            <Tag>Consistent Hashing</Tag>
            <Tag>React · TypeScript</Tag>
            <Tag>Docker · Render</Tag>
          </div>
          <h1 className="text-4xl font-bold text-slate-900 tracking-tight mb-4">
            Distributed Semantic Search Engine
          </h1>
          <p className="text-slate-600 text-lg leading-relaxed">
            A from-scratch distributed retrieval system built to understand the engineering tradeoffs
            that production search infrastructure teams face — sharding strategy, fan-out latency,
            embedding model constraints, and graceful degradation under partial failures.
          </p>
          <p className="text-slate-500 text-sm mt-3 leading-relaxed">
            This is not a competitor to Elasticsearch or Google Search. It is a working system
            that makes the internals of distributed semantic search visible and interactive.
          </p>
        </motion.div>

        {/* What this is NOT */}
        <motion.div variants={section} initial="hidden" animate="visible" transition={{ duration: 0.3, delay: 0.05 }}>
          <Card className="border-l-4 border-l-amber-400">
            <p className="text-slate-700 text-sm leading-relaxed">
              <span className="font-semibold text-slate-900">Honest scope: </span>
              Production search engines (Elasticsearch, Vespa, Meilisearch) have years of engineering
              behind query planning, inverted indexes, and horizontal scaling. This system runs on
              Render's free tier with a 900-document Wikipedia corpus. The goal is to demonstrate
              distributed systems thinking — not to replace existing tools.
            </p>
          </Card>
        </motion.div>

        {/* What it demonstrates */}
        <motion.div variants={section} initial="hidden" animate="visible" transition={{ duration: 0.3, delay: 0.1 }}>
          <SectionTitle>What it demonstrates</SectionTitle>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              {
                icon: "◈",
                title: "Semantic vs keyword retrieval",
                desc: "Queries match by meaning, not exact words. \"climate disasters\" finds documents about floods and droughts that never mention \"climate disasters\" verbatim.",
              },
              {
                icon: "⬡",
                title: "Consistent hashing",
                desc: "MD5-based ring with 150 virtual nodes determines document shard assignment. Minimal remapping when nodes join or leave.",
              },
              {
                icon: "⇶",
                title: "Parallel fan-out",
                desc: "asyncio.gather sends all worker queries simultaneously. Total search latency ≈ max(worker latency), not sum.",
              },
              {
                icon: "⚠",
                title: "Fault tolerance",
                desc: "Health poller detects worker failures every 10s. Coordinator falls back to degraded mode — remaining shards still serve results.",
              },
              {
                icon: "⊞",
                title: "Distributed merging",
                desc: "Each shard returns its top-K results. Coordinator heap-merges across shards to produce a globally ranked top-K.",
              },
              {
                icon: "◎",
                title: "Operational observability",
                desc: "p50/p95/p99 latency histograms, per-worker query counts, QPS, structured JSON logs with trace IDs propagated end-to-end.",
              },
            ].map(({ icon, title, desc }) => (
              <Card key={title}>
                <div className="text-2xl mb-2 text-indigo-400 font-mono">{icon}</div>
                <h3 className="font-semibold text-slate-900 text-sm mb-1">{title}</h3>
                <p className="text-slate-500 text-sm leading-relaxed">{desc}</p>
              </Card>
            ))}
          </div>
        </motion.div>

        {/* Architecture */}
        <motion.div variants={section} initial="hidden" animate="visible" transition={{ duration: 0.3, delay: 0.15 }}>
          <SectionTitle>Architecture</SectionTitle>
          <div className="space-y-3">
            {ARCHITECTURE.map(({ label, color, text, border, bg, desc }) => (
              <Card key={label} className={`flex gap-4 items-start border-l-4 ${border.replace("border", "border-l")}`}>
                <span className={`inline-flex items-center gap-1.5 font-mono text-xs rounded-full px-2.5 py-1 shrink-0 ${bg} ${text}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${color}`} />
                  {label}
                </span>
                <p className="text-slate-600 text-sm leading-relaxed">{desc}</p>
              </Card>
            ))}
          </div>

          {/* Flow diagram */}
          <div className="mt-5 bg-slate-900 rounded-[12px] p-5 font-mono text-sm text-slate-300 leading-loose">
            <div className="text-slate-500 text-xs mb-3"># request flow</div>
            <div>Browser &rarr; <span className="text-indigo-400">coordinator /search</span></div>
            <div className="ml-4">↳ embed query <span className="text-slate-500">(MiniLM-L6-v2, 384-dim)</span></div>
            <div className="ml-4">↳ asyncio.gather(</div>
            <div className="ml-8 text-blue-400">worker-0 /search  <span className="text-slate-500">(FAISS scan, shard 0)</span></div>
            <div className="ml-8 text-emerald-400">worker-1 /search  <span className="text-slate-500">(FAISS scan, shard 1)</span></div>
            <div className="ml-8 text-orange-400">worker-2 /search  <span className="text-slate-500">(FAISS scan, shard 2)</span></div>
            <div className="ml-4">)</div>
            <div className="ml-4">↳ heap-merge top-K across shards</div>
            <div className="ml-4">↳ return <span className="text-indigo-400">SearchResponse</span></div>
          </div>
        </motion.div>

        {/* Engineering decisions */}
        <motion.div variants={section} initial="hidden" animate="visible" transition={{ duration: 0.3, delay: 0.2 }}>
          <SectionTitle>Engineering decisions & tradeoffs</SectionTitle>
          <div className="space-y-4">
            {DECISIONS.map(({ q, a }) => (
              <Card key={q}>
                <p className="font-semibold text-slate-900 text-sm mb-1.5">{q}</p>
                <p className="text-slate-500 text-sm leading-relaxed">{a}</p>
              </Card>
            ))}
          </div>
        </motion.div>

        {/* Try it */}
        <motion.div variants={section} initial="hidden" animate="visible" transition={{ duration: 0.3, delay: 0.25 }}>
          <SectionTitle>Try it live</SectionTitle>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              {
                to: "/search?q=quantum+entanglement+superposition",
                label: "Semantic search",
                desc: "Query the corpus. Watch fan-out latency and per-shard results in the side panel.",
                cta: "Run a search →",
                color: "text-indigo-600",
              },
              {
                to: "/system",
                label: "Fault injection",
                desc: "Click \"Simulate Down\" on a worker. Watch the coordinator switch to degraded mode in real time.",
                cta: "Open System →",
                color: "text-red-500",
              },
              {
                to: "/corpus",
                label: "Corpus browser",
                desc: "Browse the 900-document Wikipedia corpus split across 3 domain shards.",
                cta: "Browse corpus →",
                color: "text-emerald-600",
              },
            ].map(({ to, label, desc, cta, color }) => (
              <Link key={to} to={to}>
                <Card className="h-full hover:-translate-y-0.5 hover:shadow-md transition-all duration-200 cursor-pointer">
                  <p className="font-semibold text-slate-900 text-sm mb-1.5">{label}</p>
                  <p className="text-slate-500 text-sm leading-relaxed mb-3">{desc}</p>
                  <span className={`text-xs font-mono font-medium ${color}`}>{cta}</span>
                </Card>
              </Link>
            ))}
          </div>
        </motion.div>

        {/* Stack */}
        <motion.div variants={section} initial="hidden" animate="visible" transition={{ duration: 0.3, delay: 0.3 }}>
          <SectionTitle>Stack</SectionTitle>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
            {[
              ["Backend", "Python 3.11 · FastAPI · uvicorn"],
              ["ML", "sentence-transformers · all-MiniLM-L6-v2"],
              ["Vector index", "FAISS IndexFlatIP (exact cosine)"],
              ["Hashing", "MD5 ring · 150 virtual nodes · bisect"],
              ["Frontend", "React 18 · TypeScript · Vite"],
              ["UI", "Tailwind CSS v3 · Framer Motion · Recharts"],
              ["Deploy", "Render (backend) · Vercel (frontend)"],
              ["Corpus", "Wikipedia REST API · 900 chunks · 3 shards"],
            ].map(([label, value]) => (
              <div key={label} className="bg-white rounded-[10px] border border-slate-100 p-4">
                <p className="text-xs text-slate-400 mb-1">{label}</p>
                <p className="font-mono text-xs text-slate-700 leading-snug">{value}</p>
              </div>
            ))}
          </div>
        </motion.div>

      </main>
    </motion.div>
  );
}
