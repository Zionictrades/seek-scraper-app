# test script to verify async scraper
import sys
import asyncio
from pathlib import Path

# ensure project root (backend) is on sys.path so "from app import scraper" works
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import scraper

async def main():
    jobs = await scraper.scrape_seek(role="Electrician", location="Adelaide", pages=1)
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j)

if __name__ == "__main__":
    asyncio.run(main())
