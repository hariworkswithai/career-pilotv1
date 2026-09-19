"use client";

import { useState } from "react";
import { Sidebar } from "./sidebar";
import { Header } from "./header";
import { MobileNav } from "./mobile-nav";
import { RouteGuard } from "./route-guard";

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-canvas dark:bg-slate-950">
      <RouteGuard>
        <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <div className="lg:pl-72 min-h-screen flex flex-col">
          <Header onMenuClick={() => setSidebarOpen(true)} />
          <main className="flex-1 min-w-0 p-4 pb-24 lg:p-8 lg:pb-8">
            <div className="max-w-6xl mx-auto w-full">{children}</div>
          </main>
        </div>
        <MobileNav />
      </RouteGuard>
    </div>
  );
}