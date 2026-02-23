#!/usr/bin/env python3
"""
Test script to verify the email reading and memory writing pipeline.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables FIRST
from dotenv import load_dotenv
load_dotenv()

from agents.email_reader import EmailReaderAgent
from agents.memory_writer import MemoryWriterAgent

print("="*60)
print("Testing Email Memory Agent Pipeline")
print("="*60)

# Step 1: Test EmailReaderAgent
print("\n[Step 1] Testing EmailReaderAgent...")
email_reader = EmailReaderAgent()
prompt = "Build my memory from emails. Fetch up to 5 emails from the last 30 days."

try:
    reader_result = email_reader.run(prompt)
    print(f"\n[OK] EmailReaderAgent completed")
    print(f"  Result length: {len(reader_result)} characters")

    # Check if result contains expected structure
    if "observations" in reader_result.lower():
        print("\n[OK] Result contains 'observations'")
        # Count observations
        import json
        try:
            result_json = json.loads(reader_result)
            obs_count = len(result_json.get("observations", []))
            print(f"  Number of observations: {obs_count}")
        except:
            print("  (Could not parse JSON to count observations)")
    else:
        print("\n[WARN] Result does NOT contain 'observations'")
        # Try to print preview without emojis
        try:
            print(f"\n  Preview: {reader_result[:500]}")
        except:
            print("  (Cannot display preview due to encoding)")

except Exception as e:
    print(f"\n[ERROR] EmailReaderAgent FAILED: {e}")
    sys.exit(1)

# Step 2: Test MemoryWriterAgent
print("\n[Step 2] Testing MemoryWriterAgent...")
memory_writer = MemoryWriterAgent()
writer_prompt = (
    "Here are observations about the user extracted from their emails. "
    "Process each observation and write it to the memory vault. "
    "Check for existing memories first to avoid duplicates.\n\n"
    f"OBSERVATIONS:\n{reader_result}"
)

try:
    writer_result = memory_writer.run(writer_prompt)
    print(f"\n[OK] MemoryWriterAgent completed")
    print(f"  Result: {writer_result[:500]}")
except Exception as e:
    print(f"\n[ERROR] MemoryWriterAgent FAILED: {e}")
    sys.exit(1)

# Step 3: Check vault
print("\n[Step 3] Checking vault...")
from memory.vault import get_vault_stats
import os

stats = get_vault_stats()
print(f"\n  Vault statistics:")
for key, value in stats.items():
    print(f"    {key}: {value}")

if stats['total'] > 0:
    print(f"\n[SUCCESS] Created {stats['total']} memories")

    # List created files
    print("\n  Files created:")
    for root, dirs, files in os.walk("vault"):
        for file in files:
            if file.endswith('.md') and file != '_index.md':
                filepath = os.path.join(root, file)
                print(f"    - {filepath}")
else:
    print("\n[WARN] No memories created!")

print("\n" + "="*60)
print("Test complete")
print("="*60)
