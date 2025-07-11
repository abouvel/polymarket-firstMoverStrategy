import { SearchFilters } from "@/components/search-filters"
import { MarketList } from "@/components/market-list"
import { SearchHeader } from "@/components/search-header"

export default function SearchPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        <SearchHeader />

        <div className="grid lg:grid-cols-4 gap-8 mt-8">
          {/* Filters Sidebar */}
          <div className="lg:col-span-1">
            <SearchFilters />
          </div>

          {/* Results */}
          <div className="lg:col-span-3">
            <MarketList />
          </div>
        </div>
      </div>
    </div>
  )
}
