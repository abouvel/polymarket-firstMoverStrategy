'use client'

import { useEffect, useState } from 'react'

interface TweetEvent {
  timestamp: string
  type: 'tweet_received'
  data: {
    tweet_id: string
    username: string
    text: string
    url?: string
  }
}

interface TradeEvent {
  timestamp: string
  type: 'trade_executed' | 'trade_skipped'
  data: {
    token_id?: string
    token_name?: string
    market_name: string
    reason?: string
  }
}

type DashboardEvent = TweetEvent | TradeEvent

export default function Dashboard() {
  const [tweets, setTweets] = useState<TweetEvent[]>([])
  const [trades, setTrades] = useState<TradeEvent[]>([])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let eventSource: EventSource | null = null
    
    const connect = () => {
      try {
        eventSource = new EventSource('http://localhost:8000/events')
        
        eventSource.onopen = () => {
          setConnected(true)
          setError(null)
        }
        
        eventSource.onerror = () => {
          setConnected(false)
          setError('Connection lost - retrying...')
        }
        
        eventSource.onmessage = (event) => {
          try {
            const data: DashboardEvent = JSON.parse(event.data)
            
            if (data.type === 'tweet_received') {
              setTweets(prev => [data as TweetEvent, ...prev.slice(0, 19)])
            } else if (data.type === 'trade_executed' || data.type === 'trade_skipped') {
              setTrades(prev => [data as TradeEvent, ...prev.slice(0, 19)])
            }
          } catch (err) {
            console.error('Error parsing event:', err)
          }
        }
        
      } catch (err) {
        setError('Failed to connect to backend')
        setConnected(false)
      }
    }

    // Load recent events first
    fetch('http://localhost:8000/api/recent')
      .then(response => response.json())
      .then((events: DashboardEvent[]) => {
        const tweetEvents = events.filter(e => e.type === 'tweet_received') as TweetEvent[]
        const tradeEvents = events.filter(e => e.type === 'trade_executed' || e.type === 'trade_skipped') as TradeEvent[]
        
        setTweets(tweetEvents.slice(0, 20))
        setTrades(tradeEvents.slice(0, 20))
      })
      .catch(err => console.error('Failed to load recent events:', err))

    // Connect to live stream
    connect()

    return () => {
      if (eventSource) {
        eventSource.close()
      }
    }
  }, [])

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString()
  }

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold text-gray-900">
            🚀 PolyAI Trading Dashboard
          </h1>
          <div className="flex items-center space-x-2">
            <div className={`h-3 w-3 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`}></div>
            <span className={`text-sm font-medium ${connected ? 'text-green-700' : 'text-red-700'}`}>
              {connected ? 'Live' : 'Disconnected'}
            </span>
          </div>
        </div>
        {error && (
          <div className="mt-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-md p-2">
            {error}
          </div>
        )}
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Tweets Column */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900 flex items-center">
              📱 Live Tweets
              <span className="ml-2 text-sm font-normal text-gray-500">
                ({tweets.length})
              </span>
            </h2>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {tweets.length === 0 ? (
              <div className="p-6 text-center text-gray-500">
                No tweets yet...
              </div>
            ) : (
              tweets.map((tweet, index) => (
                <div key={`${tweet.data.tweet_id}-${index}`} className="p-4 border-b border-gray-100 last:border-b-0 hover:bg-gray-50">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-1">
                        <span className="font-medium text-blue-600">
                          @{tweet.data.username}
                        </span>
                        <span className="text-xs text-gray-400">
                          {formatTime(tweet.timestamp)}
                        </span>
                      </div>
                      <p className="text-sm text-gray-800 leading-relaxed">
                        {tweet.data.text}
                      </p>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Trades Column */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900 flex items-center">
              💰 Trading Activity
              <span className="ml-2 text-sm font-normal text-gray-500">
                ({trades.length})
              </span>
            </h2>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {trades.length === 0 ? (
              <div className="p-6 text-center text-gray-500">
                No trades yet...
              </div>
            ) : (
              trades.map((trade, index) => (
                <div key={`${trade.data.market_name}-${index}`} className="p-4 border-b border-gray-100 last:border-b-0 hover:bg-gray-50">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-2">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          trade.type === 'trade_executed' 
                            ? 'bg-green-100 text-green-800' 
                            : 'bg-yellow-100 text-yellow-800'
                        }`}>
                          {trade.type === 'trade_executed' ? '✅ EXECUTED' : '⏭️ SKIPPED'}
                        </span>
                        <span className="text-xs text-gray-400">
                          {formatTime(trade.timestamp)}
                        </span>
                      </div>
                      
                      {trade.type === 'trade_executed' && trade.data.token_name && (
                        <div className="mb-1">
                          <span className="text-sm font-medium text-gray-700">
                            Token: {trade.data.token_name}
                          </span>
                        </div>
                      )}
                      
                      <div className="mb-1">
                        <span className="text-sm text-gray-600">
                          Market: {trade.data.market_name}
                        </span>
                      </div>
                      
                      {trade.data.reason && (
                        <div className="text-xs text-gray-500">
                          Reason: {trade.data.reason}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Stats Footer */}
      <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="text-sm font-medium text-gray-500">Total Tweets</div>
          <div className="text-2xl font-bold text-gray-900">{tweets.length}</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="text-sm font-medium text-gray-500">Trades Executed</div>
          <div className="text-2xl font-bold text-green-600">
            {trades.filter(t => t.type === 'trade_executed').length}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="text-sm font-medium text-gray-500">Trades Skipped</div>
          <div className="text-2xl font-bold text-yellow-600">
            {trades.filter(t => t.type === 'trade_skipped').length}
          </div>
        </div>
      </div>
    </div>
  )
}
