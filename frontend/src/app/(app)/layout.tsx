import { AppShell } from "@/components/layout/AppShell";
import "./design-lab.css";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <div className="hey-design-system h-dvh min-h-0"><AppShell>{children}</AppShell></div>;
}
