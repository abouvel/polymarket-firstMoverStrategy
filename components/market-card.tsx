import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { TrendingUp, Clock, DollarSign } from "lucide-react"

interface MarketCardProps {
  market: {
    id: string
    title: string
    category: string
    yesPrice: number
    noPrice: number
    arbitrageProfit: number
    volume: number
    endDate: string
    description: string
  }
}

export function MarketCard({ market }: MarketCardProps) {
  return (
    <Card className="hover:shadow-lg transition-shadow border-l-4 border-l-green-500">
      <CardHeader className="pb-3">
        <div className="flex justify-between items-start gap-4">
          <div className="space-y-2 flex-1">
            <div className="flex items-center gap-2">
              <Badge variant="secondary">{market.category}</Badge>
              <Badge variant="outline" className="text-green-600 border-green-600">
                <TrendingUp className="h-3 w-3 mr-1" />
                {market.arbitrageProfit}% profit
              </Badge>
            </div>
            <h3 className="font-semibold text-lg leading-tight">{market.title}</h3>
            <p className="text-sm text-gray-600 line-clamp-2">{market.description}</p>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Price Information */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <div className="text-xs text-gray-500 uppercase tracking-wide">Yes Price</div>
            <div className="text-lg font-semibold">${market.yesPrice}</div>
          </div>
          <div className="space-y-1">
            <div className="text-xs text-gray-500 uppercase tracking-wide">No Price</div>
            <div className="text-lg font-semibold">${market.noPrice}</div>
          </div>
        </div>

        {/* Market Stats */}
        <div className="flex justify-between items-center text-sm text-gray-600">
          <div className="flex items-center gap-1">
            <DollarSign className="h-4 w-4" />
            <span>${market.volume.toLocaleString()} volume</span>
          </div>
          <div className="flex items-center gap-1">
            <Clock className="h-4 w-4" />
            <span>Ends {market.endDate}</span>
          </div>
        </div>

        {/* Action Button */}
        <Button className="w-full" variant="outline">
          View Arbitrage Details
        </Button>
      </CardContent>
    </Card>
  )
}
