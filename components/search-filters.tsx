import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

export function SearchFilters() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Arbitrage Filters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Profit Threshold */}
          <div className="space-y-3">
            <Label className="text-sm font-medium">Minimum Profit (%)</Label>
            <Slider defaultValue={[1]} max={20} min={0.1} step={0.1} className="w-full" />
            <div className="flex justify-between text-xs text-gray-500">
              <span>0.1%</span>
              <span>20%</span>
            </div>
          </div>

          {/* Market Categories */}
          <div className="space-y-3">
            <Label className="text-sm font-medium">Categories</Label>
            <div className="space-y-2">
              {["Politics", "Sports", "Crypto", "Business", "Entertainment"].map((category) => (
                <div key={category} className="flex items-center space-x-2">
                  <Checkbox id={category.toLowerCase()} />
                  <Label htmlFor={category.toLowerCase()} className="text-sm">
                    {category}
                  </Label>
                </div>
              ))}
            </div>
          </div>

          {/* Time Frame */}
          <div className="space-y-3">
            <Label className="text-sm font-medium">Resolution Time</Label>
            <Select>
              <SelectTrigger>
                <SelectValue placeholder="Select timeframe" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="24h">Next 24 hours</SelectItem>
                <SelectItem value="week">This week</SelectItem>
                <SelectItem value="month">This month</SelectItem>
                <SelectItem value="quarter">This quarter</SelectItem>
                <SelectItem value="year">This year</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
