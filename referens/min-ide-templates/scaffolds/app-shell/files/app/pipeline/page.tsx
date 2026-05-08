import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const stages = [
  { name: "Intake", count: 24, status: "ok" },
  { name: "Kvalificering", count: 18, status: "ok" },
  { name: "Genomförande", count: 41, status: "warning" },
  { name: "QA", count: 12, status: "ok" },
  { name: "Klart", count: 33, status: "ok" },
];

export default function PipelinePage() {
  return (
    <div className="space-y-8 p-8">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight">Pipeline</h1>
        <p className="text-muted-foreground">Visualisera hur arbetet flyter mellan varje steg.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {stages.map((stage) => (
          <Card key={stage.name} className="bg-card border-border">
            <CardHeader>
              <CardTitle className="text-base">{stage.name}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <p className="text-3xl font-semibold tabular-nums">{stage.count}</p>
              <Badge
                variant="outline"
                className={stage.status === "warning" ? "border-amber-500/30 text-amber-400" : "border-emerald-500/30 text-emerald-400"}
              >
                {stage.status === "warning" ? "Behöver uppföljning" : "Stabil"}
              </Badge>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
