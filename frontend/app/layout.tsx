import "./globals.css";
import { ReactQueryProvider } from "@/components/providers/ReactQueryProvider";
import { Toaster } from "sonner";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-bg-primary text-text-primary">
        <ReactQueryProvider>
          {children}
          <Toaster richColors />
        </ReactQueryProvider>
      </body>
    </html>
  );
}

