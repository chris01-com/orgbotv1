
import asyncio
import json
import os
from datetime import datetime
from bot.sql_database import SQLDatabase
from bot.models import Quest, QuestProgress, UserStats, ChannelConfig

class JSONToSQLMigrator:
    """Migrates data from JSON files to PostgreSQL database"""
    
    def __init__(self):
        self.database = SQLDatabase()
        self.json_data_dir = "data"  # Adjust if your JSON files are in a different directory
    
    async def migrate_all(self):
        """Run complete migration from JSON to SQL"""
        print("Starting migration from JSON to PostgreSQL...")
        
        # Initialize database
        await self.database.initialize()
        
        # Migrate each data type
        await self.migrate_quests()
        await self.migrate_quest_progress()
        await self.migrate_user_stats()
        await self.migrate_channel_config()
        
        print("Migration completed successfully!")
        await self.database.close()
    
    async def migrate_quests(self):
        """Migrate quests from JSON"""
        quests_file = os.path.join(self.json_data_dir, "quests.json")
        if not os.path.exists(quests_file):
            print(f"No quests file found at {quests_file}")
            return
        
        print("Migrating quests...")
        with open(quests_file, 'r') as f:
            quests_data = json.load(f)
        
        migrated_count = 0
        for quest_data in quests_data.values():
            try:
                # Convert datetime string if needed
                if isinstance(quest_data.get('created_at'), str):
                    quest_data['created_at'] = datetime.fromisoformat(quest_data['created_at'])
                
                quest = Quest.from_dict(quest_data)
                await self.database.save_quest(quest)
                migrated_count += 1
            except Exception as e:
                print(f"Error migrating quest {quest_data.get('quest_id', 'unknown')}: {e}")
        
        print(f"Migrated {migrated_count} quests")
    
    async def migrate_quest_progress(self):
        """Migrate quest progress from JSON"""
        progress_file = os.path.join(self.json_data_dir, "quest_progress.json")
        if not os.path.exists(progress_file):
            print(f"No quest progress file found at {progress_file}")
            return
        
        print("Migrating quest progress...")
        with open(progress_file, 'r') as f:
            progress_data = json.load(f)
        
        migrated_count = 0
        for progress_entry in progress_data.values():
            try:
                # Convert datetime strings if needed
                for date_field in ['accepted_at', 'completed_at', 'approved_at']:
                    if isinstance(progress_entry.get(date_field), str):
                        progress_entry[date_field] = datetime.fromisoformat(progress_entry[date_field])
                
                progress = QuestProgress.from_dict(progress_entry)
                await self.database.save_quest_progress(progress)
                migrated_count += 1
            except Exception as e:
                print(f"Error migrating quest progress for user {progress_entry.get('user_id', 'unknown')}: {e}")
        
        print(f"Migrated {migrated_count} quest progress entries")
    
    async def migrate_user_stats(self):
        """Migrate user statistics from JSON"""
        stats_file = os.path.join(self.json_data_dir, "user_stats.json")
        if not os.path.exists(stats_file):
            print(f"No user stats file found at {stats_file}")
            return
        
        print("Migrating user statistics...")
        with open(stats_file, 'r') as f:
            stats_data = json.load(f)
        
        migrated_count = 0
        for stats_entry in stats_data.values():
            try:
                # Convert datetime string if needed
                if isinstance(stats_entry.get('last_updated'), str):
                    stats_entry['last_updated'] = datetime.fromisoformat(stats_entry['last_updated'])
                
                stats = UserStats.from_dict(stats_entry)
                await self.database.save_user_stats(stats)
                migrated_count += 1
            except Exception as e:
                print(f"Error migrating user stats for user {stats_entry.get('user_id', 'unknown')}: {e}")
        
        print(f"Migrated {migrated_count} user statistics")
    
    async def migrate_channel_config(self):
        """Migrate channel configuration from JSON"""
        config_file = os.path.join(self.json_data_dir, "channel_config.json")
        if not os.path.exists(config_file):
            print(f"No channel config file found at {config_file}")
            return
        
        print("Migrating channel configurations...")
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        migrated_count = 0
        for config_entry in config_data.values():
            try:
                config = ChannelConfig.from_dict(config_entry)
                await self.database.save_channel_config(config)
                migrated_count += 1
            except Exception as e:
                print(f"Error migrating channel config for guild {config_entry.get('guild_id', 'unknown')}: {e}")
        
        print(f"Migrated {migrated_count} channel configurations")
    
    def check_json_files(self):
        """Check what JSON files are available for migration"""
        print("Checking for JSON files...")
        files_to_check = ["quests.json", "quest_progress.json", "user_stats.json", "channel_config.json"]
        
        for filename in files_to_check:
            filepath = os.path.join(self.json_data_dir, filename)
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    data = json.load(f)
                print(f"✓ {filename}: {len(data)} entries")
            else:
                print(f"✗ {filename}: Not found")

async def main():
    """Main migration function"""
    migrator = JSONToSQLMigrator()
    
    # First check what files are available
    migrator.check_json_files()
    
    # Ask for confirmation
    response = input("\nProceed with migration? (y/n): ")
    if response.lower() != 'y':
        print("Migration cancelled")
        return
    
    # Run migration
    await migrator.migrate_all()

if __name__ == "__main__":
    asyncio.run(main())
