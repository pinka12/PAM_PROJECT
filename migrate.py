#!/usr/bin/env python3
"""
Simple migration script
"""
import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("🚀 360° Manager Assessment System - Migration Script")
print("=" * 60)

try:
    # Import the migration function
    from app.aggregator import migrate_existing_data
    
    print("\n🔄 Running migration...")
    print("=" * 60)
    
    # Run the migration
    result = migrate_existing_data()
    
    if result.get("success"):
        print("\n✅ MIGRATION SUCCESSFUL!")
        print(f"   Created: {result.get('created', 0)} new manager entries")
        print(f"   Updated: {result.get('updated', 0)} existing manager entries")
        print(f"   Total managers: {result.get('total', 0)}")
        print("\n🎉 You can now start the server!")
        print("\nNext steps:")
        print("1. Start server: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        print("2. Open browser: http://localhost:8000/")
        print("3. View API: http://localhost:8000/api/managers")
    else:
        print(f"\n❌ MIGRATION FAILED: {result.get('error')}")
        print("\nTroubleshooting:")
        print("1. Check if MongoDB is running")
        print("2. Check if you have form responses in database")
        print("3. Check .env file configuration")
        
except ImportError as e:
    print(f"\n❌ Cannot import modules: {e}")
    print("\nMake sure these files exist:")
    print("  - app/__init__.py")
    print("  - app/db.py")
    print("  - app/aggregator.py")
    print("  - app/processor.py")
except Exception as e:
    print(f"\n❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()

print("=" * 60)