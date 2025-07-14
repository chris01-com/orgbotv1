
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List
from datetime import datetime

from bot.models import QuestRank, QuestCategory, QuestStatus
from bot.quest_manager import QuestManager
from bot.config import ChannelConfig
from bot.user_stats import UserStatsManager
from bot.permissions import has_quest_creation_permission, can_manage_quest, user_has_required_roles


class QuestCommands(commands.Cog):
    """Quest command handlers"""

    def __init__(self, bot: commands.Bot, quest_manager: QuestManager,
                 channel_config: ChannelConfig,
                 user_stats_manager: UserStatsManager,
                 quest_templates=None,
                 quest_bookmarks=None,
                 quest_search=None,
                 quest_analytics=None):
        self.bot = bot
        self.quest_manager = quest_manager
        self.channel_config = channel_config
        self.user_stats_manager = user_stats_manager
        self.quest_templates = quest_templates
        self.quest_bookmarks = quest_bookmarks
        self.quest_search = quest_search
        self.quest_analytics = quest_analytics

    def _get_rank_color(self, rank: str) -> discord.Color:
        """Get color based on quest rank"""
        colors = {
            QuestRank.EASY: discord.Color.green(),
            QuestRank.NORMAL: discord.Color.blue(),
            QuestRank.MEDIUM: discord.Color.orange(),
            QuestRank.HARD: discord.Color.red(),
            QuestRank.IMPOSSIBLE: discord.Color.purple()
        }
        return colors.get(rank, discord.Color.light_grey())

    def _get_status_color(self, status: str) -> discord.Color:
        """Get color based on quest status"""
        colors = {
            QuestStatus.AVAILABLE: discord.Color.green(),
            QuestStatus.ACCEPTED: discord.Color.yellow(),
            QuestStatus.COMPLETED: discord.Color.orange(),
            QuestStatus.APPROVED: discord.Color.blue(),
            QuestStatus.REJECTED: discord.Color.red(),
            QuestStatus.CANCELLED: discord.Color.dark_grey()
        }
        return colors.get(status, discord.Color.light_grey())

    @app_commands.command(name="setup_channels", description="Setup quest channels for the server")
    @app_commands.describe(
        quest_list_channel="Channel for quest listings",
        quest_accept_channel="Channel for quest acceptance",
        quest_submit_channel="Channel for quest submissions",
        quest_approval_channel="Channel for quest approvals",
        notification_channel="Channel for notifications"
    )
    async def setup_channels(self, interaction: discord.Interaction,
                             quest_list_channel: discord.TextChannel,
                             quest_accept_channel: discord.TextChannel,
                             quest_submit_channel: discord.TextChannel,
                             quest_approval_channel: discord.TextChannel,
                             notification_channel: discord.TextChannel):
        """Setup quest channels for the server"""
        if not has_quest_creation_permission(interaction.user, interaction.guild):
            await interaction.response.send_message("You don't have permission to setup channels!", ephemeral=True)
            return

        embed = discord.Embed(
            title="Channel Configuration Complete",
            description="Quest channels have been successfully configured for this server.",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Quest List Channel",
            value=f"{quest_list_channel.mention}\nNew quests will be posted here",
            inline=False
        )
        embed.add_field(
            name="Quest Accept Channel",
            value=f"{quest_accept_channel.mention}\nUse this channel to accept quests",
            inline=False
        )
        embed.add_field(
            name="Quest Submit Channel",
            value=f"{quest_submit_channel.mention}\nSubmit completed quests here",
            inline=False
        )
        embed.add_field(
            name="Quest Approval Channel",
            value=f"{quest_approval_channel.mention}\nQuest approvals will be processed here",
            inline=False
        )
        embed.add_field(
            name="Notification Channel",
            value=f"{notification_channel.mention}\nGeneral quest notifications will appear here",
            inline=False
        )

        embed.set_footer(text=f"Configured by {interaction.user.display_name}")
        embed.timestamp = datetime.now()

        await interaction.response.send_message(embed=embed)

        # Set channels in database after responding
        await self.channel_config.set_guild_channels(
            interaction.guild.id,
            quest_list_channel.id,
            quest_accept_channel.id,
            quest_submit_channel.id,
            quest_approval_channel.id,
            notification_channel.id
        )

    @app_commands.command(name="create_quest", description="Create a new quest")
    @app_commands.describe(
        title="Quest title",
        description="Quest description",
        rank="Quest difficulty rank",
        category="Quest category",
        requirements="Quest requirements",
        reward="Quest reward",
        required_roles="Required roles (mention roles or use role names separated by commas)"
    )
    @app_commands.choices(rank=[
        app_commands.Choice(name="Easy", value=QuestRank.EASY),
        app_commands.Choice(name="Normal", value=QuestRank.NORMAL),
        app_commands.Choice(name="Medium", value=QuestRank.MEDIUM),
        app_commands.Choice(name="Hard", value=QuestRank.HARD),
        app_commands.Choice(name="Impossible", value=QuestRank.IMPOSSIBLE)
    ])
    @app_commands.choices(category=[
        app_commands.Choice(name="Hunting", value=QuestCategory.HUNTING),
        app_commands.Choice(name="Gathering", value=QuestCategory.GATHERING),
        app_commands.Choice(name="Collecting", value=QuestCategory.COLLECTING),
        app_commands.Choice(name="Crafting", value=QuestCategory.CRAFTING),
        app_commands.Choice(name="Exploration", value=QuestCategory.EXPLORATION),
        app_commands.Choice(name="Combat", value=QuestCategory.COMBAT),
        app_commands.Choice(name="Social", value=QuestCategory.SOCIAL),
        app_commands.Choice(name="Building", value=QuestCategory.BUILDING),
        app_commands.Choice(name="Trading", value=QuestCategory.TRADING),
        app_commands.Choice(name="Puzzle", value=QuestCategory.PUZZLE),
        app_commands.Choice(name="Survival", value=QuestCategory.SURVIVAL),
        app_commands.Choice(name="Other", value=QuestCategory.OTHER)
    ])
    async def create_quest(self,
                           interaction: discord.Interaction,
                           title: str,
                           description: str,
                           rank: str = QuestRank.NORMAL,
                           category: str = QuestCategory.OTHER,
                           requirements: str = "",
                           reward: str = "",
                           required_roles: str = ""):
        """Create a new quest"""
        if not has_quest_creation_permission(interaction.user, interaction.guild):
            await interaction.response.send_message("You don't have permission to create quests!", ephemeral=True)
            return

        await interaction.response.defer()

        # Parse required roles
        required_role_ids = []
        if required_roles:
            import re
            # Extract role IDs from mentions
            role_mention_pattern = r'<@&(\d+)>'
            role_ids = re.findall(role_mention_pattern, required_roles)
            for role_id in role_ids:
                role = interaction.guild.get_role(int(role_id))
                if role:
                    required_role_ids.append(role.id)

            # If no mentions found, try parsing as role names
            if not required_role_ids:
                role_names = [name.strip() for name in required_roles.split(',')]
                for role_name in role_names:
                    role = discord.utils.get(interaction.guild.roles, name=role_name)
                    if role:
                        required_role_ids.append(role.id)

        quest = await self.quest_manager.create_quest(
            title=title,
            description=description,
            creator_id=interaction.user.id,
            guild_id=interaction.guild.id,
            requirements=requirements,
            reward=reward,
            rank=rank,
            category=category,
            required_role_ids=required_role_ids
        )

        # Create beautiful quest embed for quest list channel
        public_embed = discord.Embed(
            title="NEW QUEST AVAILABLE",
            description=f"**{quest.title}**",
            color=self._get_rank_color(quest.rank)
        )
        
        public_embed.add_field(
            name="■ Description",
            value=f"```\n{quest.description}\n```",
            inline=False
        )
        
        # Quest info section with better formatting
        quest_info = f"**Quest ID:** `{quest.quest_id}`\n**Difficulty:** {quest.rank.title()}\n**Category:** {quest.category.title()}"
        public_embed.add_field(
            name="■ Quest Information",
            value=quest_info,
            inline=True
        )
        
        # Status indicator
        public_embed.add_field(
            name="■ Status",
            value=f"**{quest.status.title()}**\n*Ready to Accept*",
            inline=True
        )
        
        # Empty field for spacing
        public_embed.add_field(name="\u200b", value="\u200b", inline=True)
        
        if quest.requirements:
            public_embed.add_field(
                name="■ Requirements",
                value=f"```yaml\n{quest.requirements}\n```",
                inline=False
            )
        
        if quest.reward:
            public_embed.add_field(
                name="■ Reward",
                value=f"```yaml\n{quest.reward}\n```",
                inline=False
            )
        
        if quest.required_role_ids:
            role_mentions = []
            for role_id in quest.required_role_ids:
                role = interaction.guild.get_role(role_id)
                if role:
                    role_mentions.append(role.mention)
            if role_mentions:
                public_embed.add_field(
                    name="■ Required Roles",
                    value=" ".join(role_mentions),
                    inline=False
                )
        
        # Add acceptance instructions
        accept_channel = await self.channel_config.get_quest_accept_channel(interaction.guild.id)
        if accept_channel:
            public_embed.add_field(
                name="■ How to Accept This Quest",
                value=f"Use `/accept_quest {quest.quest_id}` in <#{accept_channel}>",
                inline=False
            )
        else:
            public_embed.add_field(
                name="■ How to Accept This Quest",
                value=f"Use `/accept_quest {quest.quest_id}` in any channel",
                inline=False
            )
        
        public_embed.set_author(
            name=f"Quest Creator: {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None
        )
        
        public_embed.set_footer(
            text=f"Quest ID: {quest.quest_id} • Created {quest.created_at.strftime('%B %d, %Y at %I:%M %p')}",
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        public_embed.timestamp = quest.created_at

        # Create private response embed
        private_embed = discord.Embed(
            title="Quest Creation Complete",
            description=f"Your quest **{quest.title}** has been successfully created and posted.",
            color=self._get_rank_color(quest.rank)
        )
        private_embed.add_field(name="Quest ID", value=f"`{quest.quest_id}`", inline=True)
        private_embed.add_field(name="Difficulty", value=quest.rank.title(), inline=True)
        private_embed.add_field(name="Category", value=quest.category.title(), inline=True)
        private_embed.set_footer(text="Your quest is now live and ready for adventurers to accept.")

        await interaction.followup.send(embed=private_embed)

        # Send to quest list channel
        quest_list_channel_id = await self.channel_config.get_quest_list_channel(interaction.guild.id)
        if quest_list_channel_id:
            quest_list_channel = interaction.guild.get_channel(quest_list_channel_id)
            if quest_list_channel:
                await quest_list_channel.send(embed=public_embed)

    @app_commands.command(name="list_quests", description="List all available quests")
    @app_commands.describe(
        rank_filter="Filter by quest rank",
        category_filter="Filter by quest category",
        show_all="Show all quests including completed ones"
    )
    @app_commands.choices(rank_filter=[
        app_commands.Choice(name="Easy", value=QuestRank.EASY),
        app_commands.Choice(name="Normal", value=QuestRank.NORMAL),
        app_commands.Choice(name="Medium", value=QuestRank.MEDIUM),
        app_commands.Choice(name="Hard", value=QuestRank.HARD),
        app_commands.Choice(name="Impossible", value=QuestRank.IMPOSSIBLE)
    ])
    @app_commands.choices(category_filter=[
        app_commands.Choice(name="Hunting", value=QuestCategory.HUNTING),
        app_commands.Choice(name="Gathering", value=QuestCategory.GATHERING),
        app_commands.Choice(name="Collecting", value=QuestCategory.COLLECTING),
        app_commands.Choice(name="Crafting", value=QuestCategory.CRAFTING),
        app_commands.Choice(name="Exploration", value=QuestCategory.EXPLORATION),
        app_commands.Choice(name="Combat", value=QuestCategory.COMBAT),
        app_commands.Choice(name="Social", value=QuestCategory.SOCIAL),
        app_commands.Choice(name="Building", value=QuestCategory.BUILDING),
        app_commands.Choice(name="Trading", value=QuestCategory.TRADING),
        app_commands.Choice(name="Puzzle", value=QuestCategory.PUZZLE),
        app_commands.Choice(name="Survival", value=QuestCategory.SURVIVAL),
        app_commands.Choice(name="Other", value=QuestCategory.OTHER)
    ])
    async def list_quests(self,
                          interaction: discord.Interaction,
                          rank_filter: str = None,
                          category_filter: str = None,
                          show_all: bool = False):
        """List all available quests"""
        await interaction.response.defer()

        # Get quests
        if show_all:
            quests = await self.quest_manager.get_guild_quests(interaction.guild.id)
        else:
            quests = await self.quest_manager.get_available_quests(interaction.guild.id)

        # Apply filters
        if rank_filter:
            quests = [q for q in quests if q.rank == rank_filter]
        if category_filter:
            quests = [q for q in quests if q.category == category_filter]

        if not quests:
            embed = discord.Embed(
                title="No Quests Available",
                description="No quests match your current filters. Try adjusting your search criteria or check back later for new adventures.",
                color=discord.Color.light_grey()
            )
            embed.add_field(
                name="Suggestions",
                value="• Remove filters to see all quests\n• Try different difficulty or category filters\n• Check back later for new quests",
                inline=False
            )
            await interaction.followup.send(embed=embed)
            return

        # Create paginated quest list
        embed = discord.Embed(
            title=f"Quest Board - {interaction.guild.name}",
            description=f"**{len(quests)}** quest{'s' if len(quests) != 1 else ''} found",
            color=discord.Color.blue()
        )

        # Add filter info with better formatting
        filter_info = []
        if rank_filter:
            filter_info.append(f"**Difficulty:** {rank_filter.title()}")
        if category_filter:
            filter_info.append(f"**Category:** {category_filter.title()}")
        if show_all:
            filter_info.append("**Scope:** All Quests")
        else:
            filter_info.append("**Scope:** Available Only")

        if filter_info:
            embed.add_field(
                name="■ Active Filters",
                value=" • ".join(filter_info),
                inline=False
            )

        # Add quests (limit to 10 for readability)
        for i, quest in enumerate(quests[:10]):
            creator = interaction.guild.get_member(quest.creator_id)
            creator_name = creator.display_name if creator else "Unknown User"
            
            # Status indicator without emojis
            status_text = quest.status.title()
            
            quest_info = f"**Difficulty:** {quest.rank.title()}\n**Category:** {quest.category.title()}\n**Creator:** {creator_name}\n**Status:** {status_text}"
            
            if quest.reward:
                reward_preview = quest.reward[:40] + '...' if len(quest.reward) > 40 else quest.reward
                quest_info += f"\n**Reward:** {reward_preview}"

            embed.add_field(
                name=f"■ {quest.title}",
                value=f"```yaml\nID: {quest.quest_id}\n```{quest_info}",
                inline=True
            )

        if len(quests) > 10:
            embed.add_field(
                name="■ Additional Information",
                value=f"Showing first 10 of {len(quests)} quests. Use filters to narrow down results.",
                inline=False
            )

        embed.set_footer(text="Use /quest_info <quest_id> to view detailed information • Use /accept_quest <quest_id> to accept a quest")
        embed.timestamp = datetime.now()

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="quest_info", description="Get detailed information about a specific quest")
    @app_commands.describe(quest_id="The ID of the quest")
    async def quest_info(self, interaction: discord.Interaction, quest_id: str):
        """Get detailed information about a specific quest"""
        quest = await self.quest_manager.get_quest(quest_id)
        
        if not quest:
            await interaction.response.send_message("Quest not found!", ephemeral=True)
            return

        # Check if quest is from the same guild
        if quest.guild_id != interaction.guild.id:
            await interaction.response.send_message("Quest not found in this server!", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Quest Details: {quest.title}",
            description=f"```\n{quest.description}\n```",
            color=self._get_rank_color(quest.rank)
        )

        # Quest information in a structured format
        quest_details = f"**Quest ID:** `{quest.quest_id}`\n**Difficulty:** {quest.rank.title()}\n**Category:** {quest.category.title()}"
        embed.add_field(
            name="■ Quest Information",
            value=quest_details,
            inline=True
        )

        # Status information
        status_color = self._get_status_color(quest.status)
        embed.add_field(
            name="■ Status",
            value=f"**{quest.status.title()}**",
            inline=True
        )

        # Creator info
        creator = interaction.guild.get_member(quest.creator_id)
        creator_name = creator.display_name if creator else "Unknown User"
        embed.add_field(
            name="■ Quest Creator",
            value=f"**{creator_name}**\n*Created {quest.created_at.strftime('%B %d, %Y')}*",
            inline=True
        )

        if quest.requirements:
            embed.add_field(
                name="■ Requirements",
                value=f"```yaml\n{quest.requirements}\n```",
                inline=False
            )

        if quest.reward:
            embed.add_field(
                name="■ Reward",
                value=f"```yaml\n{quest.reward}\n```",
                inline=False
            )

        if quest.required_role_ids:
            role_mentions = []
            for role_id in quest.required_role_ids:
                role = interaction.guild.get_role(role_id)
                if role:
                    role_mentions.append(role.mention)
            if role_mentions:
                embed.add_field(
                    name="■ Required Roles",
                    value=" ".join(role_mentions),
                    inline=False
                )

        # Add acceptance info if quest is available
        if quest.status == QuestStatus.AVAILABLE:
            accept_channel = await self.channel_config.get_quest_accept_channel(interaction.guild.id)
            if accept_channel:
                embed.add_field(
                    name="How to Accept",
                    value=f"Use `/accept_quest {quest.quest_id}` in <#{accept_channel}>",
                    inline=False
                )

        embed.set_footer(text=f"Quest ID: {quest.quest_id}")
        embed.timestamp = quest.created_at

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="accept_quest", description="Accept a quest")
    @app_commands.describe(quest_id="The ID of the quest to accept")
    async def accept_quest(self, interaction: discord.Interaction, quest_id: str):
        """Accept a quest"""
        user_role_ids = [role.id for role in interaction.user.roles]
        
        progress, error = await self.quest_manager.accept_quest(
            quest_id, 
            interaction.user.id, 
            user_role_ids, 
            interaction.channel.id
        )
        
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return
        
        quest = await self.quest_manager.get_quest(quest_id)
        if not quest:
            await interaction.response.send_message("Quest not found!", ephemeral=True)
            return

        # Update user stats
        await self.user_stats_manager.update_quest_accepted(interaction.user.id, interaction.guild.id)
        
        embed = discord.Embed(
            title="Quest Accepted Successfully",
            description=f"You have embarked on the quest **{quest.title}**",
            color=self._get_rank_color(quest.rank)
        )
        
        # Quest details section
        quest_details = f"**Quest ID:** `{quest.quest_id}`\n**Difficulty:** {quest.rank.title()}\n**Category:** {quest.category.title()}"
        embed.add_field(
            name="■ Quest Information",
            value=quest_details,
            inline=True
        )
        
        # Acceptance info
        embed.add_field(
            name="■ Accepted",
            value=f"**{progress.accepted_at.strftime('%B %d, %Y')}**\n*{progress.accepted_at.strftime('%I:%M %p')}*",
            inline=True
        )
        
        # Status
        embed.add_field(
            name="■ Status",
            value="**In Progress**\n*Quest Active*",
            inline=True
        )
        
        if quest.requirements:
            embed.add_field(
                name="■ Requirements to Complete",
                value=f"```yaml\n{quest.requirements}\n```",
                inline=False
            )
        
        if quest.reward:
            embed.add_field(
                name="■ Reward Upon Completion",
                value=f"```yaml\n{quest.reward}\n```",
                inline=False
            )
        
        # Add submission info
        submit_channel = await self.channel_config.get_quest_submit_channel(interaction.guild.id)
        if submit_channel:
            embed.add_field(
                name="■ Next Steps",
                value=f"Complete the quest requirements and use `/submit_quest {quest.quest_id}` in <#{submit_channel}> to submit your proof.",
                inline=False
            )
        else:
            embed.add_field(
                name="■ Next Steps",
                value=f"Complete the quest requirements and use `/submit_quest {quest.quest_id}` to submit your proof.",
                inline=False
            )
        
        embed.set_footer(text=f"Quest ID: {quest.quest_id} • Good luck on your adventure!")
        embed.timestamp = progress.accepted_at

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="submit_quest", description="Submit a completed quest")
    @app_commands.describe(
        quest_id="The ID of the quest to submit",
        proof_text="Description of your proof",
        proof_image1="Image proof 1",
        proof_image2="Image proof 2",
        proof_image3="Image proof 3",
        proof_image4="Image proof 4",
        proof_image5="Image proof 5",
        proof_image6="Image proof 6",
        proof_image7="Image proof 7",
        proof_image8="Image proof 8",
        proof_image9="Image proof 9",
        proof_image10="Image proof 10",
        proof_image11="Image proof 11",
        proof_image12="Image proof 12",
        proof_image13="Image proof 13",
        proof_image14="Image proof 14",
        proof_image15="Image proof 15"
    )
    async def submit_quest(self,
                          interaction: discord.Interaction,
                          quest_id: str,
                          proof_text: str,
                          proof_image1: discord.Attachment = None,
                          proof_image2: discord.Attachment = None,
                          proof_image3: discord.Attachment = None,
                          proof_image4: discord.Attachment = None,
                          proof_image5: discord.Attachment = None,
                          proof_image6: discord.Attachment = None,
                          proof_image7: discord.Attachment = None,
                          proof_image8: discord.Attachment = None,
                          proof_image9: discord.Attachment = None,
                          proof_image10: discord.Attachment = None,
                          proof_image11: discord.Attachment = None,
                          proof_image12: discord.Attachment = None,
                          proof_image13: discord.Attachment = None,
                          proof_image14: discord.Attachment = None,
                          proof_image15: discord.Attachment = None):
        """Submit a completed quest"""
        # Check if in correct channel
        quest_submit_channel_id = await self.channel_config.get_quest_submit_channel(interaction.guild.id)
        if quest_submit_channel_id and interaction.channel.id != quest_submit_channel_id:
            submit_channel = interaction.guild.get_channel(quest_submit_channel_id)
            if submit_channel:
                await interaction.response.send_message(
                    f"Please use {submit_channel.mention} to submit quest completions!",
                    ephemeral=True
                )
                return

        # Collect all proof images
        proof_images = [proof_image1, proof_image2, proof_image3, proof_image4, proof_image5,
                       proof_image6, proof_image7, proof_image8, proof_image9, proof_image10,
                       proof_image11, proof_image12, proof_image13, proof_image14, proof_image15]
        proof_image_urls = []

        for image in proof_images:
            if image:
                proof_image_urls.append(image.url)
        
        progress = await self.quest_manager.complete_quest(
            quest_id, 
            interaction.user.id, 
            proof_text, 
            proof_image_urls
        )
        
        if not progress:
            await interaction.response.send_message("Quest not found or not in accepted state!", ephemeral=True)
            return
        
        quest = await self.quest_manager.get_quest(quest_id)
        if not quest:
            await interaction.response.send_message("Quest not found!", ephemeral=True)
            return

        embed = discord.Embed(
            title="Quest Submitted Successfully",
            description=f"Your completion of **{quest.title}** has been submitted for approval.",
            color=discord.Color.orange()
        )
        
        # Quest details section
        quest_details = f"**Quest ID:** `{quest.quest_id}`\n**Difficulty:** {quest.rank.title()}\n**Category:** {quest.category.title()}"
        embed.add_field(
            name="■ Quest Information",
            value=quest_details,
            inline=True
        )
        
        # Submission info
        embed.add_field(
            name="■ Submitted",
            value=f"**{progress.completed_at.strftime('%B %d, %Y')}**\n*{progress.completed_at.strftime('%I:%M %p')}*",
            inline=True
        )
        
        # Status
        embed.add_field(
            name="■ Status",
            value="**Pending Approval**\n*Awaiting Review*",
            inline=True
        )
        
        # Proof section
        embed.add_field(
            name="■ Proof of Completion",
            value=f"```\n{proof_text[:1000] if len(proof_text) > 1000 else proof_text}\n```",
            inline=False
        )
        
        if proof_image_urls:
            embed.add_field(
                name="■ Images Submitted",
                value=f"{len(proof_image_urls)} image(s) uploaded",
                inline=True
            )
            embed.set_image(url=proof_image_urls[0])
        
        # Next steps
        embed.add_field(
            name="■ What Happens Next",
            value="Your submission is now pending approval from the quest creator. You will be notified once it's reviewed and approved or if additional information is needed.",
            inline=False
        )
        
        embed.set_footer(text=f"Quest ID: {quest.quest_id} • Submission received and queued for review")
        embed.timestamp = progress.completed_at

        await interaction.response.send_message(embed=embed)

        # Send to approval channel and ping quest creator
        approval_channel_id = await self.channel_config.get_quest_approval_channel(interaction.guild.id)
        if approval_channel_id:
            approval_channel = interaction.guild.get_channel(approval_channel_id)
            creator = interaction.guild.get_member(quest.creator_id)
            
            if approval_channel:
                approval_embed = discord.Embed(
                    title="Quest Submission Pending Approval",
                    description=f"**{interaction.user.display_name}** has submitted proof for quest **{quest.title}**",
                    color=discord.Color.orange()
                )
                
                approval_embed.add_field(
                    name="■ Quest Details",
                    value=f"**ID:** `{quest.quest_id}`\n**Rank:** {quest.rank.title()}\n**Category:** {quest.category.title()}",
                    inline=True
                )
                
                approval_embed.add_field(
                    name="■ Submitter",
                    value=f"{interaction.user.mention}\n**User ID:** {interaction.user.id}",
                    inline=True
                )
                
                approval_embed.add_field(
                    name="■ Submitted",
                    value=f"<t:{int(progress.completed_at.timestamp())}:f>",
                    inline=True
                )
                
                approval_embed.add_field(
                    name="■ Proof Text",
                    value=f"```\n{proof_text[:500]}{'...' if len(proof_text) > 500 else ''}\n```",
                    inline=False
                )
                
                if proof_image_urls:
                    approval_embed.add_field(
                        name="■ Images Submitted",
                        value=f"{len(proof_image_urls)} image(s) attached",
                        inline=True
                    )
                    approval_embed.set_image(url=proof_image_urls[0])
                
                approval_embed.add_field(
                    name="■ Actions",
                    value=f"Use `/approve_quest {quest.quest_id} {interaction.user.id}` or `/reject_quest {quest.quest_id} {interaction.user.id}`",
                    inline=False
                )
                
                approval_embed.set_footer(text=f"Quest ID: {quest.quest_id}")
                approval_embed.timestamp = progress.completed_at
                
                # Send with creator ping
                content = f"{creator.mention if creator else 'Quest Creator'} - New quest submission requires your approval!"
                await approval_channel.send(content=content, embed=approval_embed)
                
                # Send additional images if there are more than one
                if len(proof_image_urls) > 1:
                    additional_embed = discord.Embed(
                        title="Additional Proof Images",
                        description=f"Additional images for quest `{quest_id}` by {interaction.user.display_name}",
                        color=discord.Color.blue()
                    )
                    for i, url in enumerate(proof_image_urls[1:], 2):
                        additional_embed.add_field(name=f"Image {i}", value=f"[View Image]({url})", inline=True)
                    
                    await approval_channel.send(embed=additional_embed)

    @app_commands.command(name="approve_quest", description="Approve a completed quest")
    @app_commands.describe(
        quest_id="The ID of the quest to approve",
        user="The user who completed the quest"
    )
    async def approve_quest(self, interaction: discord.Interaction, quest_id: str, user: discord.Member):
        """Approve a completed quest"""
        quest = await self.quest_manager.get_quest(quest_id)
        if not quest:
            await interaction.response.send_message("Quest not found!", ephemeral=True)
            return
        
        if not can_manage_quest(interaction.user, interaction.guild, quest.creator_id):
            await interaction.response.send_message("You don't have permission to approve this quest!", ephemeral=True)
            return
        
        progress = await self.quest_manager.approve_quest(quest_id, user.id, True)
        if not progress:
            await interaction.response.send_message("Quest not found or not in completed state!", ephemeral=True)
            return
        
        # Update user stats
        await self.user_stats_manager.update_quest_completed(user.id, interaction.guild.id)
        
        embed = discord.Embed(
            title="Quest Approved",
            description=f"Quest **{quest.title}** completed by {user.mention} has been approved.",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Quest Details",
            value=f"**ID:** `{quest.quest_id}`\n**Rank:** {quest.rank.title()}\n**Category:** {quest.category.title()}",
            inline=True
        )
        
        embed.add_field(
            name="Approved By",
            value=interaction.user.mention,
            inline=True
        )
        
        embed.add_field(
            name="Approved On",
            value=datetime.now().strftime("%B %d, %Y at %I:%M %p"),
            inline=True
        )
        
        if quest.reward:
            embed.add_field(
                name="Reward",
                value=f"```\n{quest.reward}\n```",
                inline=False
            )
        
        embed.set_footer(text=f"Quest ID: {quest.quest_id}")
        embed.timestamp = datetime.now()

        await interaction.response.send_message(embed=embed)
        
        # Notify the user in quest accept channel
        quest_accept_channel_id = await self.channel_config.get_quest_accept_channel(interaction.guild.id)
        quest_accept_channel = interaction.guild.get_channel(quest_accept_channel_id) if quest_accept_channel_id else None
        
        user_embed = discord.Embed(
            title="🎉 Quest Approved!",
            description=f"Congratulations! Your completion of **{quest.title}** has been approved!",
            color=discord.Color.green()
        )
        
        user_embed.add_field(
            name="■ Quest Details",
            value=f"**ID:** `{quest.quest_id}`\n**Rank:** {quest.rank.title()}\n**Category:** {quest.category.title()}",
            inline=True
        )
        
        user_embed.add_field(
            name="■ Approved By",
            value=f"{interaction.user.mention}\n**{interaction.user.display_name}**",
            inline=True
        )
        
        user_embed.add_field(
            name="■ Approved On",
            value=f"<t:{int(datetime.now().timestamp())}:f>",
            inline=True
        )
        
        if quest.reward:
            user_embed.add_field(
                name="■ Your Reward",
                value=f"```yaml\n{quest.reward}\n```",
                inline=False
            )
        
        user_embed.add_field(
            name="■ Congratulations!",
            value="Well done on completing this quest! Your efforts have been recognized and rewarded.",
            inline=False
        )
        
        user_embed.set_footer(text=f"Quest ID: {quest.quest_id} • Keep up the great work!")
        user_embed.timestamp = datetime.now()
        
        if quest_accept_channel:
            await quest_accept_channel.send(content=f"{user.mention} 🎉", embed=user_embed)
        else:
            # Fallback to current channel if quest accept channel not set
            await interaction.followup.send(content=f"{user.mention} 🎉", embed=user_embed)

    @app_commands.command(name="reject_quest", description="Reject a completed quest")
    @app_commands.describe(
        quest_id="The ID of the quest to reject",
        user="The user who completed the quest"
    )
    async def reject_quest(self, interaction: discord.Interaction, quest_id: str, user: discord.Member):
        """Reject a completed quest"""
        quest = await self.quest_manager.get_quest(quest_id)
        if not quest:
            await interaction.response.send_message("Quest not found!", ephemeral=True)
            return
        
        if not can_manage_quest(interaction.user, interaction.guild, quest.creator_id):
            await interaction.response.send_message("You don't have permission to reject this quest!", ephemeral=True)
            return
        
        progress = await self.quest_manager.approve_quest(quest_id, user.id, False)
        if not progress:
            await interaction.response.send_message("Quest not found or not in completed state!", ephemeral=True)
            return
        
        # Update user stats
        await self.user_stats_manager.update_quest_rejected(user.id, interaction.guild.id)
        
        embed = discord.Embed(
            title="Quest Rejected",
            description=f"Quest **{quest.title}** completed by {user.mention} has been rejected.",
            color=discord.Color.red()
        )
        
        embed.add_field(
            name="Quest Details",
            value=f"**ID:** `{quest.quest_id}`\n**Rank:** {quest.rank.title()}\n**Category:** {quest.category.title()}",
            inline=True
        )
        
        embed.add_field(
            name="Rejected By",
            value=interaction.user.mention,
            inline=True
        )
        
        embed.add_field(
            name="Rejected On",
            value=datetime.now().strftime("%B %d, %Y at %I:%M %p"),
            inline=True
        )
        
        embed.add_field(
            name="Note",
            value="The user can attempt this quest again after 24 hours.",
            inline=False
        )
        
        embed.set_footer(text=f"Quest ID: {quest.quest_id}")
        embed.timestamp = datetime.now()

        await interaction.response.send_message(embed=embed)
        
        # Notify the user in quest accept channel
        quest_accept_channel_id = await self.channel_config.get_quest_accept_channel(interaction.guild.id)
        quest_accept_channel = interaction.guild.get_channel(quest_accept_channel_id) if quest_accept_channel_id else None
        
        user_embed = discord.Embed(
            title="❌ Quest Rejected",
            description=f"Your submission for **{quest.title}** has been rejected and requires revision.",
            color=discord.Color.red()
        )
        
        user_embed.add_field(
            name="■ Quest Details",
            value=f"**ID:** `{quest.quest_id}`\n**Rank:** {quest.rank.title()}\n**Category:** {quest.category.title()}",
            inline=True
        )
        
        user_embed.add_field(
            name="■ Rejected By",
            value=f"{interaction.user.mention}\n**{interaction.user.display_name}**",
            inline=True
        )
        
        user_embed.add_field(
            name="■ Rejected On",
            value=f"<t:{int(datetime.now().timestamp())}:f>",
            inline=True
        )
        
        user_embed.add_field(
            name="■ What's Next",
            value="• Review the quest requirements carefully\n• You can attempt this quest again after 24 hours\n• Make sure your proof meets all the specified criteria\n• Contact the quest creator if you need clarification",
            inline=False
        )
        
        user_embed.add_field(
            name="■ Don't Give Up!",
            value="Learning from feedback is part of the adventure. Use this as an opportunity to improve and try again!",
            inline=False
        )
        
        user_embed.set_footer(text=f"Quest ID: {quest.quest_id} • Try again in 24 hours")
        user_embed.timestamp = datetime.now()
        
        if quest_accept_channel:
            await quest_accept_channel.send(content=f"{user.mention} 📋", embed=user_embed)
        else:
            # Fallback to current channel if quest accept channel not set
            await interaction.followup.send(content=f"{user.mention} 📋", embed=user_embed)

    @app_commands.command(name="my_quests", description="View your quest progress")
    async def my_quests(self, interaction: discord.Interaction):
        """View user's quest progress"""
        user_quests = await self.quest_manager.get_user_quests(interaction.user.id, interaction.guild.id)
        
        if not user_quests:
            embed = discord.Embed(
                title="No Quest Activity",
                description="You haven't accepted any quests yet. Start your adventure by exploring available quests.",
                color=discord.Color.light_grey()
            )
            embed.add_field(
                name="Getting Started",
                value="• Use `/list_quests` to see available quests\n• Use `/quest_info <quest_id>` to view quest details\n• Use `/accept_quest <quest_id>` to begin your journey",
                inline=False
            )
            await interaction.response.send_message(embed=embed)
            return

        embed = discord.Embed(
            title=f"Quest Progress - {interaction.user.display_name}",
            description=f"Your adventure log in **{interaction.guild.name}**",
            color=discord.Color.blue()
        )

        # Group by status
        status_groups = {}
        for progress in user_quests:
            status = progress.status
            if status not in status_groups:
                status_groups[status] = []
            status_groups[status].append(progress)

        # Display each status group with better formatting
        for status, quests in status_groups.items():
            quest_list = []
            for progress in quests[:5]:  # Limit to 5 per status
                quest = await self.quest_manager.get_quest(progress.quest_id)
                if quest:
                    quest_list.append(f"• `{quest.quest_id}` **{quest.title}**")
            
            if quest_list:
                status_title = f"■ {status.title()} Quests"
                if len(quests) > 5:
                    status_title += f" ({len(quests)} total, showing first 5)"
                else:
                    status_title += f" ({len(quests)})"
                
                embed.add_field(
                    name=status_title,
                    value="\n".join(quest_list),
                    inline=False
                )

        # Add user stats with better formatting
        stats = await self.user_stats_manager.get_user_stats(interaction.user.id, interaction.guild.id)
        
        # Calculate success rate
        success_rate = 0
        if stats.quests_accepted > 0:
            success_rate = (stats.quests_completed / stats.quests_accepted) * 100
        
        stats_text = f"**Quests Completed:** {stats.quests_completed}\n**Quests Accepted:** {stats.quests_accepted}\n**Success Rate:** {success_rate:.1f}%\n**Rejected:** {stats.quests_rejected}"
        
        embed.add_field(
            name="■ Your Statistics",
            value=stats_text,
            inline=True
        )

        embed.set_footer(text="Use /quest_info <quest_id> to view details • Use /leaderboard to see server rankings")
        embed.timestamp = datetime.now()

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="View the quest leaderboard")
    @app_commands.describe(limit="Number of users to show (default: 10)")
    async def leaderboard(self, interaction: discord.Interaction, limit: int = 10):
        """View the quest leaderboard"""
        if limit > 25:
            limit = 25
        if limit < 1:
            limit = 10

        leaderboard = await self.user_stats_manager.get_guild_leaderboard(interaction.guild.id, limit)
        
        if not leaderboard:
            embed = discord.Embed(
                title="Leaderboard Empty",
                description="No quest activity found in this server yet. Be the first to complete a quest and claim the top spot!",
                color=discord.Color.light_grey()
            )
            embed.add_field(
                name="Start Your Journey",
                value="• Use `/list_quests` to see available quests\n• Complete quests to earn your place on the leaderboard\n• Compete with other adventurers for the top position",
                inline=False
            )
            await interaction.response.send_message(embed=embed)
            return

        embed = discord.Embed(
            title=f"Quest Leaderboard - {interaction.guild.name}",
            description=f"**Top {len(leaderboard)} Quest Champions**",
            color=discord.Color.gold()
        )

        leaderboard_text = ""
        for i, stats in enumerate(leaderboard, 1):
            user = interaction.guild.get_member(stats.user_id)
            username = user.display_name if user else "Unknown User"
            
            # Add ranking indicator for top 3
            if i == 1:
                rank_indicator = "**[CHAMPION]**"
            elif i == 2:
                rank_indicator = "**[ELITE]**"
            elif i == 3:
                rank_indicator = "**[VETERAN]**"
            else:
                rank_indicator = f"**#{i}**"
            
            completion_rate = 0
            if stats.quests_accepted > 0:
                completion_rate = (stats.quests_completed / stats.quests_accepted) * 100
            
            leaderboard_text += f"{rank_indicator} **{username}**\n"
            leaderboard_text += f"```yaml\nCompleted: {stats.quests_completed} | Success Rate: {completion_rate:.1f}%\n```"

        embed.add_field(
            name="■ Quest Champions",
            value=leaderboard_text,
            inline=False
        )

        # Add guild stats with better formatting
        guild_stats = await self.user_stats_manager.get_total_guild_stats(interaction.guild.id)
        stats_text = f"**Total Quests Created:** {guild_stats['total_quests']}\n**Total Completed:** {guild_stats['total_completed']}\n**Active Adventurers:** {guild_stats['active_users']}"
        
        embed.add_field(
            name="■ Server Statistics",
            value=stats_text,
            inline=True
        )

        embed.set_footer(text="Use /my_quests to see your personal progress • Rankings updated in real-time")
        embed.timestamp = datetime.now()

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="delete_quest", description="Delete a quest (quest creators only)")
    @app_commands.describe(quest_id="The ID of the quest to delete")
    async def delete_quest(self, interaction: discord.Interaction, quest_id: str):
        """Delete a quest"""
        quest = await self.quest_manager.get_quest(quest_id)
        if not quest:
            await interaction.response.send_message("Quest not found!", ephemeral=True)
            return
        
        if not can_manage_quest(interaction.user, interaction.guild, quest.creator_id):
            await interaction.response.send_message("You don't have permission to delete this quest!", ephemeral=True)
            return
        
        success = await self.quest_manager.delete_quest(quest_id)
        if success:
            embed = discord.Embed(
                title="Quest Deleted",
                description=f"Quest **{quest.title}** has been permanently deleted.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Quest Details",
                value=f"**ID:** `{quest.quest_id}`\n**Rank:** {quest.rank.title()}\n**Category:** {quest.category.title()}",
                inline=True
            )
            embed.add_field(
                name="Deleted By",
                value=interaction.user.mention,
                inline=True
            )
            embed.set_footer(text="This action cannot be undone")
            embed.timestamp = datetime.now()
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("Failed to delete quest!", ephemeral=True)

    @app_commands.command(name="create_from_template", description="Create a quest from a template")
    @app_commands.describe(
        template_name="Choose a quest template",
        title="Custom title for your quest (optional)",
        description="Custom description for your quest (optional)",
        requirements="Custom requirements (optional)",
        reward="Custom reward (optional)"
    )
    @app_commands.choices(template_name=[
        app_commands.Choice(name="Hunting Adventure", value="hunting_basic"),
        app_commands.Choice(name="Gathering Materials", value="gathering_basic"),
        app_commands.Choice(name="Combat Challenge", value="combat_basic"),
        app_commands.Choice(name="Social Event", value="social_basic"),
        app_commands.Choice(name="Exploration Mission", value="exploration_basic"),
        app_commands.Choice(name="Building Project", value="building_basic"),
        app_commands.Choice(name="Trading Quest", value="trading_basic"),
        app_commands.Choice(name="Puzzle Challenge", value="puzzle_basic")
    ])
    async def create_from_template(self, interaction: discord.Interaction,
                                   template_name: str,
                                   title: str = None,
                                   description: str = None,
                                   requirements: str = None,
                                   reward: str = None):
        """Create a quest from a template"""
        if not has_quest_creation_permission(interaction.user, interaction.guild):
            await interaction.response.send_message("You don't have permission to create quests!", ephemeral=True)
            return

        if not self.quest_templates:
            await interaction.response.send_message("Quest templates are not available!", ephemeral=True)
            return

        await interaction.response.defer()

        # Get template
        template = self.quest_templates.get_template(template_name)
        if not template:
            await interaction.response.send_message("Template not found!", ephemeral=True)
            return

        # Use custom values or template defaults
        final_title = title or template.title
        final_description = description or template.description
        final_requirements = requirements or template.requirements
        final_reward = reward or template.reward

        # Create quest from template
        quest = await self.quest_manager.create_quest(
            title=final_title,
            description=final_description,
            creator_id=interaction.user.id,
            guild_id=interaction.guild.id,
            requirements=final_requirements,
            reward=final_reward,
            rank=template.rank,
            category=template.category,
            required_role_ids=[]
        )

        # Create beautiful template embed
        embed = discord.Embed(
            title="✨ Quest Created from Template",
            description=f"Successfully created **{quest.title}** using the **{template_name.replace('_', ' ').title()}** template.",
            color=self._get_rank_color(quest.rank)
        )
        
        embed.add_field(
            name="■ Template Information",
            value=f"**Template:** {template_name.replace('_', ' ').title()}\n**Category:** {template.category.title()}\n**Difficulty:** {template.rank.title()}",
            inline=True
        )
        
        embed.add_field(
            name="■ Quest Details",
            value=f"**Quest ID:** `{quest.quest_id}`\n**Creator:** {interaction.user.display_name}\n**Status:** Available",
            inline=True
        )
        
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        
        if final_description:
            embed.add_field(
                name="■ Description",
                value=f"```\n{final_description[:500]}{'...' if len(final_description) > 500 else ''}\n```",
                inline=False
            )
        
        if final_requirements:
            embed.add_field(
                name="■ Requirements",
                value=f"```yaml\n{final_requirements[:300]}{'...' if len(final_requirements) > 300 else ''}\n```",
                inline=False
            )
        
        if final_reward:
            embed.add_field(
                name="■ Reward",
                value=f"```yaml\n{final_reward[:300]}{'...' if len(final_reward) > 300 else ''}\n```",
                inline=False
            )
        
        embed.add_field(
            name="■ What's Next",
            value="Your quest has been posted to the quest list channel and is ready for adventurers to accept!",
            inline=False
        )
        
        embed.set_footer(text=f"Quest ID: {quest.quest_id} • Template: {template_name}")
        embed.timestamp = datetime.now()

        await interaction.followup.send(embed=embed)

        # Post to quest list channel (reuse existing logic)
        quest_list_channel_id = await self.channel_config.get_quest_list_channel(interaction.guild.id)
        if quest_list_channel_id:
            quest_list_channel = interaction.guild.get_channel(quest_list_channel_id)
            if quest_list_channel:
                # Create the public quest embed (reuse existing embed creation logic)
                public_embed = discord.Embed(
                    title="NEW QUEST AVAILABLE",
                    description=f"**{quest.title}** *(Created from Template)*",
                    color=self._get_rank_color(quest.rank)
                )
                
                public_embed.add_field(
                    name="■ Description",
                    value=f"```\n{quest.description}\n```",
                    inline=False
                )
                
                quest_info = f"**Quest ID:** `{quest.quest_id}`\n**Difficulty:** {quest.rank.title()}\n**Category:** {quest.category.title()}"
                public_embed.add_field(
                    name="■ Quest Information",
                    value=quest_info,
                    inline=True
                )
                
                public_embed.add_field(
                    name="■ Status",
                    value=f"**{quest.status.title()}**\n*Ready to Accept*",
                    inline=True
                )
                
                public_embed.add_field(name="\u200b", value="\u200b", inline=True)
                
                if quest.requirements:
                    public_embed.add_field(
                        name="■ Requirements",
                        value=f"```yaml\n{quest.requirements}\n```",
                        inline=False
                    )
                
                if quest.reward:
                    public_embed.add_field(
                        name="■ Reward",
                        value=f"```yaml\n{quest.reward}\n```",
                        inline=False
                    )
                
                accept_channel = await self.channel_config.get_quest_accept_channel(interaction.guild.id)
                if accept_channel:
                    public_embed.add_field(
                        name="■ How to Accept This Quest",
                        value=f"Use `/accept_quest {quest.quest_id}` in <#{accept_channel}>",
                        inline=False
                    )
                
                public_embed.set_author(
                    name=f"Quest Creator: {interaction.user.display_name}",
                    icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None
                )
                
                public_embed.set_footer(
                    text=f"Quest ID: {quest.quest_id} • Created from template • {quest.created_at.strftime('%B %d, %Y at %I:%M %p')}",
                    icon_url=interaction.guild.icon.url if interaction.guild.icon else None
                )
                
                public_embed.timestamp = quest.created_at
                
                await quest_list_channel.send(embed=public_embed)

    @app_commands.command(name="bookmark_quest", description="Bookmark a quest for later")
    @app_commands.describe(quest_id="The ID of the quest to bookmark")
    async def bookmark_quest(self, interaction: discord.Interaction, quest_id: str):
        """Bookmark a quest for later"""
        if not self.quest_bookmarks:
            await interaction.response.send_message("Quest bookmarks are not available!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        quest = await self.quest_manager.get_quest(quest_id)
        if not quest:
            await interaction.followup.send("Quest not found!", ephemeral=True)
            return

        if quest.guild_id != interaction.guild.id:
            await interaction.followup.send("Quest not found in this server!", ephemeral=True)
            return

        success = await self.quest_bookmarks.add_bookmark(interaction.user.id, quest_id)
        
        if success:
            embed = discord.Embed(
                title="📚 Quest Bookmarked",
                description=f"Successfully bookmarked **{quest.title}** for later reference.",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="■ Quest Information",
                value=f"**ID:** `{quest.quest_id}`\n**Title:** {quest.title}\n**Difficulty:** {quest.rank.title()}\n**Category:** {quest.category.title()}",
                inline=True
            )
            
            embed.add_field(
                name="■ Bookmark Status",
                value="**Added to Bookmarks**\n*You can now easily find this quest later*",
                inline=True
            )
            
            embed.add_field(name="\u200b", value="\u200b", inline=True)
            
            embed.add_field(
                name="■ Quick Access",
                value="Use `/my_bookmarks` to view all your bookmarked quests anytime.",
                inline=False
            )
            
            embed.set_footer(text=f"Quest ID: {quest.quest_id} • Bookmark added")
            embed.timestamp = datetime.now()
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="📚 Already Bookmarked",
                description=f"**{quest.title}** is already in your bookmarks.",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="■ Quest Information",
                value=f"**ID:** `{quest.quest_id}`\n**Title:** {quest.title}",
                inline=True
            )
            
            embed.add_field(
                name="■ Bookmark Status",
                value="**Already Saved**\n*This quest is already bookmarked*",
                inline=True
            )
            
            embed.add_field(
                name="■ Quick Access",
                value="Use `/my_bookmarks` to view all your bookmarked quests.",
                inline=False
            )
            
            embed.set_footer(text="Use /remove_bookmark to remove it if needed")
            
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="remove_bookmark", description="Remove a quest from your bookmarks")
    @app_commands.describe(quest_id="The ID of the quest to remove from bookmarks")
    async def remove_bookmark(self, interaction: discord.Interaction, quest_id: str):
        """Remove a quest from bookmarks"""
        if not self.quest_bookmarks:
            await interaction.response.send_message("Quest bookmarks are not available!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        success = await self.quest_bookmarks.remove_bookmark(interaction.user.id, quest_id)
        
        if success:
            quest = await self.quest_manager.get_quest(quest_id)
            quest_title = quest.title if quest else "Unknown Quest"
            
            embed = discord.Embed(
                title="🗑️ Bookmark Removed",
                description=f"Successfully removed **{quest_title}** from your bookmarks.",
                color=discord.Color.red()
            )
            
            embed.add_field(
                name="■ Action Completed",
                value=f"**Quest ID:** `{quest_id}`\n**Status:** Removed from bookmarks",
                inline=True
            )
            
            embed.add_field(
                name="■ Quick Access",
                value="Use `/my_bookmarks` to view your remaining bookmarked quests.",
                inline=True
            )
            
            embed.set_footer(text="You can bookmark this quest again anytime")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="🔍 Bookmark Not Found",
                description=f"Quest `{quest_id}` is not in your bookmarks.",
                color=discord.Color.light_grey()
            )
            
            embed.add_field(
                name="■ No Action Needed",
                value="This quest was not bookmarked or has already been removed.",
                inline=False
            )
            
            embed.add_field(
                name="■ Quick Access",
                value="Use `/my_bookmarks` to view your current bookmarked quests.",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="my_bookmarks", description="View your bookmarked quests")
    async def my_bookmarks(self, interaction: discord.Interaction):
        """View user's bookmarked quests"""
        if not self.quest_bookmarks:
            await interaction.response.send_message("Quest bookmarks are not available!", ephemeral=True)
            return

        bookmarks = await self.quest_bookmarks.get_user_bookmarks(interaction.user.id)
        
        if not bookmarks:
            embed = discord.Embed(
                title="📚 No Bookmarks Found",
                description="You haven't bookmarked any quests yet. Start building your quest collection!",
                color=discord.Color.light_grey()
            )
            
            embed.add_field(
                name="■ Getting Started",
                value="• Use `/list_quests` to browse available quests\n• Use `/bookmark_quest <quest_id>` to save interesting quests\n• Use `/quest_info <quest_id>` to learn more about a quest",
                inline=False
            )
            
            embed.add_field(
                name="■ Why Bookmark Quests?",
                value="• Save quests for later when you have time\n• Keep track of challenging quests to attempt\n• Build a personal quest wishlist",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="📚 Your Bookmarked Quests",
            description=f"You have **{len(bookmarks)}** quest{'s' if len(bookmarks) != 1 else ''} bookmarked.",
            color=discord.Color.blue()
        )

        # Group bookmarks by status
        available_quests = []
        other_quests = []

        for bookmark in bookmarks:
            quest = await self.quest_manager.get_quest(bookmark['quest_id'])
            if quest and quest.guild_id == interaction.guild.id:
                if quest.status == "available":
                    available_quests.append(quest)
                else:
                    other_quests.append(quest)

        # Show available quests first
        if available_quests:
            quest_list = []
            for quest in available_quests[:5]:  # Limit to 5
                quest_list.append(f"• `{quest.quest_id}` **{quest.title}**\n  *{quest.rank.title()} • {quest.category.title()}*")
            
            title = f"■ Available Quests ({len(available_quests)})"
            if len(available_quests) > 5:
                title += " - Showing first 5"
            
            embed.add_field(
                name=title,
                value="\n".join(quest_list),
                inline=False
            )

        # Show other status quests
        if other_quests:
            quest_list = []
            for quest in other_quests[:3]:  # Limit to 3
                status_emoji = "🔄" if quest.status == "accepted" else "✅" if quest.status == "approved" else "❌"
                quest_list.append(f"• `{quest.quest_id}` **{quest.title}** {status_emoji}\n  *{quest.status.title()} • {quest.rank.title()}*")
            
            title = f"■ Other Bookmarked Quests ({len(other_quests)})"
            if len(other_quests) > 3:
                title += " - Showing first 3"
            
            embed.add_field(
                name=title,
                value="\n".join(quest_list),
                inline=False
            )

        embed.add_field(
            name="■ Quick Actions",
            value="• Use `/quest_info <quest_id>` to view quest details\n• Use `/accept_quest <quest_id>` to start a quest\n• Use `/remove_bookmark <quest_id>` to remove from bookmarks",
            inline=False
        )

        embed.set_footer(text="Bookmarks are personal and only visible to you")
        embed.timestamp = datetime.now()

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="search_quests", description="Search for quests by keyword")
    @app_commands.describe(
        keyword="Search keyword for quest titles and descriptions",
        rank_filter="Filter by quest rank",
        category_filter="Filter by quest category"
    )
    @app_commands.choices(rank_filter=[
        app_commands.Choice(name="Easy", value=QuestRank.EASY),
        app_commands.Choice(name="Normal", value=QuestRank.NORMAL),
        app_commands.Choice(name="Medium", value=QuestRank.MEDIUM),
        app_commands.Choice(name="Hard", value=QuestRank.HARD),
        app_commands.Choice(name="Impossible", value=QuestRank.IMPOSSIBLE)
    ])
    @app_commands.choices(category_filter=[
        app_commands.Choice(name="Hunting", value=QuestCategory.HUNTING),
        app_commands.Choice(name="Gathering", value=QuestCategory.GATHERING),
        app_commands.Choice(name="Collecting", value=QuestCategory.COLLECTING),
        app_commands.Choice(name="Crafting", value=QuestCategory.CRAFTING),
        app_commands.Choice(name="Exploration", value=QuestCategory.EXPLORATION),
        app_commands.Choice(name="Combat", value=QuestCategory.COMBAT),
        app_commands.Choice(name="Social", value=QuestCategory.SOCIAL),
        app_commands.Choice(name="Building", value=QuestCategory.BUILDING),
        app_commands.Choice(name="Trading", value=QuestCategory.TRADING),
        app_commands.Choice(name="Puzzle", value=QuestCategory.PUZZLE),
        app_commands.Choice(name="Survival", value=QuestCategory.SURVIVAL),
        app_commands.Choice(name="Other", value=QuestCategory.OTHER)
    ])
    async def search_quests(self, interaction: discord.Interaction, 
                           keyword: str,
                           rank_filter: str = None,
                           category_filter: str = None):
        """Search for quests by keyword"""
        if not self.quest_search:
            await interaction.response.send_message("Quest search is not available!", ephemeral=True)
            return

        await interaction.response.defer()

        results = await self.quest_search.search_quests(
            interaction.guild.id, 
            keyword, 
            rank_filter, 
            category_filter
        )

        if not results:
            embed = discord.Embed(
                title="🔍 No Search Results",
                description=f"No quests found matching your search criteria.",
                color=discord.Color.light_grey()
            )
            
            embed.add_field(
                name="■ Search Details",
                value=f"**Keyword:** {keyword}\n**Rank Filter:** {rank_filter.title() if rank_filter else 'None'}\n**Category Filter:** {category_filter.title() if category_filter else 'None'}",
                inline=True
            )
            
            embed.add_field(
                name="■ Search Tips",
                value="• Try using different keywords\n• Remove filters to broaden search\n• Check spelling of search terms\n• Try searching for quest creators",
                inline=True
            )
            
            embed.add_field(
                name="■ Alternative Options",
                value="• Use `/list_quests` to browse all available quests\n• Use `/my_bookmarks` to view saved quests",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            return

        embed = discord.Embed(
            title="🔍 Quest Search Results",
            description=f"Found **{len(results)}** quest{'s' if len(results) != 1 else ''} matching your search.",
            color=discord.Color.green()
        )

        # Add search criteria
        search_info = f"**Keyword:** {keyword}"
        if rank_filter:
            search_info += f"\n**Rank:** {rank_filter.title()}"
        if category_filter:
            search_info += f"\n**Category:** {category_filter.title()}"
        
        embed.add_field(
            name="■ Search Criteria",
            value=search_info,
            inline=True
        )
        
        embed.add_field(
            name="■ Results Found",
            value=f"**{len(results)}** matching quest{'s' if len(results) != 1 else ''}",
            inline=True
        )
        
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        # Show results (limit to 8 for readability)
        for i, quest in enumerate(results[:8]):
            creator = interaction.guild.get_member(quest.creator_id)
            creator_name = creator.display_name if creator else "Unknown User"
            
            status_emoji = "🟢" if quest.status == "available" else "🟡" if quest.status == "accepted" else "🔴"
            
            quest_info = f"**Rank:** {quest.rank.title()}\n**Category:** {quest.category.title()}\n**Creator:** {creator_name}\n**Status:** {status_emoji} {quest.status.title()}"
            
            if quest.reward:
                reward_preview = quest.reward[:30] + '...' if len(quest.reward) > 30 else quest.reward
                quest_info += f"\n**Reward:** {reward_preview}"

            embed.add_field(
                name=f"■ {quest.title}",
                value=f"```yaml\nID: {quest.quest_id}\n```{quest_info}",
                inline=True
            )

        if len(results) > 8:
            embed.add_field(
                name="■ Additional Results",
                value=f"Showing first 8 of {len(results)} results. Refine your search for more specific results.",
                inline=False
            )

        embed.add_field(
            name="■ Next Steps",
            value="• Use `/quest_info <quest_id>` to view detailed information\n• Use `/accept_quest <quest_id>` to start a quest\n• Use `/bookmark_quest <quest_id>` to save for later",
            inline=False
        )

        embed.set_footer(text="Search completed • Use different keywords to find more quests")
        embed.timestamp = datetime.now()

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="quest_analytics", description="View quest analytics for this server")
    async def quest_analytics(self, interaction: discord.Interaction):
        """View quest analytics"""
        if not self.quest_analytics:
            await interaction.response.send_message("Quest analytics are not available!", ephemeral=True)
            return

        if not has_quest_creation_permission(interaction.user, interaction.guild):
            await interaction.response.send_message("You don't have permission to view analytics!", ephemeral=True)
            return

        await interaction.response.defer()

        analytics = await self.quest_analytics.get_guild_analytics(interaction.guild.id)

        embed = discord.Embed(
            title="📊 Quest Analytics Dashboard",
            description=f"Comprehensive quest statistics for **{interaction.guild.name}**",
            color=discord.Color.blue()
        )

        # Overall statistics
        embed.add_field(
            name="■ Overall Statistics",
            value=f"**Total Quests:** {analytics['total_quests']}\n**Completed Quests:** {analytics['completed_quests']}\n**Active Users:** {analytics['active_users']}\n**Success Rate:** {analytics['success_rate']:.1f}%",
            inline=True
        )

        # Popular categories
        if analytics['popular_categories']:
            cat_text = "\n".join([f"**{cat.title()}:** {count} quests" for cat, count in analytics['popular_categories'][:5]])
            embed.add_field(
                name="■ Popular Categories",
                value=cat_text,
                inline=True
            )

        # Popular ranks
        if analytics['popular_ranks']:
            rank_text = "\n".join([f"**{rank.title()}:** {count} quests" for rank, count in analytics['popular_ranks'][:5]])
            embed.add_field(
                name="■ Difficulty Distribution",
                value=rank_text,
                inline=True
            )

        # Top creators
        if analytics['top_creators']:
            creator_list = []
            for creator_id, count in analytics['top_creators'][:5]:
                creator = interaction.guild.get_member(creator_id)
                creator_name = creator.display_name if creator else "Unknown User"
                creator_list.append(f"**{creator_name}:** {count} quests")
            
            embed.add_field(
                name="■ Top Quest Creators",
                value="\n".join(creator_list),
                inline=False
            )

        # Recent activity
        if analytics.get('recent_activity'):
            embed.add_field(
                name="■ Recent Activity (Last 7 Days)",
                value=f"**New Quests:** {analytics['recent_activity'].get('new_quests', 0)}\n**Completed:** {analytics['recent_activity'].get('completed', 0)}\n**New Users:** {analytics['recent_activity'].get('new_users', 0)}",
                inline=True
            )

        # Completion trends
        if analytics.get('completion_trends'):
            embed.add_field(
                name="■ Completion Trends",
                value=f"**Average Time:** {analytics['completion_trends'].get('avg_completion_time', 'N/A')}\n**Most Active Day:** {analytics['completion_trends'].get('most_active_day', 'N/A')}\n**Peak Hours:** {analytics['completion_trends'].get('peak_hours', 'N/A')}",
                inline=True
            )

        embed.add_field(
            name="■ Server Health",
            value=f"**Quest Variety:** {'High' if len(analytics.get('popular_categories', [])) >= 5 else 'Medium' if len(analytics.get('popular_categories', [])) >= 3 else 'Low'}\n**User Engagement:** {'High' if analytics['active_users'] >= 10 else 'Medium' if analytics['active_users'] >= 5 else 'Low'}\n**Success Rate:** {'Excellent' if analytics['success_rate'] >= 80 else 'Good' if analytics['success_rate'] >= 60 else 'Needs Improvement'}",
            inline=True
        )

        embed.set_footer(text="Analytics updated in real-time • Data shown for this server only")
        embed.timestamp = datetime.now()

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="help", description="Get help with quest commands")
    async def help_command(self, interaction: discord.Interaction):
        """Get help with quest commands"""
        embed = discord.Embed(
            title="🎯 Quest Bot Command Guide",
            description="**Complete guide to managing quests in your server**",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="■ Server Setup",
            value="```yaml\n/setup_channels - Configure quest channels for your server\n```",
            inline=False
        )
        
        embed.add_field(
            name="■ Quest Creation & Management",
            value="```yaml\n/create_quest - Create a new quest\n/create_from_template - Create quest from template\n/delete_quest - Delete a quest (creators only)\n```",
            inline=False
        )
        
        embed.add_field(
            name="■ Quest Participation",
            value="```yaml\n/list_quests - View available quests\n/quest_info - Get detailed quest information\n/accept_quest - Accept a quest\n/submit_quest - Submit completed quest\n```",
            inline=False
        )
        
        embed.add_field(
            name="■ Quest Discovery & Organization",
            value="```yaml\n/search_quests - Search quests by keyword\n/bookmark_quest - Save quest for later\n/remove_bookmark - Remove quest bookmark\n/my_bookmarks - View your bookmarked quests\n```",
            inline=False
        )
        
        embed.add_field(
            name="■ Quest Review",
            value="```yaml\n/approve_quest - Approve a completed quest\n/reject_quest - Reject a completed quest\n```",
            inline=False
        )
        
        embed.add_field(
            name="■ Progress & Analytics",
            value="```yaml\n/my_quests - View your quest progress\n/leaderboard - View server leaderboard\n/quest_analytics - View server quest statistics\n```",
            inline=False
        )
        
        embed.add_field(
            name="■ Quest Difficulty Levels",
            value="**Easy** → **Normal** → **Medium** → **Hard** → **Impossible**",
            inline=True
        )
        
        embed.add_field(
            name="■ Available Categories",
            value="**Hunting** • **Gathering** • **Collecting** • **Crafting**\n**Exploration** • **Combat** • **Social** • **Building**\n**Trading** • **Puzzle** • **Survival** • **Other**",
            inline=True
        )
        
        embed.add_field(
            name="■ New Features ✨",
            value="• **Templates** - Quick quest creation\n• **Bookmarks** - Save quests for later\n• **Search** - Find quests by keyword\n• **Analytics** - Track server statistics",
            inline=False
        )
        
        embed.set_footer(text="Need additional help? Contact your server administrators • Enhanced quest management system")
        embed.timestamp = datetime.now()
        
        await interaction.response.send_message(embed=embed)
