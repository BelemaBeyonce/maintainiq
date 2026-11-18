import type { Metadata } from "next";
import { WorkspaceProvider } from "@/components/workspace";
import "./globals.css";
export const metadata: Metadata = {
  title: "MaintainIQ — Maintenance foundation",
  description:
    "Tenant-scoped asset registry and maintenance evidence. Milestone 1.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <WorkspaceProvider>{children}</WorkspaceProvider>
      </body>
    </html>
  );
}
