import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import './Search.css';

const Search = () => {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState([]);
    const [showResults, setShowResults] = useState(false);
    const searchRef = useRef(null);
    const navigate = useNavigate();

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (searchRef.current && !searchRef.current.contains(event.target)) {
                setShowResults(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    useEffect(() => {
        const fetchResults = async () => {
            if (query.length < 2) {
                setResults([]);
                return;
            }

            try {
                const response = await fetch(`http://localhost:5000/api/search?q=${encodeURIComponent(query)}`);
                const data = await response.json();
                setResults(data);
                setShowResults(true);
            } catch (error) {
                console.error('Error fetching search results:', error);
                setResults([]);
            }
        };

        const debounceTimer = setTimeout(fetchResults, 300);
        return () => clearTimeout(debounceTimer);
    }, [query]);

    const handleSelect = (market) => {
        setQuery(market.name);
        setShowResults(false);
        navigate(`/market/${market.id}`);
    };

    return (
        <div className="search-container" ref={searchRef}>
            <input
                type="text"
                className="search-input"
                placeholder="Search markets..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onFocus={() => query.length >= 2 && setShowResults(true)}
            />
            {showResults && results.length > 0 && (
                <div className="search-results">
                    {results.map((result) => (
                        <div
                            key={result.id}
                            className="search-result-item"
                            onClick={() => handleSelect(result)}
                        >
                            <div className="result-name">{result.name}</div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default Search; 