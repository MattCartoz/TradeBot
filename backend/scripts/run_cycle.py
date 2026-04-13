"""Run a single analysis cycle manually — for testing and development."""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.core.config import load_settings
from src.core.trading_loop import TradingLoop
from src.data.market_data import MarketDataProvider
from src.exchange.paper import AlpacaPaperExchange
from src.llm.claude_provider import ClaudeProvider
from src.llm.grok_provider import GrokProvider
from src.memory.episodic import EpisodicMemory
from src.memory.semantic import SemanticMemory
from src.memory.working import WorkingMemory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


async def main():
    settings = load_settings()

    market_data = MarketDataProvider(settings.exchange.name, sandbox=True)
    exchange = AlpacaPaperExchange(paper=True)
    claude = ClaudeProvider(model=settings.llm.claude.model)
    grok = GrokProvider(model=settings.llm.grok.model)
    episodic = EpisodicMemory(settings.database.url)
    semantic = SemanticMemory()
    working = WorkingMemory()

    working.load_from_disk()
    semantic.load()

    await market_data.initialize()
    await exchange.initialize()
    await episodic.initialize()

    async def log_event(event: dict):
        print(f"\n{'─'*60}")
        print(f"EVENT: {event.get('type', 'unknown')}")
        for k, v in event.items():
            if k != 'type':
                print(f"  {k}: {v}")
        print(f"{'─'*60}")

    loop = TradingLoop(
        settings=settings,
        market_data=market_data,
        exchange=exchange,
        claude_llm=claude,
        grok_llm=grok,
        working_memory=working,
        episodic_memory=episodic,
        semantic_memory=semantic,
        event_callback=log_event,
    )

    print("\n" + "=" * 60)
    print("  TRADING FLOOR — Manual Cycle")
    print("=" * 60 + "\n")

    result = await loop.run_cycle()

    print("\n" + "=" * 60)
    print("  CYCLE RESULT")
    print("=" * 60)
    for k, v in result.items():
        print(f"  {k}: {v}")

    # Cleanup
    await market_data.close()
    await exchange.close()
    await claude.close()
    await grok.close()
    await episodic.close()


if __name__ == "__main__":
    asyncio.run(main())
