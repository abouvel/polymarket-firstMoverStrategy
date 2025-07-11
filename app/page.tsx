import { Search } from "lucide-react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-16">
        <div className="max-w-4xl mx-auto text-center space-y-8">
          {/* Header */}
          <div className="space-y-4">
            <h1 className="text-4xl md:text-6xl font-bold text-gray-900">
              Polymarket
              <span className="text-blue-600"> Arbitrage</span>
            </h1>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              Discover arbitrage opportunities across Polymarket prediction markets in real-time
            </p>
          </div>

          {/* Search Section */}
          <div className="max-w-2xl mx-auto space-y-4">
            <div className="relative">
              <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-400 h-5 w-5" />
              <Input
                placeholder="Search markets, events, or topics..."
                className="pl-12 h-14 text-lg border-2 border-gray-200 focus:border-blue-500 rounded-xl"
              />
            </div>
            <Link href="/search">
              <Button size="lg" className="w-full h-12 text-lg rounded-xl">
                Search Markets
              </Button>
            </Link>
          </div>

          {/* Feature Cards */}
          <div className="grid md:grid-cols-3 gap-6 mt-16">
            <Card className="border-2 hover:border-blue-200 transition-colors">
              <CardHeader>
                <CardTitle className="text-blue-600">Real-time Scanning</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription>
                  Continuously monitor all Polymarket markets for arbitrage opportunities
                </CardDescription>
              </CardContent>
            </Card>

            <Card className="border-2 hover:border-green-200 transition-colors">
              <CardHeader>
                <CardTitle className="text-green-600">Profit Analysis</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription>Calculate potential profits and ROI for each arbitrage opportunity</CardDescription>
              </CardContent>
            </Card>

            <Card className="border-2 hover:border-purple-200 transition-colors">
              <CardHeader>
                <CardTitle className="text-purple-600">Smart Filtering</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription>Filter by market category, profit threshold, and risk level</CardDescription>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}
