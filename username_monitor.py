"""
Username availability monitor
"""

import asyncio
import logging
from typing import List, Dict, Tuple
from telethon import TelegramClient
from telethon.errors import UsernameNotOccupiedError, FloodWaitError
from database import DatabaseManager

logger = logging.getLogger(__name__)

class UsernameMonitor:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.monitoring = False
        self.monitor_task = None

    async def check_username_availability(self, client: TelegramClient, username: str) -> bool:
        """Check if a username is available"""
        try:
            # Try to get entity by username
            await client.get_entity(f"@{username}")
            return False  # Username is taken
        except UsernameNotOccupiedError:
            return True   # Username is available
        except FloodWaitError as e:
            logger.warning(f"Flood wait error: {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            return False
        except ValueError as e:
            # Check if it's the "No user has X as username" error which means it's available
            if "No user has" in str(e) and "as username" in str(e):
                logger.info(f"Username @{username} is available!")
                return True
            logger.error(f"ValueError checking username @{username}: {e}")
            return False
        except Exception as e:
            # Check for other indicators that username is available
            error_msg = str(e).lower()
            if any(indicator in error_msg for indicator in ["no user", "not found", "does not exist"]):
                logger.info(f"Username @{username} appears to be available (error: {e})")
                return True
            logger.error(f"Error checking username @{username}: {e}")
            return False

    def distribute_usernames(self, usernames: List[str], client_count: int) -> List[List[str]]:
        """Distribute usernames among available clients"""
        if client_count == 0:
            return []

        if len(usernames) == 0:
            return [[] for _ in range(client_count)]

        # Sort usernames for consistent distribution
        sorted_usernames = sorted(usernames)
        chunks = [[] for _ in range(client_count)]

        if len(usernames) >= client_count:
            # Più username che client: distribuzione round-robin normale
            for i, username in enumerate(sorted_usernames):
                client_index = i % client_count
                chunks[client_index].append(username)
        else:
            # Più client che username: ogni username va a un client diverso, 
            # poi i client rimanenti alternano tra tutti gli username
            
            # Prima assegna 1 username per client (fino agli username disponibili)
            for i, username in enumerate(sorted_usernames):
                chunks[i].append(username)
            
            # I client rimanenti ricevono tutti gli username per alternare
            for client_index in range(len(usernames), client_count):
                chunks[client_index] = sorted_usernames.copy()

        # Log detailed distribution
        logger.info(f"📋 Distribuzione dettagliata di {len(usernames)} username tra {client_count} client:")
        for i, chunk in enumerate(chunks):
            if chunk:
                logger.info(f"  Client {i+1}: {len(chunk)} username → {chunk}")
            else:
                logger.info(f"  Client {i+1}: 0 username → []")

        return chunks

    async def monitor_username_batch(self, client: TelegramClient, usernames: List[str],
                                   check_interval: int, client_id: str) -> List[str]:
        """Monitor a batch of usernames with one client"""
        available_usernames = []

        logger.info(f"Client {client_id} monitoring {len(usernames)} usernames: {usernames}")

        for username in usernames:
            try:
                if await self.check_username_availability(client, username):
                    logger.info(f"🎯 FOUND AVAILABLE: @{username}")
                    available_usernames.append(username)
                else:
                    logger.debug(f"Username @{username} is taken")

                # Update last checked in database
                self.db.update_username_check(username)

                # Wait between checks
                if check_interval > 0:
                    await asyncio.sleep(check_interval)

            except Exception as e:
                logger.error(f"Error monitoring @{username}: {e}")
                continue

        return available_usernames

    async def start_monitoring(self, clients: Dict[str, TelegramClient],
                             found_callback=None) -> None:
        """Start monitoring usernames with multiple clients in pairs"""
        if self.monitoring:
            logger.warning("Monitoring already running")
            return

        self.monitoring = True
        logger.info("Starting username monitoring...")

        # Filter out disconnected clients
        active_clients = {}
        for phone, client in clients.items():
            try:
                if client.is_connected():
                    active_clients[phone] = client
                else:
                    logger.warning(f"Client {phone} is disconnected, excluding from monitoring")
            except Exception as e:
                logger.warning(f"Client {phone} has connection issues, excluding: {e}")

        if not active_clients:
            logger.error("No active clients available for monitoring")
            return

        client_list = list(active_clients.items())
        client_count = len(client_list)

        logger.info(f"Using {client_count} active clients out of {len(clients)} total clients")

        if client_count == 0:
            logger.warning("No active clients for monitoring")
            return

        # Get configuration
        check_interval = int(self.db.get_config('check_interval', '30'))
        pair_delay = int(self.db.get_config('pair_delay', '60'))

        logger.info(f"Monitoring with {client_count} clients, "
                   f"check interval: {check_interval}s, pair delay: {pair_delay}s")

        while self.monitoring:
            try:
                # Get current usernames to monitor
                usernames = self.db.get_active_usernames()

                if not usernames:
                    logger.info("No usernames to monitor. Waiting...")
                    await asyncio.sleep(30)
                    continue

                # Distribute usernames among clients
                username_chunks = self.distribute_usernames(usernames, client_count)

                # Log distribution details
                logger.info(f"📊 Distribuzione username tra {client_count} client:")
                total_assigned = 0
                for i, (phone, _) in enumerate(client_list):
                    chunk = username_chunks[i] if i < len(username_chunks) else []
                    total_assigned += len(chunk)
                    logger.info(f"  {phone}: {len(chunk)} username → {chunk}")

                # Verify all usernames are assigned
                if total_assigned != len(usernames):
                    logger.warning(f"⚠️ PROBLEMA DISTRIBUZIONE: {len(usernames)} username totali, "
                                 f"ma solo {total_assigned} assegnati!")
                else:
                    logger.info(f"✅ Tutti i {len(usernames)} username sono stati assegnati correttamente")

                # Work with clients sequentially (alternating) - use all clients that have usernames
                active_client_indices = [i for i in range(client_count) if username_chunks[i]]

                if not active_client_indices:
                    logger.warning("No clients have usernames assigned")
                    await asyncio.sleep(30)
                    continue

                # Count unique usernames vs total clients
                unique_usernames = len(usernames)
                total_clients = len(active_client_indices)
                
                if unique_usernames >= client_count:
                    logger.info(f"🎯 Usando tutti i {total_clients} client (distribuzione normale)")
                else:
                    primary_clients = unique_usernames
                    alternating_clients = total_clients - primary_clients
                    logger.info(f"🎯 Usando {total_clients} client: {primary_clients} primari + {alternating_clients} alternanti")

                current_index = 0
                round_counter = 0
                
                while self.monitoring:
                    # Get current active client
                    client_index = active_client_indices[current_index]
                    phone, client = client_list[client_index]
                    chunk = username_chunks[client_index]

                    # Determine what usernames this client should check
                    if len(usernames) >= client_count:
                        # Distribuzione normale: ogni client ha i suoi username fissi
                        usernames_to_check = chunk
                        is_alternating = False
                    else:
                        # Più client che username
                        if client_index < len(usernames):
                            # Client primario: controlla sempre lo stesso username
                            usernames_to_check = [chunk[0]] if chunk else []
                            is_alternating = False
                        else:
                            # Client alternante: controlla un username diverso ogni turno
                            username_index = round_counter % len(usernames)
                            usernames_to_check = [usernames[username_index]]
                            is_alternating = True

                    alternating_info = " (alternante)" if is_alternating else ""
                    logger.info(f"🔄 Turno di {phone}{alternating_info} - Controllando {len(usernames_to_check)} username: {usernames_to_check}")

                    # Check this client's usernames
                    try:
                        results = await self.monitor_username_batch(
                            client, usernames_to_check, check_interval, phone
                        )

                        # Process any found usernames
                        for username in results:
                            if found_callback:
                                await found_callback(username)

                    except Exception as e:
                        logger.error(f"Error in client {phone}: {e}")

                    # Move to next active client (round-robin)
                    current_index = (current_index + 1) % len(active_client_indices)

                    # If we completed a full round, wait before starting next round
                    if current_index == 0:
                        round_counter += 1
                        if pair_delay > 0 and self.monitoring:
                            logger.info(f"🔄 Completato giro {round_counter}. Aspettando {pair_delay}s prima del prossimo giro...")
                            await asyncio.sleep(pair_delay)

                        # Re-check for username changes
                        new_usernames = self.db.get_active_usernames()
                        if new_usernames != usernames:
                            logger.info("📝 Lista username cambiata, ridistribuendo...")
                            break

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(30)

    def stop_monitoring(self):
        """Stop the monitoring process"""
        self.monitoring = False
        logger.info("Stopping username monitoring...")

    def is_monitoring(self) -> bool:
        """Check if monitoring is active"""
        return self.monitoring