'use client';

import { useEffect, useState } from 'react';
import { MarketCard } from "@/components/market-card"
import { Card, CardContent } from "@/components/ui/card"
import { useSearchParams } from 'next/navigation';

interface Market {
  id: string;
  title: string;
  category: string;
  yesPrice: number;
  noPrice: number;
  arbitrageProfit: number;
  volume: number;
  endDate: string;
  description: string;
}

export function MarketList() {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [loading, setLoading] = useState(true);
  const searchParams = useSearchParams();
  const query = searchParams.get('q') || '';

  useEffect(() => {
    const fetchMarkets = async () => {
      setLoading(true);
      try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        
        // Transform the data to match our Market interface
        const transformedMarkets = data.map((market: any) => ({
          id: market.id,
          title: market.name,
          category: 'Prediction Market', // Default category
          yesPrice: 0.5, // These would come from the market details
          noPrice: 0.5,  // These would come from the market details
          arbitrageProfit: 0, // Calculate based on prices
          volume: 0, // Would come from market details
          endDate: 'TBD', // Would come from market details
          description: market.name // Use name as description for now
        }));
        
        setMarkets(transformedMarkets);
      } catch (error) {
        console.error('Error fetching markets:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchMarkets();
  }, [query]);

  if (loading) {
    return (
      <Card>
        <CardContent className="py-16 text-center">
          <div className="space-y-4">
            <div className="text-6xl">⏳</div>
            <h3 className="text-xl font-semibold text-gray-900">Loading Markets</h3>
            <p className="text-gray-600 max-w-md mx-auto">
              Fetching market data from Polymarket...
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (markets.length === 0) {
    return (
      <Card>
        <CardContent className="py-16 text-center">
          <div className="space-y-4">
            <div className="text-6xl">🔍</div>
            <h3 className="text-xl font-semibold text-gray-900">No Markets Found</h3>
            <p className="text-gray-600 max-w-md mx-auto">
              Try adjusting your search terms or filters to find markets.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold">Markets</h2>
        <span className="text-sm text-gray-500">{markets.length} markets found</span>
      </div>

      <div className="space-y-4">
        {markets.map((market) => (
          <MarketCard key={market.id} market={market} />
        ))}
      </div>
    </div>
  );
}
