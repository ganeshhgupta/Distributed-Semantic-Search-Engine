export default function SkeletonCard() {
  return (
    <div className="bg-white rounded-[12px] border border-slate-100 shadow-sm p-5 animate-pulse">
      {/* Doc ID line */}
      <div className="h-3 bg-slate-100 rounded w-32 mb-3" />
      {/* Title */}
      <div className="h-4 bg-slate-100 rounded w-3/4 mb-2" />
      {/* Snippet lines */}
      <div className="space-y-2 mt-3">
        <div className="h-3 bg-slate-100 rounded w-full" />
        <div className="h-3 bg-slate-100 rounded w-5/6" />
        <div className="h-3 bg-slate-100 rounded w-4/6" />
      </div>
      {/* Score bar */}
      <div className="mt-4 h-1 bg-slate-100 rounded-full w-full" />
    </div>
  );
}
