import os
import django
import sys

# Initialize Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from contributions.models import Contribution

print("\n" + "="*50)
print("⚠️  WARNING: FINANCIAL RECORD WIPE  ⚠️")
print("="*50)
print("This script will permanently delete ALL Contribution records in the database.")
print("It will NOT delete Users/Contestants, but all their raised amounts will drop to zero.")
print(f"Current number of records to delete: {Contribution.objects.count()}")
print("="*50 + "\n")

confirm = input("Are you absolutely sure you want to proceed? Type 'YES' to confirm: ")

if confirm == "YES":
    # Delete all contributions
    deleted_count, _ = Contribution.objects.all().delete()
    print(f"\n✅ Successfully wiped {deleted_count} financial records.")
    print("Database is now clean and ready for Live APIs.")
else:
    print("\n❌ Operation cancelled. No records were deleted.")
    sys.exit(0)
