"""
Main userbot class that coordinates all components
"""

import asyncio
import logging
import re
from typing import Optional
from telethon import TelegramClient, events
from telethon.tl.types import User

from config import API_ID, API_HASH, MIN_CHECK_INTERVAL, MAX_CHECK_INTERVAL, MIN_PAIR_DELAY, MAX_PAIR_DELAY
from database import DatabaseManager
from account_manager import AccountManager
from username_monitor import UsernameMonitor
from channel_creator import ChannelCreator

logger = logging.getLogger(__name__)

class UserbotSniper:
    def __init__(self):
        # Initialize components
        self.db = DatabaseManager()
        self.account_manager = AccountManager(self.db)
        self.username_monitor = UsernameMonitor(self.db)
        self.channel_creator = ChannelCreator()
        
        # Main userbot client (the one that receives commands)
        self.main_client = None
        self.authorized_user_id = None
    
    async def start(self):
        """Start the userbot system"""
        try:
            # Create main client for receiving commands
            self.main_client = TelegramClient('main_session', API_ID, API_HASH)
            await self.main_client.start()
            
            # Get authorized user
            me = await self.main_client.get_me()
            if me:
                self.authorized_user_id = getattr(me, 'id', None)
                first_name = getattr(me, 'first_name', 'Unknown')
                username = getattr(me, 'username', 'N/A')
                logger.info(f"Main userbot started as {first_name} (@{username})")
            
            # Register event handlers
            self.register_handlers()
            
            # Load existing sessions
            await self.account_manager.load_existing_sessions()
            
            logger.info("Userbot sniper system started successfully")
            
            # Auto-start monitoring if accounts and usernames exist
            await self.auto_start_monitoring()
            
        except Exception as e:
            logger.error(f"Error starting userbot: {e}")
            raise
    
    def register_handlers(self):
        """Register command handlers"""
        
        @self.main_client.on(events.NewMessage(pattern=r'\.new (.+)', outgoing=True))
        async def handle_new_account(event):
            phone = event.pattern_match.group(1).strip()
            
            # Validate phone number format
            if not re.match(r'^\+\d{1,15}$', phone):
                await event.edit("❌ Formato numero non valido. Usa formato: +1234567890")
                return
            
            success, message = await self.account_manager.add_new_account(phone)
            await event.edit(f"📱 {message}")
        
        @self.main_client.on(events.NewMessage(pattern=r'\.code (.+)', outgoing=True))
        async def handle_verify_code(event):
            code = event.pattern_match.group(1).strip()
            
            # Get the last pending session (assuming user adds one at a time)
            if not self.account_manager.pending_sessions:
                await event.edit("❌ Nessuna verifica in attesa. Usa prima il comando .new")
                return
            
            # Get the first pending session
            phone = list(self.account_manager.pending_sessions.keys())[0]
            
            success, message = await self.account_manager.verify_code(phone, code)
            await event.edit(f"🔐 {message}")
            
            # If verification was successful, reload sessions
            if success:
                await self.account_manager.load_existing_sessions()
                logger.info("Account list reloaded after successful verification")
        
        @self.main_client.on(events.NewMessage(pattern=r'\.voip', outgoing=True))
        async def handle_list_accounts(event):
            accounts = self.db.get_all_accounts()
            
            if not accounts:
                await event.edit("📱 Nessun account configurato.")
                return
            
            message = "📱 **Account Configurati:**\n\n"
            for i, account in enumerate(accounts, 1):
                status = "✅ Attivo" if account['active'] else "⏳ In attesa"
                message += f"{i}. {account['phone']} - {status}\n"
            
            await event.edit(message)
        
        @self.main_client.on(events.NewMessage(pattern=r'\.delvoip (.+)', outgoing=True))
        async def handle_remove_account(event):
            phone = event.pattern_match.group(1).strip()
            
            # Add + if not present
            if not phone.startswith('+'):
                phone = '+' + phone
            
            # Check if account exists
            if phone not in self.account_manager.clients:
                await event.edit(f"❌ Account {phone} non trovato o non attivo")
                return
            
            try:
                # Disconnect the client
                client = self.account_manager.clients[phone]
                await client.disconnect()
                
                # Remove from active clients
                del self.account_manager.clients[phone]
                
                # Deactivate in database
                self.db.deactivate_account(phone)
                
                await event.edit(f"✅ Account {phone} rimosso dal monitoraggio e disconnesso")
                logger.info(f"Account {phone} removed from monitoring")
                
                # Reload existing sessions to get updated active accounts
                await self.account_manager.load_existing_sessions()
                logger.info("Account list reloaded after removal")
                
            except Exception as e:
                logger.error(f"Error removing account {phone}: {e}")
                await event.edit(f"❌ Errore rimuovendo account {phone}: {str(e)}")
        
        @self.main_client.on(events.NewMessage(pattern=r'\.addusername (@?\w+)', outgoing=True))
        async def handle_add_username(event):
            username = event.pattern_match.group(1).strip()
            
            if self.db.add_username(username):
                await event.edit(f"✅ Username {username} aggiunto alla lista di monitoraggio")
            else:
                await event.edit(f"❌ Username {username} già presente o errore")
        
        @self.main_client.on(events.NewMessage(pattern=r'\.delusername (@?\w+)', outgoing=True))
        async def handle_del_username(event):
            username = event.pattern_match.group(1).strip()
            
            if self.db.remove_username(username):
                await event.edit(f"✅ Username {username} rimosso dalla lista di monitoraggio")
            else:
                await event.edit(f"❌ Username {username} non trovato nella lista")
        
        @self.main_client.on(events.NewMessage(pattern=r'\.lista', outgoing=True))
        async def handle_list_usernames(event):
            usernames = self.db.get_active_usernames()
            
            if not usernames:
                await event.edit("📝 Nessun username in monitoraggio.")
                return
            
            message = "📝 **Username Monitorati:**\n\n"
            for i, username in enumerate(usernames, 1):
                message += f"{i}. @{username}\n"
            
            await event.edit(message)
        
        @self.main_client.on(events.NewMessage(pattern=r'\.setime (\d+)', outgoing=True))
        async def handle_set_time(event):
            interval = int(event.pattern_match.group(1))
            
            if interval < MIN_CHECK_INTERVAL or interval > MAX_CHECK_INTERVAL:
                await event.edit(f"❌ L'intervallo deve essere tra {MIN_CHECK_INTERVAL} e {MAX_CHECK_INTERVAL} secondi")
                return
            
            self.db.set_config('check_interval', str(interval))
            await event.edit(f"⏰ Intervallo di controllo impostato a {interval} secondi")
        
        @self.main_client.on(events.NewMessage(pattern=r'\.coppia (\d+)', outgoing=True))
        async def handle_set_pair_delay(event):
            delay = int(event.pattern_match.group(1))
            
            if delay < MIN_PAIR_DELAY or delay > MAX_PAIR_DELAY:
                await event.edit(f"❌ Il ritardo coppia deve essere tra {MIN_PAIR_DELAY} e {MAX_PAIR_DELAY} secondi")
                return
            
            self.db.set_config('pair_delay', str(delay))
            await event.edit(f"⏰ Ritardo coppia impostato a {delay} secondi")
        
        @self.main_client.on(events.NewMessage(pattern=r'\.start', outgoing=True))
        async def handle_start_monitoring(event):
            if self.username_monitor.is_monitoring():
                await event.edit("⚡ Il monitoraggio è già attivo!")
                return
            
            clients = self.account_manager.get_active_clients()
            if not clients:
                await event.edit("❌ Nessun account attivo disponibile per il monitoraggio")
                return
            
            usernames = self.db.get_active_usernames()
            if not usernames:
                await event.edit("❌ Nessun username da monitorare")
                return
            
            await event.edit(f"🚀 Avvio monitoraggio con {len(clients)} account e {len(usernames)} username...")
            
            # Start monitoring in background
            asyncio.create_task(self.start_monitoring_loop())
        
        @self.main_client.on(events.NewMessage(pattern=r'\.stop', outgoing=True))
        async def handle_stop_monitoring(event):
            if not self.username_monitor.is_monitoring():
                await event.edit("⏹️ Il monitoraggio non è attivo")
                return
            
            self.username_monitor.stop_monitoring()
            await event.edit("⏹️ Monitoraggio fermato")
        
        @self.main_client.on(events.NewMessage(pattern=r'\.status', outgoing=True))
        async def handle_status(event):
            clients = self.account_manager.get_active_clients()
            usernames = self.db.get_active_usernames()
            is_monitoring = self.username_monitor.is_monitoring()
            
            check_interval = self.db.get_config('check_interval', '30')
            pair_delay = self.db.get_config('pair_delay', '60')
            
            status = "📊 **Stato Sniper:**\n\n"
            status += f"🤖 Account Attivi: {len(clients)}\n"
            status += f"👁️ Username Monitorati: {len(usernames)}\n"
            status += f"⚡ Monitoraggio: {'✅ Attivo' if is_monitoring else '⏹️ Fermo'}\n"
            status += f"⏰ Intervallo Controlli: {check_interval}s\n"
            status += f"🔄 Ritardo Coppie: {pair_delay}s\n"
            
            await event.edit(status)
        
        @self.main_client.on(events.NewMessage(pattern=r'\.sniperati', outgoing=True))
        async def handle_sniped_history(event):
            sniped = self.db.get_sniped_usernames(20)  # Show last 20
            
            if not sniped:
                await event.edit("📋 Nessun username sniperato finora.")
                return
            
            message = "📋 **Username Sniperati:**\n\n"
            for i, entry in enumerate(sniped, 1):
                timestamp = entry['timestamp'].split('.')[0] if entry['timestamp'] else "N/A"
                account = entry['account'] or "N/A"
                link = entry['channel_link'] or f"@{entry['username']}"
                message += f"{i}. @{entry['username']}\n"
                message += f"   📅 {timestamp}\n"
                message += f"   🤖 Account: {account}\n"
                message += f"   🔗 {link}\n\n"
            
            await event.edit(message)
        
        @self.main_client.on(events.NewMessage(pattern=r'\.help', outgoing=True))
        async def handle_help(event):
            help_text = """
🤖 **Bot Sniper Username Telegram**

**Gestione Account:**
`.new +1234567890` - Aggiungi nuovo account
`.code 12345` - Verifica account con codice
`.voip` - Lista di tutti gli account
`.delvoip +1234567890` - Rimuovi account dal monitoraggio

**Gestione Username:**
`.addusername @username` - Aggiungi username da monitorare
`.delusername @username` - Rimuovi username
`.lista` - Mostra username monitorati
`.sniperati` - Mostra cronologia username sniperati

**Configurazione:**
`.setime 30` - Imposta intervallo controlli (5-300 secondi)
`.coppia 60` - Imposta ritardo coppie (10-600 secondi)

**Controllo:**
`.start` - Avvia monitoraggio
`.stop` - Ferma monitoraggio
`.status` - Mostra stato attuale
`.help` - Mostra questo aiuto
            """
            await event.edit(help_text)
    
    async def auto_start_monitoring(self):
        """Auto-start monitoring if conditions are met"""
        try:
            clients = self.account_manager.get_active_clients()
            usernames = self.db.get_active_usernames()
            
            if clients and usernames and not self.username_monitor.is_monitoring():
                logger.info(f"🚀 Auto-starting monitoring with {len(clients)} accounts and {len(usernames)} usernames...")
                asyncio.create_task(self.start_monitoring_loop())
        except Exception as e:
            logger.error(f"Error auto-starting monitoring: {e}")
    
    async def start_monitoring_loop(self):
        """Start the monitoring loop"""
        try:
            clients = self.account_manager.get_active_clients()
            
            async def on_username_found(username):
                """Callback when an available username is found"""
                logger.info(f"🎯 Found available username: @{username}")
                
                # Try to create channel
                success, message, channel_link = await self.channel_creator.create_channel_with_fallback(clients, username)
                
                # If channel was created successfully, remove username from monitoring list and add to history
                if success:
                    self.db.remove_username(username)
                    # Extract account used from message
                    account_used = message.split("usando ")[1].split(":")[0] if "usando " in message else "Unknown"
                    self.db.add_sniped_username(username, channel_link, account_used)
                    logger.info(f"✅ Username @{username} removed from monitoring list after successful snipe")
                    message += f"\n\n✅ Username @{username} rimosso dalla lista di monitoraggio"
                
                # Send notification to main chat
                notification = f"🎯 **USERNAME TROVATO**: @{username}\n\n{message}"
                if self.main_client:
                    await self.main_client.send_message('me', notification)
            
            # Start monitoring
            await self.username_monitor.start_monitoring(clients, on_username_found)
            
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            if self.main_client:
                await self.main_client.send_message('me', f"❌ Errore monitoraggio: {str(e)}")
    
    async def run_until_disconnected(self):
        """Keep the bot running"""
        if self.main_client:
            await self.main_client.run_until_disconnected()
    
    async def disconnect(self):
        """Disconnect all clients"""
        try:
            self.username_monitor.stop_monitoring()
            await self.account_manager.disconnect_all()
            if self.main_client:
                await self.main_client.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
