#!/usr/bin/env python3
"""Qdrant Cloud setup via Playwright — automated signup, cluster creation, and config."""

from __future__ import annotations
import asyncio
import sys
from pathlib import Path

async def setup_qdrant():
    print("=" * 60)
    print("QDRANT CLOUD SETUP — Playwright Automation")
    print("=" * 60)

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ERROR: Playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    email = "tap4500@gmail.com"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        page = await browser.new_page(viewport={"width": 1280, "height": 800})

        try:
            print("\n[1] Navigating to cloud.qdrant.io...")
            await page.goto("https://cloud.qdrant.io", wait_until="networkidle", timeout=60000)

            # Check for "Sign up" or "Start for free" buttons on landing page
            signup_selectors = [
                "text=Sign up", 
                "text=Start for free", 
                "text=Try for free",
                "a[href*='signup']",
                "button:has-text('Sign up')"
            ]
            
            for selector in signup_selectors:
                if await page.is_visible(selector):
                    print(f"\n[2] Clicking '{selector}'...")
                    await page.click(selector)
                    await page.wait_for_load_state("networkidle", timeout=20000)
                    break

            print("[3] Waiting for email input...")
            try:
                email_field = page.locator("input[type='email'], input[name='email'], input[placeholder*='email' i]")
                await email_field.first.wait_for(state="visible", timeout=30000)
                print(f"[3] Filling email: {email}")
                await email_field.first.fill(email)
            except Exception as e:
                print(f"  Warning: Could not find email field automatically: {e}")
                print("  Please enter your email manually in the browser window.")

            try:
                continue_btn = page.locator("button:has-text('Continue'), button:has-text('Sign up'), button[type='submit']")
                if await continue_btn.first.is_visible():
                    await continue_btn.first.click()
                    await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            print("\n" + "=" * 60)
            print(">>> EMAIL VERIFICATION REQUIRED <<<")
            print("Please check tap4500@gmail.com and enter the verification code")
            print("in the browser window, then click the verification link.")
            print("=" * 60)

            await page.wait_for_url("**/clusters**", timeout=300000)
            print("[4] Email verified, cluster page reached.")

            print("[5] Looking for 'Create Cluster' button...")

            try:
                create_btn = page.locator("button:has-text('Create Cluster'), button:has-text('New Cluster'), a:has-text('Create'), button:has-text('Create'):not([disabled])")
                await create_btn.first.click(timeout=10000)
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                print("  (Create button not immediately visible, looking for alternatives...)")

            await asyncio.sleep(3)

            print("[6] Selecting free tier cluster...")
            free_options = page.locator("text=FREE, text=Free, text=Free tier")
            if await free_options.count() > 0:
                await free_options.first.click()
                await asyncio.sleep(1)

            cluster_name = f"deterministic-brain-{Path.home().name}"
            print(f"[7] Setting cluster name: {cluster_name}")
            name_input = page.locator("input[placeholder*='name' i], input[placeholder*='cluster' i], input[name*='name']")
            if await name_input.count() > 0:
                await name_input.first.fill(cluster_name)
            else:
                await page.keyboard.type(cluster_name)

            print("[8] Creating cluster (this may take 1-2 minutes)...")
            submit_btn = page.locator("button:has-text('Create'):not([disabled]), button:has-text('Submit'), button:has-text('Deploy')")
            await submit_btn.first.click()

            print("  Waiting for cluster to be ready...")
            await page.wait_for_selector("text=Ready, text=ACTIVE, text=Running", timeout=120000)
            print("  Cluster is ready!")

            await asyncio.sleep(3)

            print("[9] Extracting API key...")

            settings_btn = page.locator("button:has-text('Settings'), button:has-text('API Key'), a:has-text('Settings')")
            if await settings_btn.count() > 0:
                await settings_btn.first.click()
                await page.wait_for_load_state("networkidle", timeout=10000)
                await asyncio.sleep(2)

            api_key_elem = page.locator("[readonly], input[readonly], text=API Key").first
            api_key = None

            cluster_url = page.url

            copy_btns = page.locator("button:has-text('Copy'), button[title*='API'], button[aria-label*='API']")
            if await copy_btns.count() > 0:
                await copy_btns.first.click()
                await asyncio.sleep(1)
                try:
                    api_key = await page.evaluate("navigator.clipboard.readText()")
                except Exception:
                    pass

            if not api_key or len(api_key) < 20:
                print("\n  Could not auto-extract API key.")
                print("  Please manually copy the API key from the Qdrant Cloud dashboard.")
                api_key = input("  Paste API key here: ").strip()

            cluster_url_elem = page.locator("input[readonly], text=https://").first
            cluster_url = await cluster_url_elem.inner_text() if await cluster_url_elem.count() > 0 else ""

            if not cluster_url or "cloud.qdrant" not in cluster_url:
                cluster_url = page.url

            print(f"\n[10] Cluster URL: {cluster_url}")
            print(f"[11] API Key: {'*' * 20}{api_key[-10:] if api_key else 'N/A'}")

            print("[12] Writing credentials to .env...")
            env_path = Path(".env")

            if env_path.exists():
                existing = env_path.read_text()
            else:
                existing = ""

            lines = existing.split("\n")
            qdrant_lines = [
                f"QDRANT_URL={cluster_url}",
                f"QDRANT_API_KEY={api_key}",
                "QDRANT_COLLECTION=brain_vectors",
            ]

            lines = [l for l in lines if not l.startswith("QDRANT_")]
            lines.extend(qdrant_lines)

            env_path.write_text("\n".join(lines) + "\n")
            print("  .env updated.")

            print("[13] Testing Qdrant connection...")
            try:
                from qdrant_client import QdrantClient
                client = QdrantClient(url=cluster_url, api_key=api_key, timeout=5)
                info = client.get_collections()
                print(f"  Connection OK. Existing collections: {[c.name for c in info.collections]}")

                from qdrant_client.models import Distance, VectorParams
                existing_names = [c.name for c in info.collections]
                if "brain_vectors" not in existing_names:
                    client.create_collection("brain_vectors", vectors_config=VectorParams(size=384, distance=Distance.COSINE))
                    print("  Created 'brain_vectors' collection.")

            except ImportError:
                print("  Qdrant client not installed (pip install qdrant-client) — skipping connection test.")
            except Exception as e:
                print(f"  Connection test failed: {e}")

            print("\n" + "=" * 60)
            print("QDRANT SETUP COMPLETE!")
            print("=" * 60)
            print(f"Cluster URL: {cluster_url}")
            print("API Key saved to .env")
            print("=" * 60)

        finally:
            await browser.close()


if __name__ == "__main__":
    try:
        asyncio.run(setup_qdrant())
    except KeyboardInterrupt:
        print("\nSetup cancelled by user.")
    except Exception as e:
        print(f"\nFATAL: {e}")
        import traceback
        traceback.print_exc()