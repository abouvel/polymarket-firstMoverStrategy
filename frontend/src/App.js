import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Search from './components/Search';
import Market from './components/Market';
import './App.css';

function App() {
  return (
    <Router>
      <div className="App">
        <header className="App-header">
          <h1>Polymarket Live Data</h1>
          <Search />
        </header>
        <main>
          <Routes>
            <Route path="/market/:marketId" element={<Market />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
