import { motion } from "framer-motion";
import { AlertTriangle } from "lucide-react";

export default function CrashData() {
  const crashes = [
    { id: "CR-1024", message: "NullPointerException in AuthService", time: "2 min ago", severity: "Critical" },
    { id: "CR-1023", message: "TimeoutError in PaymentGateway", time: "14 min ago", severity: "High" },
    { id: "CR-1022", message: "MemoryOverflow in ImageProcessor", time: "1 hr ago", severity: "Medium" },
    { id: "CR-1021", message: "ConnectionReset in DatabasePool", time: "3 hrs ago", severity: "High" },
  ];

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
      <div className="flex items-center gap-3 mb-6">
        <div className="inline-flex items-center justify-center h-10 w-10 rounded-lg bg-nav-crash/10 text-nav-crash">
          <AlertTriangle className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">Crash Data</h2>
          <p className="text-sm text-muted-foreground">Recent application crash reports</p>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="grid grid-cols-[1fr_auto_auto] gap-4 px-5 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider border-b border-border">
          <span>Error</span><span>Severity</span><span>Time</span>
        </div>
        {crashes.map((c) => (
          <div key={c.id} className="grid grid-cols-[1fr_auto_auto] gap-4 px-5 py-4 border-b border-border last:border-0 hover:bg-accent/50 transition-colors">
            <div>
              <span className="text-xs font-mono text-muted-foreground">{c.id}</span>
              <p className="text-sm font-medium text-card-foreground">{c.message}</p>
            </div>
            <span className={`text-xs font-medium px-2 py-1 rounded-full self-center ${
              c.severity === "Critical" ? "bg-nav-crash/10 text-nav-crash" : c.severity === "High" ? "bg-nav-support/10 text-nav-support" : "bg-nav-system/10 text-nav-system"
            }`}>{c.severity}</span>
            <span className="text-xs text-muted-foreground self-center whitespace-nowrap">{c.time}</span>
          </div>
        ))}
      </div>
    </motion.div>
  );
}
