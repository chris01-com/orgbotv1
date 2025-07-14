
from typing import List, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field
from bot.sql_database import SQLDatabase

@dataclass
class QuestBookmark:
    """Quest bookmark data model"""
    user_id: int
    guild_id: int
    quest_id: str
    bookmarked_at: datetime = field(default_factory=datetime.now)
    notes: str = ""

class QuestBookmarkManager:
    """Manages quest bookmarking system"""
    
    def __init__(self, database: SQLDatabase):
        self.database = database
    
    async def bookmark_quest(self, user_id: int, guild_id: int, quest_id: str, notes: str = "") -> bool:
        """Bookmark a quest for later"""
        try:
            async with self.database.pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO quest_bookmarks (user_id, guild_id, quest_id, bookmarked_at, notes)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (user_id, quest_id) DO UPDATE SET
                        notes = EXCLUDED.notes,
                        bookmarked_at = EXCLUDED.bookmarked_at
                ''', user_id, guild_id, quest_id, datetime.now(), notes)
            return True
        except Exception as e:
            print(f"Error bookmarking quest: {e}")
            return False
    
    async def remove_bookmark(self, user_id: int, quest_id: str) -> bool:
        """Remove a quest bookmark"""
        try:
            async with self.database.pool.acquire() as conn:
                result = await conn.execute('''
                    DELETE FROM quest_bookmarks 
                    WHERE user_id = $1 AND quest_id = $2
                ''', user_id, quest_id)
                return result != 'DELETE 0'
        except Exception as e:
            print(f"Error removing bookmark: {e}")
            return False
    
    async def get_user_bookmarks(self, user_id: int, guild_id: int = None) -> List[dict]:
        """Get all bookmarks for a user, optionally filtered by guild"""
        try:
            async with self.database.pool.acquire() as conn:
                if guild_id:
                    rows = await conn.fetch('''
                        SELECT * FROM quest_bookmarks 
                        WHERE user_id = $1 AND guild_id = $2
                        ORDER BY bookmarked_at DESC
                    ''', user_id, guild_id)
                else:
                    rows = await conn.fetch('''
                        SELECT * FROM quest_bookmarks 
                        WHERE user_id = $1
                        ORDER BY bookmarked_at DESC
                    ''', user_id)
                
                bookmarks = []
                for row in rows:
                    bookmark = {
                        'user_id': row['user_id'],
                        'guild_id': row['guild_id'],
                        'quest_id': row['quest_id'],
                        'bookmarked_at': row['bookmarked_at'],
                        'notes': row['notes'] or ""
                    }
                    bookmarks.append(bookmark)
                
                return bookmarks
        except Exception as e:
            print(f"Error getting bookmarks: {e}")
            return []
    
    async def is_bookmarked(self, user_id: int, quest_id: str) -> bool:
        """Check if a quest is bookmarked by user"""
        try:
            async with self.database.pool.acquire() as conn:
                result = await conn.fetchval('''
                    SELECT EXISTS(SELECT 1 FROM quest_bookmarks 
                                WHERE user_id = $1 AND quest_id = $2)
                ''', user_id, quest_id)
                return result
        except Exception as e:
            print(f"Error checking bookmark: {e}")
            return False
    
    async def get_bookmark_count(self, quest_id: str) -> int:
        """Get number of bookmarks for a quest"""
        try:
            async with self.database.pool.acquire() as conn:
                count = await conn.fetchval('''
                    SELECT COUNT(*) FROM quest_bookmarks WHERE quest_id = $1
                ''', quest_id)
                return count or 0
        except Exception as e:
            print(f"Error getting bookmark count: {e}")
            return 0

    async def add_bookmark(self, user_id: int, quest_id: str, notes: str = "") -> bool:
        """Add a quest bookmark (alias for bookmark_quest)"""
        # Get quest to determine guild_id
        from bot.quest_manager import QuestManager
        # We need guild_id, but since this is called from commands, we'll get it from the quest
        try:
            async with self.database.pool.acquire() as conn:
                # First get the guild_id from the quest
                quest_row = await conn.fetchrow('SELECT guild_id FROM quests WHERE quest_id = $1', quest_id)
                if not quest_row:
                    return False
                
                guild_id = quest_row['guild_id']
                return await self.bookmark_quest(user_id, guild_id, quest_id, notes)
        except Exception as e:
            print(f"Error adding bookmark: {e}")
            return False

    async def initialize_bookmarks_table(self):
        """Create bookmarks table if it doesn't exist"""
        try:
            async with self.database.pool.acquire() as conn:
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS quest_bookmarks (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        guild_id BIGINT NOT NULL,
                        quest_id VARCHAR(255) NOT NULL,
                        bookmarked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        notes TEXT DEFAULT '',
                        UNIQUE(user_id, quest_id)
                    )
                ''')
        except Exception as e:
            print(f"Error creating bookmarks table: {e}")
