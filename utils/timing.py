"""Timing utilities."""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator


@asynccontextmanager
async def timed(label: str, logger=None) -> AsyncIterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        if logger:
            logger.info("%s completed in %.2fs", label, elapsed)


async def wait_for_stabilization(page, wait_ms: int = 1500) -> None:
    """Wait for page layout and fonts to stabilize."""
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=15000)
    except Exception:
        pass

    try:
        await page.evaluate(
            """async () => {
                if (document.fonts && document.fonts.ready) {
                    await document.fonts.ready;
                }
            }"""
        )
    except Exception:
        pass

    await asyncio.sleep(wait_ms / 1000)

    try:
        await page.evaluate(
            """() => new Promise(resolve => {
                let lastHeight = 0;
                let stable = 0;
                const check = () => {
                    const h = document.body.scrollHeight;
                    if (h === lastHeight) stable++;
                    else { stable = 0; lastHeight = h; }
                    if (stable >= 3) resolve(true);
                    else requestAnimationFrame(check);
                };
                check();
            })"""
        )
    except Exception:
        pass
