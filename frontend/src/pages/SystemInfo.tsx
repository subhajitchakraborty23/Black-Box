import { motion } from "framer-motion";
import { Monitor } from "lucide-react";

const metrics = [
  { label: "CPU Usage", value: "34%", status: "normal" },
  { label: "Memory", value: "6.2 / 16 GB", status: "normal" },
  { label: "Disk I/O", value: "120 MB/s", status: "normal" },
  { label: "Network", value: "84 Mbps", status: "normal" },
  { label: "Uptime", value: "14d 6h 32m", status: "normal" },
  { label: "Active Services", value: "12 / 12", status: "normal" },
];

export default function SystemInfo() {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
      <div className="flex items-center gap-3 mb-6">
        <div className="inline-flex items-center justify-center h-10 w-10 rounded-lg bg-nav-system/10 text-nav-system">
          <Monitor className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">System Information</h2>
          <p className="text-sm text-muted-foreground">Infrastructure health overview</p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {metrics.map((m, i) => (
          <motion.div
            key={m.label}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: i * 0.06 }}
            className="rounded-xl border border-border bg-card p-5"
          >
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{m.label}</p>
            <p className="mt-2 text-2xl font-semibold text-card-foreground">{m.value}</p>
            <div className="mt-3 flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-nav-system" />
              <span className="text-xs text-muted-foreground capitalize">{m.status}</span>
            </div>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
