import { motion } from "framer-motion";
import { Headphones, MessageSquare, BookOpen, Mail } from "lucide-react";

const channels = [
  { icon: MessageSquare, title: "Live Chat", desc: "Chat with support in real time", status: "Online" },
  { icon: Mail, title: "Email Support", desc: "Get a response within 24 hours", status: "Available" },
  { icon: BookOpen, title: "Knowledge Base", desc: "Browse documentation & FAQs", status: "120 articles" },
];

export default function Support() {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
      <div className="flex items-center gap-3 mb-6">
        <div className="inline-flex items-center justify-center h-10 w-10 rounded-lg bg-nav-support/10 text-nav-support">
          <Headphones className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">Support</h2>
          <p className="text-sm text-muted-foreground">Get help from our team</p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {channels.map((ch, i) => (
          <motion.div
            key={ch.title}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: i * 0.08 }}
            className="rounded-xl border border-border bg-card p-6 hover:shadow-md transition-shadow cursor-pointer"
          >
            <ch.icon className="h-6 w-6 text-nav-support" />
            <h3 className="mt-4 text-base font-semibold text-card-foreground">{ch.title}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{ch.desc}</p>
            <span className="mt-3 inline-block text-xs font-medium text-nav-system">{ch.status}</span>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
