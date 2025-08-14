#!/usr/bin/env python3
"""
Telegram Username Sniper Bot
Main entry point for the userbot sniper system
"""

import asyncio
import logging
import os
from userbot import UserbotSniper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sniper.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Main entry point"""
    try:
        # Initialize the userbot sniper
        sniper = UserbotSniper()
        
        logger.info("Starting Telegram Username Sniper Bot...")
        
        # Start the bot
        await sniper.start()
        
        logger.info("Bot started successfully. Waiting for commands...")
        
        # Keep the bot running
        await sniper.run_until_disconnected()
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
