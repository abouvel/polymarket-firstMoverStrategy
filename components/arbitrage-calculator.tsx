import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Calculator } from "lucide-react"

interface ArbitrageCalculatorProps {
  yesPrice: number
  noPrice: number
}

export function ArbitrageCalculator({ yesPrice, noPrice }: ArbitrageCalculatorProps) {
  const totalPrice = yesPrice + noPrice
  const arbitrageExists = totalPrice !== 1.0
  const profitPercentage = arbitrageExists ? ((1 - totalPrice) / totalPrice) * 100 : 0

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Calculator className="h-5 w-5" />
          Arbitrage Calculator
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="investment">Investment Amount ($)</Label>
            <Input id="investment" type="number" placeholder="1000" />
          </div>
          <div className="space-y-2">
            <Label>Expected Profit</Label>
            <div className="h-10 px-3 py-2 border rounded-md bg-gray-50 flex items-center">
              {profitPercentage > 0 ? `${profitPercentage.toFixed(2)}%` : "No arbitrage"}
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <Label>Strategy</Label>
          <div className="p-3 bg-blue-50 rounded-md text-sm">
            {arbitrageExists ? (
              <div>
                <p className="font-medium text-blue-900">Arbitrage Opportunity Detected</p>
                <p className="text-blue-700 mt-1">
                  Buy both YES and NO positions. Total cost: ${totalPrice.toFixed(3)} per $1 payout.
                </p>
              </div>
            ) : (
              <p className="text-gray-600">No arbitrage opportunity available at current prices.</p>
            )}
          </div>
        </div>

        <Button className="w-full" disabled={!arbitrageExists}>
          Execute Arbitrage
        </Button>
      </CardContent>
    </Card>
  )
}
