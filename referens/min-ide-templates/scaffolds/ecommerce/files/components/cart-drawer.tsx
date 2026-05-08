"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Minus, Plus, ShoppingBag, Trash2 } from "lucide-react";

const cartItems = [
  { id: "1", name: "[Produktnamn 1]", price: 499, quantity: 1 },
  { id: "2", name: "[Produktnamn 2]", price: 799, quantity: 2 },
];

const itemCount = cartItems.reduce((sum, item) => sum + item.quantity, 0);
const totalPrice = cartItems.reduce((sum, item) => sum + item.price * item.quantity, 0);

export function CartDrawer() {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="relative" aria-label={`Öppna varukorg (${itemCount})`}>
          <ShoppingBag className="h-4 w-4" />
          {itemCount > 0 && (
            <Badge className="absolute -right-2 -top-2 h-5 min-w-5 rounded-full px-1 text-[10px]">{itemCount}</Badge>
          )}
        </Button>
      </SheetTrigger>
      <SheetContent className="flex w-full flex-col sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Din varukorg</SheetTitle>
          <SheetDescription>Exempeldata — ersätt med riktig state eller API-data.</SheetDescription>
        </SheetHeader>
        <div className="mt-6 flex-1 space-y-4 overflow-y-auto">
          {cartItems.map((item) => (
            <div key={item.id} className="rounded-lg border p-3">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <p className="text-sm font-medium">{item.name}</p>
                  <p className="text-xs text-muted-foreground">{item.price} kr/st</p>
                </div>
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
              <div className="mt-3 flex items-center justify-between">
                <div className="inline-flex items-center gap-1 rounded-md border p-1">
                  <Button variant="ghost" size="icon" className="h-7 w-7">
                    <Minus className="h-3.5 w-3.5" />
                  </Button>
                  <span className="w-6 text-center text-sm">{item.quantity}</span>
                  <Button variant="ghost" size="icon" className="h-7 w-7">
                    <Plus className="h-3.5 w-3.5" />
                  </Button>
                </div>
                <p className="text-sm font-semibold">{item.price * item.quantity} kr</p>
              </div>
            </div>
          ))}
        </div>
        <SheetFooter className="mt-4 border-t pt-4">
          <div className="w-full space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Totalt</span>
              <span className="font-semibold">{totalPrice} kr</span>
            </div>
            <Button className="w-full">Till kassan</Button>
          </div>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
