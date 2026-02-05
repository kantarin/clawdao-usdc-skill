# 🦞 USDC Treasurer - OpenClaw Skill

**Track:** Best OpenClaw Skill  
**Hackathon:** OpenClaw USDC Hackathon on Moltbook

An autonomous treasurer skill that enables OpenClaw agents to manage USDC on testnet, 
process payments, and maintain transaction records - all via Telegram commands.

## 🎯 What It Does

- **Check Balance:** Real-time USDC balance queries
- **Send Payments:** Transfer USDC to any address with gas optimization
- **Transaction History:** Persistent logging of all operations
- **Cron Monitoring:** Automated balance checks every 6 hours
- **Multi-agent Ready:** Designed for agent-to-agent payments

## 🛠️ Tech Stack

- **OpenClaw:** Persistent memory, cron jobs, Telegram integration
- **Web3.py:** Ethereum interaction
- **USDC:** Sepolia testnet (6 decimals standard)
- **CCTP Ready:** Architecture prepared for Cross-Chain Transfer Protocol

## 🚀 Quick Start

```bash
# Install dependencies
pip install web3 python-dotenv

# Configure
cp .env.example .env
# Edit .env with your testnet credentials

# Run
python treasurer.py