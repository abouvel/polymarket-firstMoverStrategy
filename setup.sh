#!/bin/bash

# Install backend dependencies
pip install -r requirements.txt

# Install frontend dependencies
npm install
# Install additional frontend dependencies if needed
npm install react-router-dom socket.io-client @types/socket.io-client

# Build the frontend
npm run build 