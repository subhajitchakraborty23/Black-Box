import { motion } from "framer-motion";
import { Video, Play } from "lucide-react";

const recordings = [
  { id: "REC-401", title: "User Session #8842", duration: "4:32", date: "Today" },
  { id: "REC-400", title: "Checkout Flow Debug", duration: "12:05", date: "Yesterday" },
  { id: "REC-399", title: "Onboarding Replay", duration: "2:18", date: "Mar 13" },
  { id: "REC-398", title: "Error Reproduction #77", duration: "6:45", date: "Mar 12" },
];

export default function Recordings() {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
      <div className="flex items-center gap-3 mb-6">
        <div className="inline-flex items-center justify-center h-10 w-10 rounded-lg bg-nav-recordings/10 text-nav-recordings">
          <Video className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">Recordings</h2>
          <p className="text-sm text-muted-foreground">Session replays and diagnostics</p>
        </div>
      </div>

      <div className="space-y-3">
        {recordings.map((r, i) => (
          <motion.div
            key={r.id}
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.3, delay: i * 0.07 }}
            className="flex items-center gap-4 rounded-xl border border-border bg-card p-4 hover:shadow-md transition-shadow cursor-pointer group"
          >
            <div className="flex items-center justify-center h-10 w-10 rounded-lg bg-nav-recordings/10 text-nav-recordings group-hover:bg-nav-recordings group-hover:text-primary-foreground transition-colors">
              <Play className="h-4 w-4" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-card-foreground truncate">{r.title}</p>
              <p className="text-xs text-muted-foreground font-mono">{r.id}</p>
            </div>
            <span className="text-xs text-muted-foreground hidden sm:block">{r.duration}</span>
            <span className="text-xs text-muted-foreground">{r.date}</span>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
