#!/usr/bin/env python3
"""
USDC Treasurer Skill for OpenClaw
Hackathon Track: Best OpenClaw Skill
Interacts with USDC testnet + CCTP
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict
from dataclasses import dataclass

from web3 import Web3
from dotenv import load_dotenv

# โหลด environment variables
load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("USDC-Treasurer")


@dataclass
class Transaction:
    """เก็บข้อมูลธุรกรรม"""
    tx_hash: str
    from_address: str
    to_address: str
    amount: Decimal
    timestamp: datetime
    status: str
    note: Optional[str] = None


class USDCTreasurer:
    """
    Agent-native USDC treasurer
    จัดการ USDC testnet ผ่าน Telegram commands
    """
    
    # USDC Contract ABI (minimal - ใช้แค่ transfer และ balanceOf)
    USDC_ABI = [
        {
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "_to", "type": "address"},
                {"name": "_value", "type": "uint256"}
            ],
            "name": "transfer",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function"
        }
    ]
    
    def __init__(self):
        # Web3 setup
        self.rpc_url = os.getenv("USDC_TESTNET_RPC", "https://rpc.sepolia.org")
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        # Contract
        self.usdc_address = os.getenv(
            "USDC_CONTRACT_ADDRESS", 
            "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"  # Sepolia USDC
        )
        self.usdc = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.usdc_address),
            abi=self.USDC_ABI
        )
        
        # Wallet
        self.private_key = os.getenv("PRIVATE_KEY")
        if self.private_key:
            self.account = self.w3.eth.account.from_key(self.private_key)
            self.address = self.account.address
        else:
            self.address = None
            
        # Data storage
        self.data_file = os.path.expanduser("~/.openclaw/workspace/usdc_treasurer.json")
        self.transactions: list = []
        self.load_data()
        
        logger.info(f"USDC Treasurer initialized. Address: {self.address}")
    
    def load_data(self):
        """โหลดข้อมูลธุรกรรมที่บันทึกไว้"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.transactions = [
                        Transaction(
                            tx_hash=t['tx_hash'],
                            from_address=t['from_address'],
                            to_address=t['to_address'],
                            amount=Decimal(t['amount']),
                            timestamp=datetime.fromisoformat(t['timestamp']),
                            status=t['status'],
                            note=t.get('note')
                        ) for t in data.get('transactions', [])
                    ]
                logger.info(f"Loaded {len(self.transactions)} transactions")
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            self.transactions = []
    
    def save_data(self):
        """บันทึกข้อมูลธุรกรรม"""
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            data = {
                'transactions': [
                    {
                        'tx_hash': t.tx_hash,
                        'from_address': t.from_address,
                        'to_address': t.to_address,
                        'amount': str(t.amount),
                        'timestamp': t.timestamp.isoformat(),
                        'status': t.status,
                        'note': t.note
                    } for t in self.transactions
                ],
                'last_updated': datetime.now().isoformat()
            }
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving data: {e}")
    
    async def get_balance(self, address: Optional[str] = None) -> Dict:
        """
        เช็คยอด USDC
        ถ้าไม่ระบุ address จะใช้ address ของตัวเอง
        """
        try:
            check_address = address or self.address
            if not check_address:
                return {'error': 'No address configured'}
            
            # USDC มี 6 decimals
            raw_balance = self.usdc.functions.balanceOf(
                Web3.to_checksum_address(check_address)
            ).call()
            
            balance = Decimal(raw_balance) / Decimal(10**6)
            
            return {
                'address': check_address,
                'balance': float(balance),
                'raw_balance': raw_balance,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return {'error': str(e)}
    
    async def send_usdc(self, to_address: str, amount: float, note: Optional[str] = None) -> Dict:
        """
        ส่ง USDC ไปยัง address อื่น
        """
        try:
            if not self.private_key:
                return {'error': 'No private key configured'}
            
            # Validate address
            if not Web3.is_address(to_address):
                return {'error': 'Invalid address'}
            
            to_address = Web3.to_checksum_address(to_address)
            
            # Convert amount (USDC has 6 decimals)
            amount_decimal = Decimal(str(amount))
            amount_raw = int(amount_decimal * Decimal(10**6))
            
            # Check balance first
            balance_info = await self.get_balance()
            if 'error' in balance_info:
                return balance_info
            
            current_balance = Decimal(str(balance_info['balance']))
            if current_balance < amount_decimal:
                return {
                    'error': f'Insufficient balance. Have: {current_balance}, Need: {amount_decimal}'
                }
            
            # Build transaction
            nonce = self.w3.eth.get_transaction_count(self.address)
            
            tx = self.usdc.functions.transfer(
                to_address,
                amount_raw
            ).build_transaction({
                'from': self.address,
                'nonce': nonce,
                'gas': 100000,
                'gasPrice': self.w3.eth.gas_price
            })
            
            # Sign and send
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            # Record transaction
            transaction = Transaction(
                tx_hash=tx_hash.hex(),
                from_address=self.address,
                to_address=to_address,
                amount=amount_decimal,
                timestamp=datetime.now(),
                status='confirmed' if receipt['status'] == 1 else 'failed',
                note=note
            )
            self.transactions.append(transaction)
            self.save_data()
            
            return {
                'success': True,
                'tx_hash': tx_hash.hex(),
                'from': self.address,
                'to': to_address,
                'amount': float(amount_decimal),
                'gas_used': receipt['gasUsed'],
                'status': transaction.status,
                'explorer_link': f"https://sepolia.etherscan.io/tx/{tx_hash.hex()}"
            }
            
        except Exception as e:
            logger.error(f"Error sending USDC: {e}")
            return {'error': str(e)}
    
    async def get_transaction_history(self, limit: int = 10) -> list:
        """ดึงประวัติธุรกรรม"""
        sorted_txs = sorted(
            self.transactions, 
            key=lambda x: x.timestamp, 
            reverse=True
        )
        return [
            {
                'tx_hash': t.tx_hash,
                'from': t.from_address[:10] + '...',
                'to': t.to_address[:10] + '...',
                'amount': float(t.amount),
                'time': t.timestamp.strftime('%Y-%m-%d %H:%M'),
                'status': t.status,
                'note': t.note
            }
            for t in sorted_txs[:limit]
        ]
    
    async def check_and_notify(self):
        """
        Cron job: เช็คยอดและแจ้งเตือนถ้ามีเปลี่ยนแปลง
        """
        balance_info = await self.get_balance()
        if 'error' not in balance_info:
            logger.info(f"Balance check: {balance_info['balance']} USDC")
            # สามารถเพิ่ม logic แจ้งเตือน Telegram ได้ที่นี่
        return balance_info


# OpenClaw Integration
class OpenClawHandler:
    """
    Handler สำหรับรับคำสั่งจาก OpenClaw/Telegram
    """
    
    def __init__(self):
        self.treasurer = USDCTreasurer()
    
    async def handle_command(self, command: str, args: list) -> str:
        """
        จัดการคำสั่งต่างๆ
        """
        cmd = command.lower()
        
        if cmd == 'balance':
            result = await self.treasurer.get_balance()
            if 'error' in result:
                return f"❌ Error: {result['error']}"
            return f"💰 Balance: **{result['balance']:.2f} USDC**\nAddress: `{result['address']}`"
        
        elif cmd == 'send':
            if len(args) < 2:
                return "❌ Usage: /send <address> <amount> [note]"
            
            to_address = args[0]
            try:
                amount = float(args[1])
            except ValueError:
                return "❌ Amount must be a number"
            
            note = ' '.join(args[2:]) if len(args) > 2 else None
            
            result = await self.treasurer.send_usdc(to_address, amount, note)
            
            if 'error' in result:
                return f"❌ Transfer failed: {result['error']}"
            
            return f"""✅ **Transfer Successful!**

💸 Amount: {result['amount']:.2f} USDC
📤 To: `{result['to']}`
🔗 [View on Explorer]({result['explorer_link']})
⛽ Gas used: {result['gas_used']}"""
        
        elif cmd == 'history':
            history = await self.treasurer.get_transaction_history()
            if not history:
                return "📭 No transactions yet"
            
            lines = ["📜 **Recent Transactions**", ""]
            for i, tx in enumerate(history, 1):
                icon = "✅" if tx['status'] == 'confirmed' else "❌"
                lines.append(f"{icon} {tx['time']}: {tx['amount']:.2f} USDC")
                lines.append(f"   From: {tx['from']} → To: {tx['to']}")
                if tx['note']:
                    lines.append(f"   📝 {tx['note']}")
                lines.append("")
            
            return '\n'.join(lines)
        
        elif cmd == 'address':
            if not self.treasurer.address:
                return "❌ No wallet configured"
            return f"🏦 **Your Address**\n`{self.treasurer.address}`\n\nSend testnet USDC here!"
        
        else:
            return f"""🦞 **USDC Treasurer**

Available commands:
/balance - Check your USDC balance
/send <address> <amount> [note] - Send USDC
/history - View transaction history
/address - Show your wallet address

Network: Sepolia Testnet"""


# สำหรับรัน standalone
async def main():
    handler = OpenClawHandler()
    
    # Test commands
    print(await handler.handle_command('balance', []))
    print("\n" + "="*50 + "\n")
    print(await handler.handle_command('address', []))


if __name__ == "__main__":
    asyncio.run(main())