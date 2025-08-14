"""
Channel creator for sniped usernames
"""

import asyncio
import logging
from typing import Optional
from telethon import TelegramClient
from telethon.errors import UsernameOccupiedError, FloodWaitError
from telethon.tl.functions.channels import CreateChannelRequest, UpdateUsernameRequest, DeleteChannelRequest
from config import CHANNEL_TITLE_TEMPLATE, CHANNEL_MESSAGE

logger = logging.getLogger(__name__)

class ChannelCreator:
    def __init__(self):
        pass
    
    async def create_channel(self, client: TelegramClient, username: str) -> tuple[bool, str]:
        """Create a channel with the sniped username"""
        try:
            logger.info(f"Creating channel for username: @{username}")
            
            # Create the channel
            result = await client(CreateChannelRequest(
                title=CHANNEL_TITLE_TEMPLATE,
                about="",  # Empty description as requested
                megagroup=False  # Create a channel, not a supergroup
            ))
            
            # Get the created channel
            channel = result.chats[0]
            
            # Try to set the username
            try:
                await client(UpdateUsernameRequest(
                    channel=channel,
                    username=username
                ))
                
                logger.info(f"✅ Successfully set username @{username} for channel")
                
                # Send the required message
                await client.send_message(channel, CHANNEL_MESSAGE)
                
                logger.info(f"🎯 CHANNEL CREATED: @{username}")
                
                return True, f"✅ Canale creato con successo!\nTitolo: {CHANNEL_TITLE_TEMPLATE}\nUsername: @{username}\nMessaggio inviato: {CHANNEL_MESSAGE}"
                
            except UsernameOccupiedError:
                # Username was taken between check and creation
                logger.warning(f"Username @{username} was taken during creation")
                
                # Delete the channel since we couldn't set the username
                await client(DeleteChannelRequest(channel=channel))
                
                return False, f"❌ Username @{username} è stato preso durante la creazione"
                
            except Exception as e:
                logger.error(f"Error setting username for channel: {e}")
                
                # Try to delete the channel
                try:
                    await client(DeleteChannelRequest(channel=channel))
                except:
                    pass
                
                return False, f"❌ Errore nell'impostare username: {str(e)}"
                
        except FloodWaitError as e:
            logger.warning(f"Flood wait error when creating channel: {e.seconds} seconds")
            return False, f"❌ Limite di velocità raggiunto. Aspetta {e.seconds} secondi."
            
        except Exception as e:
            logger.error(f"Error creating channel for @{username}: {e}")
            return False, f"❌ Errore nella creazione del canale: {str(e)}"
    
    async def create_channel_with_fallback(self, clients: dict, username: str) -> tuple[bool, str, str]:
        """Try to create channel with multiple clients as fallback"""
        for phone, client in clients.items():
            try:
                success, message = await self.create_channel(client, username)
                if success:
                    channel_link = f"https://t.me/{username}"
                    return True, f"Canale creato usando {phone}: {message}", channel_link
                else:
                    logger.warning(f"Failed to create channel with {phone}: {message}")
                    continue
                    
            except Exception as e:
                logger.error(f"Error using client {phone}: {e}")
                continue
        
        return False, "❌ Impossibile creare il canale con tutti gli account disponibili", ""
