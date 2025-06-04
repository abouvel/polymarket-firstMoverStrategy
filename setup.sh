#!/bin/bash

# Install backend dependencies
pip install flask flask-cors flask-socketio python-socketio

# Install frontend dependencies
cd frontend
npm install react-router-dom socket.io-client
cd .. 