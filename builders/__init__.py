"""
HTML builder modules for the Personal Dashboard.
Each module generates HTML sections from data.
"""

from .helpers import format_currency as format_currency, PIE_COLORS as PIE_COLORS, PIE_BORDER_COLORS as PIE_BORDER_COLORS
from .calendar import build_calendar_html as build_calendar_html, build_weather_forecast_html as build_weather_forecast_html
from .tasks import build_things_html as build_things_html, build_task_li as build_task_li
from .financials import (
    build_account_card as build_account_card, fin_section as fin_section,
    build_savings_goals_html as build_savings_goals_html, build_upcoming_bills_html as build_upcoming_bills_html,
    build_recent_transactions_html as build_recent_transactions_html, build_debt_tracker_html as build_debt_tracker_html,
    build_claude_review_html as build_claude_review_html, build_market_overview_html as build_market_overview_html,
    build_finance_links_html as build_finance_links_html, build_networth_chart_html as build_networth_chart_html,
    build_claude_chat_html as build_claude_chat_html,
    ICON_PIE as ICON_PIE, ICON_ACCOUNTS as ICON_ACCOUNTS, ICON_BVA as ICON_BVA,
    ICON_TREND as ICON_TREND, ICON_CATEGORY as ICON_CATEGORY, ICON_PAYEES as ICON_PAYEES,
)
from .mail import build_mail_html as build_mail_html
from .news import build_news_html as build_news_html
from .due_soon import build_due_soon_html as build_due_soon_html, build_due_today_html as build_due_today_html
from .imessage import build_imessage_html as build_imessage_html
from .notes import build_notes_html as build_notes_html
from .system import build_system_html as build_system_html
from .contacts import build_contacts_html as build_contacts_html, build_birthdays_card as build_birthdays_card
from .today import build_today_html as build_today_html
from .events import build_events_html as build_events_html
from .journals import build_journals_html as build_journals_html
