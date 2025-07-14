
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from bot.sql_database import SQLDatabase

@dataclass
class TeamQuest:
    """Team quest data model"""
    quest_id: str
    team_size_required: int
    team_members: Set[int] = field(default_factory=set)
    team_leader: Optional[int] = None
    is_team_complete: bool = False
    team_formed_at: Optional[datetime] = None

@dataclass
class TeamProgress:
    """Team quest progress tracking"""
    quest_id: str
    user_id: int
    guild_id: int
    team_role: str  # "leader" or "member"
    joined_team_at: datetime
    individual_progress: Dict[str, any] = field(default_factory=dict)

class TeamQuestManager:
    """Manages team-based quests"""
    
    def __init__(self, database: SQLDatabase):
        self.database = database
        self.active_teams: Dict[str, TeamQuest] = {}
    
    async def create_team_quest(self, quest_id: str, team_size: int, leader_id: int) -> TeamQuest:
        """Create a new team for a quest"""
        team_quest = TeamQuest(
            quest_id=quest_id,
            team_size_required=team_size,
            team_members={leader_id},
            team_leader=leader_id,
            team_formed_at=datetime.now()
        )
        
        self.active_teams[quest_id] = team_quest
        
        # Save team leader progress
        await self._save_team_progress(TeamProgress(
            quest_id=quest_id,
            user_id=leader_id,
            guild_id=0,  # Will be updated with actual guild_id
            team_role="leader",
            joined_team_at=datetime.now()
        ))
        
        return team_quest
    
    async def join_team(self, quest_id: str, user_id: int, guild_id: int) -> bool:
        """Join a team for a quest"""
        if quest_id not in self.active_teams:
            return False
        
        team = self.active_teams[quest_id]
        
        if len(team.team_members) >= team.team_size_required:
            return False
        
        if user_id in team.team_members:
            return False
        
        team.team_members.add(user_id)
        
        if len(team.team_members) == team.team_size_required:
            team.is_team_complete = True
        
        # Save team member progress
        await self._save_team_progress(TeamProgress(
            quest_id=quest_id,
            user_id=user_id,
            guild_id=guild_id,
            team_role="member",
            joined_team_at=datetime.now()
        ))
        
        return True
    
    async def get_team_status(self, quest_id: str) -> Optional[TeamQuest]:
        """Get team status for a quest"""
        return self.active_teams.get(quest_id)
    
    async def is_team_complete(self, quest_id: str) -> bool:
        """Check if team is complete for a quest"""
        team = self.active_teams.get(quest_id)
        return team.is_team_complete if team else False
    
    async def get_team_members(self, quest_id: str) -> List[int]:
        """Get list of team members"""
        team = self.active_teams.get(quest_id)
        return list(team.team_members) if team else []
    
    async def _save_team_progress(self, progress: TeamProgress):
        """Save team progress to database"""
        # This would integrate with your existing database system
        pass
