"""
Migration script to convert participants from simple email strings to objects with email and league_user_name.

Usage:
    python scripts/migrate_participants.py

This script will:
1. Find all leagues with participants stored as simple strings
2. Look up each participant's user name from the User collection
3. Convert each participant to the new format: {email: string, league_user_name: string}
4. Update the league in MongoDB

The script is idempotent - running it multiple times won't cause issues as it checks 
if participants are already in the new format before converting.
"""

import sys
import os

# Add the project root directory to the path so we can import our modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.config.mongo import db
from src.user_module.user import User


def migrate_participants():
    """Migrate all leagues to use the new participant format"""
    
    # Find all leagues
    leagues = db.leagues.find({})
    
    migrated_count = 0
    skipped_count = 0
    error_count = 0
    
    for league in leagues:
        league_id = league.get('_id')
        league_name = league.get('name', 'Unknown')
        participants = league.get('participants', [])
        
        if not participants:
            print(f"  Skipping '{league_name}' - no participants")
            skipped_count += 1
            continue
        
        # Check if already migrated (first participant is a dict)
        if participants and isinstance(participants[0], dict):
            print(f"  Skipping '{league_name}' - already migrated")
            skipped_count += 1
            continue
        
        # Convert participants to new format
        new_participants = []
        for participant in participants:
            if isinstance(participant, str):
                # Old format - convert to new format
                email = participant
                
                # Try to get user's name from User collection
                user = User.get_user_by_mail(email)
                league_user_name = user.name if user else email
                
                new_participants.append({
                    "email": email,
                    "league_user_name": league_user_name
                })
            elif isinstance(participant, dict):
                # Already in new format, keep as is
                new_participants.append(participant)
            else:
                print(f"  Warning: Unknown participant format in '{league_name}': {participant}")
                new_participants.append({
                    "email": str(participant),
                    "league_user_name": str(participant)
                })
        
        # Update the league
        try:
            result = db.leagues.update_one(
                {"_id": league_id},
                {"$set": {"participants": new_participants}}
            )
            
            if result.modified_count > 0:
                print(f"  ✓ Migrated '{league_name}' - {len(new_participants)} participants")
                migrated_count += 1
            else:
                print(f"  - No changes for '{league_name}'")
                skipped_count += 1
                
        except Exception as e:
            print(f"  ✗ Error migrating '{league_name}': {e}")
            error_count += 1
    
    print("\n" + "=" * 50)
    print(f"Migration complete!")
    print(f"  Migrated: {migrated_count}")
    print(f"  Skipped:  {skipped_count}")
    print(f"  Errors:   {error_count}")


def rollback_participants():
    """Rollback migration - convert participants back to simple email strings"""
    
    # Find all leagues
    leagues = db.leagues.find({})
    
    rollback_count = 0
    skipped_count = 0
    
    for league in leagues:
        league_id = league.get('_id')
        league_name = league.get('name', 'Unknown')
        participants = league.get('participants', [])
        
        if not participants:
            skipped_count += 1
            continue
        
        # Check if needs rollback (first participant is a dict)
        if participants and isinstance(participants[0], str):
            print(f"  Skipping '{league_name}' - already in old format")
            skipped_count += 1
            continue
        
        # Convert back to simple email strings
        old_format_participants = []
        for participant in participants:
            if isinstance(participant, dict):
                old_format_participants.append(participant.get('email', ''))
            else:
                old_format_participants.append(str(participant))
        
        # Update the league
        try:
            result = db.leagues.update_one(
                {"_id": league_id},
                {"$set": {"participants": old_format_participants}}
            )
            
            if result.modified_count > 0:
                print(f"  ✓ Rolled back '{league_name}'")
                rollback_count += 1
                
        except Exception as e:
            print(f"  ✗ Error rolling back '{league_name}': {e}")
    
    print("\n" + "=" * 50)
    print(f"Rollback complete!")
    print(f"  Rolled back: {rollback_count}")
    print(f"  Skipped:     {skipped_count}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate league participants format')
    parser.add_argument('--rollback', action='store_true', help='Rollback to old format')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("DRY RUN - No changes will be made\n")
    
    print("=" * 50)
    print("League Participants Migration Script")
    print("=" * 50 + "\n")
    
    if args.rollback:
        print("Mode: ROLLBACK (converting back to email strings)\n")
        if not args.dry_run:
            rollback_participants()
        else:
            print("Would rollback participants to simple email strings")
    else:
        print("Mode: MIGRATE (converting to {email, league_user_name} objects)\n")
        if not args.dry_run:
            migrate_participants()
        else:
            print("Would migrate participants to new object format")
