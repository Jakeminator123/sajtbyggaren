import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const tasks = [
  { title: "Verifiera ny onboarding-flow", owner: "Anna", due: "Idag", priority: "Hög" },
  { title: "Uppdatera webhook-monitorering", owner: "Erik", due: "Imorgon", priority: "Medel" },
  { title: "Stäng äldre backlog-ärenden", owner: "Maria", due: "Fredag", priority: "Låg" },
];

export default function TasksPage() {
  return (
    <div className="space-y-8 p-8">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight">Tasks</h1>
        <p className="text-muted-foreground">Prioriterade aktiviteter för teamet denna vecka.</p>
      </div>
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle>Aktiva uppgifter</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {tasks.map((task) => (
            <div key={task.title} className="rounded-lg border border-border/60 px-4 py-3">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <p className="font-medium">{task.title}</p>
                <Badge variant="outline">{task.priority}</Badge>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">Ansvarig: {task.owner} • Deadline: {task.due}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
