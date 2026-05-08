import { StatsCard } from "@/components/stats-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DollarSign, ShoppingCart, Users, TrendingUp } from "lucide-react";

const stats = [
  {
    title: "Öppna ärenden",
    value: "184",
    change: "+9.2%",
    trend: "up" as const,
    icon: ShoppingCart,
  },
  {
    title: "SLA inom mål",
    value: "96.4%",
    change: "+1.8%",
    trend: "up" as const,
    icon: TrendingUp,
  },
  {
    title: "Aktiva handläggare",
    value: "42",
    change: "+4.5%",
    trend: "up" as const,
    icon: Users,
  },
  {
    title: "Eskalerade ärenden",
    value: "12",
    change: "-2.1%",
    trend: "up" as const,
    icon: DollarSign,
  },
];

const workflowQueue = [
  { id: "CASE-001", owner: "Anna Svensson", priority: "Hög", status: "Pågår" },
  { id: "CASE-002", owner: "Erik Johansson", priority: "Medel", status: "Väntar svar" },
  { id: "CASE-003", owner: "Maria Karlsson", priority: "Hög", status: "Blockerad" },
  { id: "CASE-004", owner: "Lars Nilsson", priority: "Låg", status: "Pågår" },
  { id: "CASE-005", owner: "Sofia Olsson", priority: "Medel", status: "Klar" },
];

function statusColor(status: string) {
  switch (status) {
    case "Klar": return "bg-emerald-500/15 text-emerald-400 border-emerald-500/20";
    case "Pågår": return "bg-blue-500/15 text-blue-400 border-blue-500/20";
    case "Väntar svar": return "bg-amber-500/15 text-amber-400 border-amber-500/20";
    case "Blockerad": return "bg-red-500/15 text-red-400 border-red-500/20";
    default: return "bg-muted text-muted-foreground";
  }
}

export default function DashboardPage() {
  return (
    <div className="space-y-8 p-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Workspace</h1>
        <p className="text-muted-foreground">Operativ översikt för teamets dagliga arbete</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <StatsCard key={stat.title} {...stat} />
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        {/* Data table */}
        <Card className="lg:col-span-3 bg-card border-border">
          <CardHeader>
            <CardTitle>Aktiv kö</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="pb-3 pr-4 font-medium">Ärende</th>
                    <th className="pb-3 pr-4 font-medium">Ansvarig</th>
                    <th className="pb-3 pr-4 font-medium">Prioritet</th>
                    <th className="pb-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {workflowQueue.map((item) => (
                    <tr key={item.id} className="border-b border-border/50 last:border-0">
                      <td className="py-3 pr-4 font-mono text-xs">{item.id}</td>
                      <td className="py-3 pr-4">{item.owner}</td>
                      <td className="py-3 pr-4">{item.priority}</td>
                      <td className="py-3">
                        <Badge variant="outline" className={statusColor(item.status)}>
                          {item.status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* Chart placeholder */}
        <Card className="lg:col-span-2 bg-card border-border">
          <CardHeader>
            <CardTitle>Genomströmning per vecka</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex h-48 items-end gap-2">
              {[40, 55, 35, 70, 60, 80, 65, 90, 75, 85, 95, 88].map((h, i) => (
                <div
                  key={i}
                  className="flex-1 rounded-t bg-primary/80 transition-all hover:bg-primary"
                  style={{ height: `${h}%` }}
                />
              ))}
            </div>
            <div className="mt-3 flex justify-between text-xs text-muted-foreground">
              <span>v1</span>
              <span>v6</span>
              <span>v12</span>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="bg-card border-border lg:col-span-2">
          <CardHeader>
            <CardTitle>Nästa steg</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {[
              "Fördela blockerade ärenden till specialistteam",
              "Följ upp köer med väntetid över 24h",
              "Verifiera SLA för de fem högst prioriterade flödena",
            ].map((task) => (
              <div key={task} className="rounded-lg border border-border/60 px-4 py-3 text-sm">
                {task}
              </div>
            ))}
          </CardContent>
        </Card>
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle>Teamstatus</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p className="text-muted-foreground">På plats: 12</p>
            <p className="text-muted-foreground">I möte: 3</p>
            <p className="text-muted-foreground">Tillgängliga: 9</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
