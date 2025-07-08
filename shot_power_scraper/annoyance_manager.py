"""Annoyance clearing functionality for shot-scraper"""
import asyncio
import click
from shot_power_scraper.page_utils import evaluate_js
from shot_power_scraper.browser import Config


async def clear_annoyances(page, timeout_seconds=5):
    """Clear annoying elements on the page"""
    buttons_to_click = [
        "button[class*='pencraft'][data-testid='maybeLater']",  # Substack "No thanks" button
        "#prestitialPopup button[alt='close']",  # Prestitial popup close button
        ".CampaignType--popup button[title='Close']",  # Campaign popup close button
        "a[role='button'].dialog-close-button",  # Dialog close button
        "a[onclick*='interstitialBox.closeit()']",  # Interstitial box close button
        "a.popmake-close",  # WP popup maker close button
        ".popup-modal button.close-button",  # Popup modal close button
        ".popup-wrap a.close-popup",  # Popup wrap close button
        "a.modal1-close",  # Modal overlay close button
        ".modal-dialog button[data-dismiss='modal']",  # Modal dialog close button
        "button[data-action='close-mc-modal']",
    ]
    for selector in buttons_to_click:
        element = await page.query_selector(selector)
        if element:
            if Config.verbose:
                click.echo(f"Found annoyance: {selector}", err=True)
            await element.click()
            await asyncio.sleep(0.3)
