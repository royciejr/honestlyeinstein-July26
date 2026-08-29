import type { Metadata, Viewport } from "next";
import { ClerkProvider, SignedIn, UserButton } from "@clerk/nextjs";
import Link from "next/link";
import "./globals.css";
import { RegisterServiceWorker } from "@/components/register-sw";

// Clerk reads its publishable key at request time; prerendering the tree at
// build time would throw before env vars exist (reference-project pattern).
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Honestly Einstein",
  description: "Adaptive maths practice for ages 8–11",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, statusBarStyle: "default", title: "Honestly Einstein" },
  icons: { apple: "/apple-touch-icon.png" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#4f46e5",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body>
          <RegisterServiceWorker />
          <header className="sticky top-0 z-10 border-b border-slate-200 bg-white">
            <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
              <Link href="/" className="text-lg font-bold text-indigo-700">
                Honestly Einstein
              </Link>
              <SignedIn>
                <nav className="flex items-center gap-4 text-sm">
                  <Link href="/" className="hover:text-indigo-700">
                    Map
                  </Link>
                  <Link href="/children" className="hover:text-indigo-700">
                    Children
                  </Link>
                  <Link href="/upload" className="hover:text-indigo-700">
                    Upload
                  </Link>
                  <UserButton afterSignOutUrl="/sign-in" />
                </nav>
              </SignedIn>
            </div>
          </header>
          <main className="mx-auto max-w-3xl px-4 py-6">{children}</main>
        </body>
      </html>
    </ClerkProvider>
  );
}
