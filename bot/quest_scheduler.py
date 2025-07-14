
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio
from bot.quest_manager import QuestManager
from bot.models import Quest, QuestStatus

@dataclass
class QuestDeadline:
    """Quest deadline tracking"""
    quest_id: str
    deadline: datetime
    warning_sent: bool = False
    expired: bool = False

@dataclass
class RecurringQuest:
    """Recurring quest configuration"""
    template_id: str
    guild_id: int
    creator_id: int
    interval_type: str  # "daily", "weekly", "monthly"
    interval_value: int  # 1 for every day, 2 for every 2 days, etc.
    last_created: Optional[datetime] = None
    is_active: bool = True

class QuestScheduler:
    """Manages quest deadlines and recurring quests"""
    
    def __init__(self, quest_manager: QuestManager):
        self.quest_manager = quest_manager
        self.active_deadlines: Dict[str, QuestDeadline] = {}
        self.recurring_quests: List[RecurringQuest] = []
        self.scheduler_running = False
    
    async def set_quest_deadline(self, quest_id: str, hours: int):
        """Set a deadline for a quest"""
        deadline = datetime.now() + timedelta(hours=hours)
        self.active_deadlines[quest_id] = QuestDeadline(
            quest_id=quest_id,
            deadline=deadline
        )
    
    async def create_recurring_quest(self, template_id: str, guild_id: int, creator_id: int, 
                                   interval_type: str, interval_value: int = 1) -> RecurringQuest:
        """Create a recurring quest schedule"""
        recurring = RecurringQuest(
            template_id=template_id,
            guild_id=guild_id,
            creator_id=creator_id,
            interval_type=interval_type,
            interval_value=interval_value,
            last_created=datetime.now()
        )
        
        self.recurring_quests.append(recurring)
        return recurring
    
    async def check_deadlines(self):
        """Check for expired quests and send warnings"""
        current_time = datetime.now()
        
        for quest_id, deadline_info in self.active_deadlines.items():
            if deadline_info.expired:
                continue
            
            time_remaining = deadline_info.deadline - current_time
            
            # Send warning 1 hour before deadline
            if time_remaining <= timedelta(hours=1) and not deadline_info.warning_sent:
                await self._send_deadline_warning(quest_id, time_remaining)
                deadline_info.warning_sent = True
            
            # Expire quest if deadline passed
            if time_remaining <= timedelta(0):
                await self._expire_quest(quest_id)
                deadline_info.expired = True
    
    async def check_recurring_quests(self):
        """Check and create recurring quests"""
        current_time = datetime.now()
        
        for recurring in self.recurring_quests:
            if not recurring.is_active:
                continue
            
            if not recurring.last_created:
                continue
            
            # Calculate next creation time
            if recurring.interval_type == "daily":
                next_creation = recurring.last_created + timedelta(days=recurring.interval_value)
            elif recurring.interval_type == "weekly":
                next_creation = recurring.last_created + timedelta(weeks=recurring.interval_value)
            elif recurring.interval_type == "monthly":
                next_creation = recurring.last_created + timedelta(days=30 * recurring.interval_value)
            else:
                continue
            
            if current_time >= next_creation:
                await self._create_recurring_quest_instance(recurring)
                recurring.last_created = current_time
    
    async def start_scheduler(self):
        """Start the background scheduler"""
        self.scheduler_running = True
        while self.scheduler_running:
            await self.check_deadlines()
            await self.check_recurring_quests()
            await asyncio.sleep(300)  # Check every 5 minutes
    
    async def stop_scheduler(self):
        """Stop the background scheduler"""
        self.scheduler_running = False
    
    async def _send_deadline_warning(self, quest_id: str, time_remaining: timedelta):
        """Send deadline warning (implement with your notification system)"""
        hours = int(time_remaining.total_seconds() / 3600)
        minutes = int((time_remaining.total_seconds() % 3600) / 60)
        print(f"Warning: Quest {quest_id} expires in {hours}h {minutes}m!")
    
    async def _expire_quest(self, quest_id: str):
        """Mark quest as expired"""
        quest = await self.quest_manager.get_quest(quest_id)
        if quest:
            quest.status = QuestStatus.CANCELLED
            await self.quest_manager.database.save_quest(quest)
            print(f"Quest {quest_id} has expired!")
    
    async def _create_recurring_quest_instance(self, recurring: RecurringQuest):
        """Create a new instance of a recurring quest"""
        # This would create a new quest based on the template
        print(f"Creating recurring quest instance for template {recurring.template_id}")
