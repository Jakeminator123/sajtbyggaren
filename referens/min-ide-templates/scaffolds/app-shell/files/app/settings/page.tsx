import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function SettingsPage() {
  return (
    <div className="space-y-8 p-8">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight">Inställningar</h1>
        <p className="text-muted-foreground">Konfigurera workspace, notifieringar och teampreferenser.</p>
      </div>
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle>Workspace</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="workspace-name">Workspace-namn</Label>
            <Input id="workspace-name" placeholder="[Workspace]" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="notification-channel">Notifieringskanal</Label>
            <Input id="notification-channel" placeholder="Slack / Teams / Email" />
          </div>
          <Button>Spara</Button>
        </CardContent>
      </Card>
    </div>
  );
}
