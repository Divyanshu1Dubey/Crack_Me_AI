// /admin/ingestion/* layout — server-side admin role gate.
//
// UPSC CMS's existing /admin/* routes continue to work unchanged; this
// layout is OPT-IN for the new isolated NEET PG / INI-CET / FMGE /
// USMLE / PLAB ingestion admin only.

import { redirect } from "next/navigation";
import { createSupabaseServerClient } from "@/lib/supabase-server";

export const dynamic = "force-dynamic";

export default async function IngestionLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  let isAdmin = false;
  try {
    const supabase = createSupabaseServerClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (user) {
      const role = (user.app_metadata as any)?.role
        || (user.user_metadata as any)?.role;
      isAdmin = role === "admin" || role === "superuser";
    }
  } catch {
    // Supabase not configured in this env — fall through; the API
    // endpoints (IsIngestionAdmin) still gate access.
  }

  if (!isAdmin) {
    redirect("/login?next=/admin/ingestion");
  }

  return <div className="ingestion-admin">{children}</div>;
}
