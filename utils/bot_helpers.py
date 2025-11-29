"""Bot helper utilities for resilient Telegram interactions.

This module provides safe wrappers with retry/backoff for network calls
to Telegram (send_message, edit_message_text, etc.) to avoid crashes
when intermittent ConnectionResetError (WinError 10054) or other
requests-level issues occur.

Usage:
	from utils.bot_helpers import safe_send_message
	safe_send_message(bot, chat_id, "Hello", reply_markup=...)  # returns telebot.types.Message or None

Design notes:
 - Retries only on network/request-level exceptions.
 - Backoff is exponential but capped to keep latency low for admin flows.
 - All exceptions are swallowed after final attempt; returning None signals failure.
 - Optional "silent" flag to suppress logging.
"""

from __future__ import annotations

import time
from typing import Any, Optional, Callable

import requests

NETWORK_EXCEPTIONS = (
	requests.exceptions.ConnectionError,
	requests.exceptions.Timeout,
	requests.exceptions.RequestException,
)

def _should_retry(exc: Exception) -> bool:
	"""Decide if we should retry given an exception."""
	if isinstance(exc, NETWORK_EXCEPTIONS):
		return True
	# WinError 10054 sometimes wrapped in generic Exception; check message.
	msg = str(exc)
	if '10054' in msg or 'Connection aborted' in msg:
		return True
	return False

def safe_send_message(bot, chat_id: int, text: str, *, parse_mode: Optional[str]=None,
					   reply_markup: Any=None, disable_web_page_preview: Optional[bool]=None,
					   max_retries: int=4, base_delay: float=0.6, silent: bool=True,
					   on_retry: Optional[Callable[[int, Exception, float], None]] = None) -> Any:
	"""Send a message with retry/backoff; returns Message or None.

	on_retry: optional callback invoked as on_retry(attempt_number, exception, delay_seconds)
	BEFORE sleeping (attempt_number starts at 1 for first retry).
	"""
	attempt = 0
	while True:
		try:
			return bot.send_message(
				chat_id,
				text,
				parse_mode=parse_mode,
				reply_markup=reply_markup,
				disable_web_page_preview=disable_web_page_preview,
			)
		except Exception as e:
			attempt += 1
			if not _should_retry(e) or attempt > max_retries:
				if not silent:
					print(f"safe_send_message: giving up after {attempt} attempts: {e}")
				return None
			# backoff
			delay = min(base_delay * (2 ** (attempt - 1)), 5)
			if on_retry:
				try:
					on_retry(attempt, e, delay)
				except Exception:
					pass
			if not silent:
				print(f"safe_send_message: retry {attempt}/{max_retries} in {delay:.1f}s due to {e}")
			time.sleep(delay)

def safe_edit_text(bot, chat_id: int, message_id: int, text: str, *, parse_mode: Optional[str]=None,
				   reply_markup: Any=None, max_retries: int=3, base_delay: float=0.5, silent: bool=True,
				   on_retry: Optional[Callable[[int, Exception, float], None]] = None) -> bool:
	"""Edit a message text safely with retry; returns True if success."""
	attempt = 0
	while True:
		try:
			bot.edit_message_text(text, chat_id, message_id, parse_mode=parse_mode, reply_markup=reply_markup)
			return True
		except Exception as e:
			attempt += 1
			if not _should_retry(e) or attempt > max_retries:
				if not silent:
					print(f"safe_edit_text: failed after {attempt} attempts: {e}")
				return False
			delay = min(base_delay * (2 ** (attempt - 1)), 4)
			if on_retry:
				try:
					on_retry(attempt, e, delay)
				except Exception:
					pass
			time.sleep(delay)

def safe_send_photo(bot, chat_id: int, file_id: str, *, caption: Optional[str]=None,
					 parse_mode: Optional[str]=None, reply_markup: Any=None, max_retries: int=4,
					 base_delay: float=0.6, silent: bool=True,
					 on_retry: Optional[Callable[[int, Exception, float], None]] = None) -> Any:
	attempt = 0
	while True:
		try:
			return bot.send_photo(chat_id, file_id, caption=caption, parse_mode=parse_mode, reply_markup=reply_markup)
		except Exception as e:
			attempt += 1
			if not _should_retry(e) or attempt > max_retries:
				if not silent:
					print(f"safe_send_photo: giving up after {attempt} attempts: {e}")
				return None
			delay = min(base_delay * (2 ** (attempt - 1)), 5)
			if on_retry:
				try:
					on_retry(attempt, e, delay)
				except Exception:
					pass
			time.sleep(delay)

