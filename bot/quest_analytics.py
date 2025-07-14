from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from bot.sql_database import SQLDatabase

@dataclass
class QuestAnalytics:
    """Quest analytics data"""
    quest_id: str
    title: str
    category: str
    rank: str
    total_accepts: int = 0
    total_completions: int = 0
    total_rejections: int = 0
    success_rate: float = 0.0
    average_completion_time: Optional[float] = None
    popularity_score: float = 0.0

@dataclass
class CategoryStats:
    """Category-wise statistics"""
    category: str
    total_quests: int
    total_accepts: int
    total_completions: int
    average_success_rate: float

class QuestAnalyticsManager:
    """Manages quest analytics and popularity tracking"""

    def __init__(self, database):
        self.database = database

    async def track_quest_view(self, quest_id: str, user_id: int):
        """Track when a user views a quest"""
        # This would be called when users use /quest_info
        await self._update_quest_metric(quest_id, "views", 1)

    async def track_quest_accept(self, quest_id: str, user_id: int):
        """Track when a user accepts a quest"""
        await self._update_quest_metric(quest_id, "accepts", 1)

    async def track_quest_completion(self, quest_id: str, user_id: int, completion_time_hours: float):
        """Track when a user completes a quest"""
        await self._update_quest_metric(quest_id, "completions", 1)
        await self._update_completion_time(quest_id, completion_time_hours)

    async def track_quest_rejection(self, quest_id: str, user_id: int):
        """Track when a quest submission is rejected"""
        await self._update_quest_metric(quest_id, "rejections", 1)

    async def get_quest_analytics(self, quest_id: str) -> Optional[QuestAnalytics]:
        """Get analytics for a specific quest"""
        # This would query your database for analytics data
        quest = await self.database.get_quest(quest_id)
        if not quest:
            return None

        # Get progress data to calculate analytics
        async with self.database.pool.acquire() as conn:
            stats = await conn.fetchrow('''
                SELECT 
                    COUNT(CASE WHEN status = 'accepted' THEN 1 END) as accepts,
                    COUNT(CASE WHEN status = 'approved' THEN 1 END) as completions,
                    COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejections
                FROM quest_progress 
                WHERE quest_id = $1
            ''', quest_id)

            if stats:
                total_accepts = stats['accepts'] + stats['completions'] + stats['rejections']
                success_rate = (stats['completions'] / total_accepts * 100) if total_accepts > 0 else 0

                return QuestAnalytics(
                    quest_id=quest_id,
                    title=quest.title,
                    category=quest.category,
                    rank=quest.rank,
                    total_accepts=total_accepts,
                    total_completions=stats['completions'],
                    total_rejections=stats['rejections'],
                    success_rate=success_rate,
                    popularity_score=self._calculate_popularity(total_accepts, stats['completions'])
                )

        return None

    async def get_popular_quests(self, guild_id: int, limit: int = 10) -> List[QuestAnalytics]:
        """Get most popular quests in a guild"""
        quests = await self.database.get_guild_quests(guild_id)
        analytics = []

        for quest in quests:
            quest_analytics = await self.get_quest_analytics(quest.quest_id)
            if quest_analytics:
                analytics.append(quest_analytics)

        # Sort by popularity score
        analytics.sort(key=lambda x: x.popularity_score, reverse=True)
        return analytics[:limit]

    async def get_category_stats(self, guild_id: int) -> List[CategoryStats]:
        """Get statistics by category"""
        async with self.database.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT 
                    q.category,
                    COUNT(q.quest_id) as total_quests,
                    COUNT(qp.quest_id) as total_accepts,
                    COUNT(CASE WHEN qp.status = 'approved' THEN 1 END) as completions
                FROM quests q
                LEFT JOIN quest_progress qp ON q.quest_id = qp.quest_id
                WHERE q.guild_id = $1
                GROUP BY q.category
            ''', guild_id)

            stats = []
            for row in rows:
                success_rate = (row['completions'] / row['total_accepts'] * 100) if row['total_accepts'] > 0 else 0
                stats.append(CategoryStats(
                    category=row['category'],
                    total_quests=row['total_quests'],
                    total_accepts=row['total_accepts'],
                    total_completions=row['completions'],
                    average_success_rate=success_rate
                ))

            return stats

    async def get_trending_quests(self, guild_id: int, days: int = 7) -> List[QuestAnalytics]:
        """Get trending quests in the last N days"""
        since_date = datetime.now() - timedelta(days=days)

        async with self.database.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT q.quest_id, COUNT(qp.quest_id) as recent_activity
                FROM quests q
                JOIN quest_progress qp ON q.quest_id = qp.quest_id
                WHERE q.guild_id = $1 AND qp.accepted_at >= $2
                GROUP BY q.quest_id
                ORDER BY recent_activity DESC
                LIMIT 10
            ''', guild_id, since_date)

            trending = []
            for row in rows:
                analytics = await self.get_quest_analytics(row['quest_id'])
                if analytics:
                    trending.append(analytics)

            return trending

    def _calculate_popularity(self, accepts: int, completions: int) -> float:
        """Calculate popularity score based on accepts and completions"""
        base_score = accepts * 1.0
        completion_bonus = completions * 2.0
        return base_score + completion_bonus

    async def _update_quest_metric(self, quest_id: str, metric: str, value: int):
        """Update a specific metric for a quest"""
        # This would update analytics tables in your database
        pass

    async def _update_completion_time(self, quest_id: str, completion_time: float):
        """Update average completion time for a quest"""
        # This would update completion time tracking
        pass

    async def get_guild_analytics(self, guild_id: int) -> dict:
        """Get comprehensive analytics for a guild"""
        try:
            async with self.database.pool.acquire() as conn:
                # Get overall statistics
                stats = await conn.fetchrow('''
                    SELECT 
                        COUNT(DISTINCT q.quest_id) as total_quests,
                        COUNT(CASE WHEN qp.status = 'approved' THEN 1 END) as completed_quests,
                        COUNT(DISTINCT qp.user_id) as active_users
                    FROM quests q
                    LEFT JOIN quest_progress qp ON q.quest_id = qp.quest_id
                    WHERE q.guild_id = $1
                ''', guild_id)

                # Calculate success rate
                total_attempts = await conn.fetchval('''
                    SELECT COUNT(*) FROM quest_progress qp
                    JOIN quests q ON qp.quest_id = q.quest_id
                    WHERE q.guild_id = $1 AND qp.status IN ('approved', 'rejected')
                ''', guild_id)

                success_rate = 0
                if total_attempts > 0 and stats['completed_quests']:
                    success_rate = (stats['completed_quests'] / total_attempts) * 100

                # Get popular categories
                popular_categories = await conn.fetch('''
                    SELECT category, COUNT(*) as count
                    FROM quests
                    WHERE guild_id = $1
                    GROUP BY category
                    ORDER BY count DESC
                    LIMIT 5
                ''', guild_id)

                # Get popular ranks
                popular_ranks = await conn.fetch('''
                    SELECT rank, COUNT(*) as count
                    FROM quests
                    WHERE guild_id = $1
                    GROUP BY rank
                    ORDER BY count DESC
                    LIMIT 5
                ''', guild_id)

                # Get top creators
                top_creators = await conn.fetch('''
                    SELECT creator_id, COUNT(*) as count
                    FROM quests
                    WHERE guild_id = $1
                    GROUP BY creator_id
                    ORDER BY count DESC
                    LIMIT 5
                ''', guild_id)

                return {
                    'total_quests': stats['total_quests'] or 0,
                    'completed_quests': stats['completed_quests'] or 0,
                    'active_users': stats['active_users'] or 0,
                    'success_rate': success_rate,
                    'popular_categories': [(row['category'], row['count']) for row in popular_categories],
                    'popular_ranks': [(row['rank'], row['count']) for row in popular_ranks],
                    'top_creators': [(row['creator_id'], row['count']) for row in top_creators]
                }
        except Exception as e:
            print(f"Error getting guild analytics: {e}")
            return {
                'total_quests': 0,
                'completed_quests': 0,
                'active_users': 0,
                'success_rate': 0,
                'popular_categories': [],
                'popular_ranks': [],
                'top_creators': []
            }