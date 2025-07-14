
from typing import List, Dict, Optional
from dataclasses import dataclass
from bot.models import QuestRank, QuestCategory

@dataclass
class QuestTemplate:
    """Quest template data model"""
    template_id: str
    name: str
    description_template: str
    requirements_template: str
    reward_template: str
    rank: str
    category: str
    placeholders: List[str]  # List of placeholder variables like {target}, {amount}
    
    @property
    def title(self) -> str:
        """Get template title"""
        return self.name
    
    @property
    def description(self) -> str:
        """Get template description"""
        return self.description_template
    
    @property
    def requirements(self) -> str:
        """Get template requirements"""
        return self.requirements_template
    
    @property
    def reward(self) -> str:
        """Get template reward"""
        return self.reward_template
    
class QuestTemplateManager:
    """Manages quest templates"""
    
    def __init__(self):
        self.templates = self._load_default_templates()
    
    def _load_default_templates(self) -> Dict[str, QuestTemplate]:
        """Load default quest templates"""
        templates = {
            "hunting_basic": QuestTemplate(
                template_id="hunting_basic",
                name="Hunting Adventure",
                description_template="Embark on a hunting quest to defeat various creatures and prove your combat prowess.",
                requirements_template="Defeat 10 monsters\nLocation: Any hunting ground\nProof: Screenshot of defeated enemies",
                reward_template="50 Gold Coins",
                rank=QuestRank.EASY,
                category=QuestCategory.HUNTING,
                placeholders=["target", "amount", "location", "reward_amount", "reward_type"]
            ),
            "gathering_basic": QuestTemplate(
                template_id="gathering_basic",
                name="Gathering Materials",
                description_template="Collect valuable resources from the world to support your community.",
                requirements_template="Gather 20 resources\nLocation: Any resource node\nQuality: Standard or better",
                reward_template="25 Gold Coins",
                rank=QuestRank.NORMAL,
                category=QuestCategory.GATHERING,
                placeholders=["resource", "amount", "location", "quality", "reward_amount", "reward_type"]
            ),
            "combat_basic": QuestTemplate(
                template_id="combat_basic",
                name="Combat Challenge",
                description_template="Test your fighting skills in intense combat scenarios.",
                requirements_template="Win 5 combat encounters\nLocation: Arena or combat zone\nProof: Victory screenshots",
                reward_template="100 Gold Coins",
                rank=QuestRank.MEDIUM,
                category=QuestCategory.COMBAT,
                placeholders=["encounters", "location", "reward_amount"]
            ),
            "social_basic": QuestTemplate(
                template_id="social_basic",
                name="Social Event",
                description_template="Participate in community activities and build relationships with fellow adventurers.",
                requirements_template="Participate in 3 social events\nDuration: This week\nProof: Event participation screenshots",
                reward_template="Social Recognition Badge",
                rank=QuestRank.EASY,
                category=QuestCategory.SOCIAL,
                placeholders=["events", "duration", "reward"]
            ),
            "exploration_basic": QuestTemplate(
                template_id="exploration_basic",
                name="Exploration Mission",
                description_template="Venture into uncharted territories and discover new locations.",
                requirements_template="Explore 5 new locations\nDocument findings\nProof: Screenshots with coordinates",
                reward_template="Explorer's Map",
                rank=QuestRank.NORMAL,
                category=QuestCategory.EXPLORATION,
                placeholders=["locations", "findings", "reward"]
            ),
            "building_basic": QuestTemplate(
                template_id="building_basic",
                name="Building Project",
                description_template="Construct structures that will benefit the community.",
                requirements_template="Build 1 community structure\nMaterials: Player provided\nProof: Before and after screenshots",
                reward_template="Builder's Tools",
                rank=QuestRank.MEDIUM,
                category=QuestCategory.BUILDING,
                placeholders=["structure", "materials", "reward"]
            ),
            "trading_basic": QuestTemplate(
                template_id="trading_basic",
                name="Trading Quest",
                description_template="Engage in commerce and establish profitable trade relationships.",
                requirements_template="Complete 10 trade transactions\nProfit margin: Positive\nProof: Transaction logs",
                reward_template="Merchant's License",
                rank=QuestRank.NORMAL,
                category=QuestCategory.TRADING,
                placeholders=["transactions", "profit", "reward"]
            ),
            "puzzle_basic": QuestTemplate(
                template_id="puzzle_basic",
                name="Puzzle Challenge",
                description_template="Solve complex puzzles that test your intellect and problem-solving skills.",
                requirements_template="Solve 3 logic puzzles\nTime limit: 2 hours\nProof: Solution screenshots",
                reward_template="Wisdom Scroll",
                rank=QuestRank.HARD,
                category=QuestCategory.PUZZLE,
                placeholders=["puzzles", "time_limit", "reward"]
            )
        }
        return templates
    
    def get_template(self, template_id: str) -> Optional[QuestTemplate]:
        """Get a specific template"""
        return self.templates.get(template_id)
    
    def get_all_templates(self) -> List[QuestTemplate]:
        """Get all available templates"""
        return list(self.templates.values())
    
    def get_templates_by_category(self, category: str) -> List[QuestTemplate]:
        """Get templates by category"""
        return [t for t in self.templates.values() if t.category == category]
    
    def apply_template(self, template_id: str, values: Dict[str, str]) -> Dict[str, str]:
        """Apply values to a template and return formatted quest data"""
        template = self.get_template(template_id)
        if not template:
            return {}
        
        # Replace placeholders in templates
        description = template.description_template
        requirements = template.requirements_template
        reward = template.reward_template
        
        for placeholder, value in values.items():
            placeholder_key = "{" + placeholder + "}"
            description = description.replace(placeholder_key, value)
            requirements = requirements.replace(placeholder_key, value)
            reward = reward.replace(placeholder_key, value)
        
        return {
            "description": description,
            "requirements": requirements,
            "reward": reward,
            "rank": template.rank,
            "category": template.category
        }
