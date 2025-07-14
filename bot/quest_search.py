from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from bot.sql_database import SQLDatabase
from bot.models import Quest

class QuestSearchManager:
    """Manages quest search functionality"""

    def __init__(self, database):
        self.database = database

    async def search_quests(self, guild_id: int, keyword: str, rank_filter: str = None, category_filter: str = None, limit: int = 20) -> List[Quest]:
        """Search quests with keyword and filters"""
        try:
            # Build dynamic query
            query_parts = ["SELECT * FROM quests WHERE guild_id = $1"]
            params = [guild_id]
            param_count = 1

            # Add keyword search
            if keyword:
                param_count += 1
                query_parts.append(f"AND (LOWER(title) LIKE LOWER(${param_count}) OR LOWER(description) LIKE LOWER(${param_count}))")
                params.append(f'%{keyword}%')

            # Add filters
            if category_filter:
                param_count += 1
                query_parts.append(f"AND category = ${param_count}")
                params.append(category_filter)

            if rank_filter:
                param_count += 1
                query_parts.append(f"AND rank = ${param_count}")
                params.append(rank_filter)

            # Add ordering and limit
            query_parts.append("ORDER BY created_at DESC")
            query_parts.append(f"LIMIT {limit}")

            full_query = " ".join(query_parts)

            async with self.database.pool.acquire() as conn:
                rows = await conn.fetch(full_query, *params)

                quests = []
                for row in rows:
                    quest = Quest(
                        quest_id=row['quest_id'],
                        title=row['title'],
                        description=row['description'],
                        creator_id=row['creator_id'],
                        guild_id=row['guild_id'],
                        requirements=row['requirements'] or '',
                        reward=row['reward'] or '',
                        rank=row['rank'] or 'normal',
                        category=row['category'] or 'other',
                        status=row['status'] or 'available',
                        created_at=row['created_at'],
                        required_role_ids=list(row['required_role_ids']) if row['required_role_ids'] else []
                    )
                    quests.append(quest)

                return quests

        except Exception as e:
            print(f"Error searching quests: {e}")
            return []