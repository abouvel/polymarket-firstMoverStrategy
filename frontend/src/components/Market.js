import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import io from 'socket.io-client';
import './Market.css';

const Market = () => {
    const { marketId } = useParams();
    const [marketData, setMarketData] = useState([]);
    const [marketDetails, setMarketDetails] = useState(null);
    const [loading, setLoading] = useState(true);
    const [socketError, setSocketError] = useState(null);

    useEffect(() => {
        // Configure Socket.IO client
        const socket = io('http://localhost:5000', {
            transports: ['polling', 'websocket'],  // Try polling first, then upgrade to websocket
            reconnection: true,
            reconnectionAttempts: 5,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            timeout: 20000,
            autoConnect: true,
            forceNew: true,
            upgrade: true
        });

        // Socket event handlers
        socket.on('connect', () => {
            console.log('Socket connected with transport:', socket.io.engine.transport.name);
            setSocketError(null);
        });

        socket.on('connect_error', (error) => {
            console.error('Socket connection error:', error);
            setSocketError('Failed to connect to server');
        });

        socket.on('disconnect', (reason) => {
            console.log('Socket disconnected:', reason);
            if (reason === 'io server disconnect') {
                // Server initiated disconnect, try to reconnect
                socket.connect();
            }
        });

        socket.on('error', (error) => {
            console.error('Socket error:', error);
            setSocketError('Connection error occurred');
        });

        // Fetch initial market data and details
        fetch(`http://localhost:5000/api/market/${marketId}`)
            .then(response => response.json())
            .then(data => {
                setMarketData(data.updates || []);
                setMarketDetails(data.details);
                setLoading(false);
            })
            .catch(error => {
                console.error('Error fetching market data:', error);
                setLoading(false);
            });

        // Listen for market updates
        socket.on('market_update', (update) => {
            if (update.market_id === marketId) {
                setMarketData(prevData => {
                    const newData = [...prevData, update.data];
                    return newData.slice(-100);
                });
            }
        });

        return () => {
            if (socket.connected) {
                socket.disconnect();
            }
        };
    }, [marketId]);

    const renderUpdate = (update) => {
        switch (update.event_type) {
            case 'book':
                return (
                    <div className="book-update">
                        <h3>Order Book Update</h3>
                        <div className="book-sides">
                            <div className="buys">
                                <h4>Buys</h4>
                                {update.buys?.map((order, index) => (
                                    <div key={index} className="order-item">
                                        <span className="price">{order.price}</span>
                                        <span className="size">{order.size}</span>
                                    </div>
                                ))}
                            </div>
                            <div className="sells">
                                <h4>Sells</h4>
                                {update.sells?.map((order, index) => (
                                    <div key={index} className="order-item">
                                        <span className="price">{order.price}</span>
                                        <span className="size">{order.size}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                );
            case 'price_change':
                return (
                    <div className="price-update">
                        <h3>Price Changes</h3>
                        {update.changes?.map((change, index) => (
                            <div key={index} className="change-item">
                                <span className="side">{change.side}</span>
                                <span className="price">{change.price}</span>
                                <span className="size">{change.size}</span>
                            </div>
                        ))}
                    </div>
                );
            case 'tick_size_change':
                return (
                    <div className="tick-update">
                        <h3>Tick Size Change</h3>
                        <div className="tick-change">
                            <span>Old: {update.old_tick_size}</span>
                            <span>New: {update.new_tick_size}</span>
                        </div>
                    </div>
                );
            default:
                return (
                    <div className="unknown-update">
                        <pre>{JSON.stringify(update, null, 2)}</pre>
                    </div>
                );
        }
    };

    if (loading) {
        return <div className="market-container">Loading market details...</div>;
    }

    if (socketError) {
        return (
            <div className="market-container">
                <div className="error-message">
                    {socketError}
                    <button onClick={() => window.location.reload()}>Retry</button>
                </div>
            </div>
        );
    }

    return (
        <div className="market-container">
            {marketDetails && (
                <div className="market-details">
                    <h2>{marketDetails.question}</h2>
                    <div className="market-info">
                        <div className="info-section">
                            <h3>Market Details</h3>
                            <div className="info-grid">
                                <div className="info-item">
                                    <span className="label">Category:</span>
                                    <span className="value">{marketDetails.category}</span>
                                </div>
                                <div className="info-item">
                                    <span className="label">Status:</span>
                                    <span className="value">
                                        {marketDetails.closed ? 'Closed' : marketDetails.active ? 'Active' : 'Inactive'}
                                    </span>
                                </div>
                                <div className="info-item">
                                    <span className="label">End Date:</span>
                                    <span className="value">{new Date(marketDetails.end_date_iso).toLocaleString()}</span>
                                </div>
                                <div className="info-item">
                                    <span className="label">Minimum Order Size:</span>
                                    <span className="value">{marketDetails.minimum_order_size}</span>
                                </div>
                                <div className="info-item">
                                    <span className="label">Minimum Tick Size:</span>
                                    <span className="value">{marketDetails.minimum_tick_size}</span>
                                </div>
                            </div>
                        </div>
                        <div className="info-section">
                            <h3>Outcomes</h3>
                            <div className="outcomes-list">
                                {marketDetails.tokens.map((token, index) => (
                                    <div key={index} className="outcome-item">
                                        <span className="token-id">Token ID: {token.token_id}</span>
                                        <span className="outcome">{token.outcome}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                        {marketDetails.rewards && (
                            <div className="info-section">
                                <h3>Rewards</h3>
                                <div className="info-grid">
                                    <div className="info-item">
                                        <span className="label">Min Size:</span>
                                        <span className="value">{marketDetails.rewards.min_size}</span>
                                    </div>
                                    <div className="info-item">
                                        <span className="label">Max Spread:</span>
                                        <span className="value">{marketDetails.rewards.max_spread}</span>
                                    </div>
                                    <div className="info-item">
                                        <span className="label">In-Game Multiplier:</span>
                                        <span className="value">{marketDetails.rewards.in_game_multiplier}x</span>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}
            <div className="updates-container">
                {marketData.map((update, index) => (
                    <div key={index} className="update-wrapper">
                        {renderUpdate(update)}
                        <div className="timestamp">
                            {new Date(update.timestamp).toLocaleString()}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default Market; 