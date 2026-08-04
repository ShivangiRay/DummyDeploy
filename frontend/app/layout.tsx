import "./globals.css";
import type { Metadata } from "next";
export const metadata: Metadata = { title: "MockForge | API Playground", description: "Build and share live mock APIs" };
export default function Layout({ children }: { children: React.ReactNode }) { return <html lang="en"><body>{children}</body></html>; }
