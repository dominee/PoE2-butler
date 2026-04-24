import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/features/app/AppShell";
import { LandingPage } from "@/features/landing/LandingPage";
import { PublicItemPage } from "@/features/items/PublicItemPage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/app" element={<AppShell />} />
      <Route path="/i/:shareId" element={<PublicItemPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
