import Header from "@/components/layout/Header";
import QuickStats from "@/components/dashboard/QuickStats";
import TabNavigation from "@/components/dashboard/TabNavigation";

export default function DashboardPage() {
  return (
    <div className="flex flex-col h-screen">
      <Header />
      <QuickStats />
      <div className="flex-1 overflow-hidden">
        <TabNavigation />
      </div>
    </div>
  );
}

