import { Link } from "react-router-dom";
import { AlertTriangle, Monitor, Headphones, Video, ArrowRight } from "lucide-react";
import { motion } from "framer-motion";

const cards = [
  {
    title: "Crash Data",
    description: "View and analyze application crash reports, stack traces, and error frequencies.",
    icon: AlertTriangle,
    url: "/crash-data",
    color: "bg-nav-crash/10 text-nav-crash",
    border: "hover:border-nav-crash/30",
  },
  {
    title: "System Information",
    description: "Monitor system health, resource usage, and infrastructure status in real time.",
    icon: Monitor,
    url: "/system-info",
    color: "bg-nav-system/10 text-nav-system",
    border: "hover:border-nav-system/30",
  },
  {
    title: "Support",
    description: "Access support tickets, knowledge base, and team communication channels.",
    icon: Headphones,
    url: "/support",
    color: "bg-nav-support/10 text-nav-support",
    border: "hover:border-nav-support/30",
  },
  {
    title: "Recordings",
    description: "Browse session recordings, user replays, and diagnostic video captures.",
    icon: Video,
    url: "/recordings",
    color: "bg-nav-recordings/10 text-nav-recordings",
    border: "hover:border-nav-recordings/30",
  },
];

const Index = () => {
  return (
    <div>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <h2 className="text-2xl font-semibold tracking-tight text-foreground">Welcome back</h2>
        <p className="mt-1 text-muted-foreground">Select a section to get started.</p>
      </motion.div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-8">
        {cards.map((card, i) => (
          <motion.div
            key={card.url}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.1 + i * 0.08 }}
          >
            <Link
              to={card.url}
              className={`group flex flex-col justify-between rounded-xl border border-border bg-card p-6 transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5 ${card.border}`}
            >
              <div>
                <div className={`inline-flex items-center justify-center h-10 w-10 rounded-lg ${card.color}`}>
                  <card.icon className="h-5 w-5" />
                </div>
                <h3 className="mt-4 text-lg font-semibold text-card-foreground">{card.title}</h3>
                <p className="mt-1 text-sm text-muted-foreground leading-relaxed">{card.description}</p>
              </div>
              <div className="mt-5 flex items-center gap-1 text-sm font-medium text-primary opacity-0 group-hover:opacity-100 transition-opacity">
                Open <ArrowRight className="h-3.5 w-3.5" />
              </div>
            </Link>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

export default Index;
