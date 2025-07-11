'use client';

import { useEffect, useState } from 'react';
import { ArbitrageCalculator } from "@/components/arbitrage-calculator"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ArrowLeft, ExternalLink } from "lucide-react"
import Link from "next/link"
import { io, Socket } from 'socket.io-client';

interface MarketData {
  id: string;
  title: string;
  category: string;
  yesPrice: number;
  noPrice: number;
  volume: number;
  description: string;
  endDate: string;
  updates: any[];
}

export default function MarketDetailPage({ params }: { params: { id: string } }) {
  const [market, setMarket] = useState<MarketData | null>(null);
  const [loading, setLoading] = useState(true);
  const [socket, setSocket] = useState<Socket | null>(null);

  useEffect(() => {
    const fetchMarketData = async () => {
      try {
        const response = await fetch(`/api/market/${params.id}`);
        const data = await response.json();
        
        // Transform the data to match our MarketData interface
        const transformedData: MarketData = {
          id: params.id,
          title: data.details.title || 'Market Details',
          category: 'Prediction Market',
          yesPrice: 0.5, // These would come from the market details
          noPrice: 0.5,  // These would come from the market details
          volume: 0, // Would come from market details
          description: data.details.description || '',
          endDate: 'TBD',
          updates: data.updates || []
        };
        
        setMarket(transformedData);
      } catch (error) {
        console.error('Error fetching market data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchMarketData();

    // Set up WebSocket connection for real-time updates
    const newSocket = io('http://localhost:5000', {
      transports: ['websocket'],
      reconnection: true,
      reconnectionAttempts: 5,
    });

    newSocket.on('connect', () => {
      console.log('Connected to WebSocket');
    });

    newSocket.on('market_update', (update) => {
      if (update.market_id === params.id) {
        setMarket(prev => {
          if (!prev) return null;
          return {
            ...prev,
            updates: [...prev.updates, update].slice(-100) // Keep last 100 updates
          };
        });
      }
    });

    setSocket(newSocket);

    return () => {
      newSocket.close();
    };
  }, [params.id]);

  if (loading || !market) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="container mx-auto px-4 py-8">
          <div className="max-w-4xl mx-auto">
            <Card>
              <CardContent className="py-16 text-center">
                <div className="space-y-4">
                  <div className="text-6xl">⏳</div>
                  <h3 className="text-xl font-semibold text-gray-900">Loading Market Data</h3>
                  <p className="text-gray-600 max-w-md mx-auto">
                    Fetching market details from Polymarket...
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto space-y-8">
          {/* Header */}
          <div className="flex items-center gap-4">
            <Link href="/search">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back to Search
              </Button>
            </Link>
          </div>

          {/* Market Info */}
          <Card>
            <CardHeader>
              <div className="flex justify-between items-start">
                <div className="space-y-2">
                  <Badge>{market.category}</Badge>
                  <CardTitle className="text-2xl">{market.title}</CardTitle>
                  <p className="text-gray-600">{market.description}</p>
                </div>
                <Button variant="outline" size="sm">
                  <ExternalLink className="h-4 w-4 mr-2" />
                  View on Polymarket
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-3 gap-6">
                <div className="text-center p-4 bg-green-50 rounded-lg">
                  <div className="text-2xl font-bold text-green-600">${market.yesPrice}</div>
                  <div className="text-sm text-gray-600">YES Price</div>
                </div>
                <div className="text-center p-4 bg-red-50 rounded-lg">
                  <div className="text-2xl font-bold text-red-600">${market.noPrice}</div>
                  <div className="text-sm text-gray-600">NO Price</div>
                </div>
                <div className="text-center p-4 bg-blue-50 rounded-lg">
                  <div className="text-2xl font-bold text-blue-600">${market.volume.toLocaleString()}</div>
                  <div className="text-sm text-gray-600">Volume</div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Arbitrage Calculator */}
          <ArbitrageCalculator yesPrice={market.yesPrice} noPrice={market.noPrice} />
        </div>
      </div>
    </div>
  )
}
