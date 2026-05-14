import { Routes, Route } from "react-router-dom";
import CronOverviewPage from "./CronOverview";

export default function MonitorPage() {
  return (
    <Routes>
      <Route path="/" element={<CronOverviewPage />} />
      <Route path="/cron-overview" element={<CronOverviewPage />} />
    </Routes>
  );
}