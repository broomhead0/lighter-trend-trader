#!/bin/bash
# Quick start script for Lighter Trend Trader

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Lighter Trend Trader...${NC}"

# Check if venv exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate

# Install dependencies if needed
if [ ! -f ".venv/.installed" ]; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -q -r requirements.txt
    touch .venv/.installed
fi

# Check if config exists
if [ ! -f "config.yaml" ]; then
    echo -e "${YELLOW}Creating config.yaml from example...${NC}"
    cp config.yaml.example config.yaml
    echo -e "${YELLOW}⚠️  Please edit config.yaml before running!${NC}"
    exit 1
fi

# Set PYTHONPATH
export PYTHONPATH=.

# Run the bot
echo -e "${GREEN}Starting bot...${NC}"
python main.py

