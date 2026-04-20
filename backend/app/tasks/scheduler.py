# FILE: backend/app/tasks/scheduler.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: Background task scheduler — recurring maintenance jobs started during FastAPI lifespan
#   SCOPE: APScheduler-based job registration and execution: subscription expiry, VPN stats, anomaly detection, cleanup, reporting
#   DEPENDS: M-001 (database), M-003 (vpn models/manager), M-004 (billing models), M-023 (handshake monitor)
#   LINKS: M-008 (background-tasks), M-004 (billing), M-003 (vpn), V-M-008
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   TaskScheduler - APScheduler wrapper (start/stop methods)
#   task_scheduler - Global singleton scheduler instance
#   check_subscription_expiry - Hourly job: deactivate expired subscriptions and VPN clients
#   update_vpn_stats - Every 5 min: update client stats from AmneziaWG
#   daily_cleanup - Daily at 3AM: clean old failed payments
#   detect_handshake_anomalies - Configurable interval: observe peer handshakes for anomaly signals
#   weekly_report - Weekly on Monday 9AM: generate subscription stats (placeholder)
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v3.1.0 - Made handshake anomaly scan interval configurable for anti-ping-pong detection
#   LAST_CHANGE: v2.8.0 - Added full GRACE MODULE_CONTRACT and MODULE_MAP per GRACE governance protocol
# END_CHANGE_SUMMARY
#
"""
Background tasks scheduler.

MODULE_CONTRACT
- PURPOSE: Own recurring maintenance jobs started during FastAPI lifespan — subscription expiry, VPN stats, anomaly detection, cleanup, and reporting.
- SCOPE: APScheduler-based job registration and execution; tasks may mutate subscriptions, VPN stats, and cleanup state without direct user requests.
- DEPENDS: M-001 DB session factory, M-003 VPN peer management, M-004 billing subscriptions, M-012 handshake monitor.
- LINKS: M-004 billing-subscription, M-003 VPN clients, M-012 background-tasks, V-M-012.

MODULE_MAP
- TaskScheduler: APScheduler wrapper managing recurring maintenance jobs.
  - start: Registers all jobs and starts the scheduler (called once at lifespan startup).
  - stop: Shuts down the scheduler.
- check_subscription_expiry: Checks for expired subscriptions and deactivates them.
- update_vpn_stats: Updates VPN client statistics from AmneziaWG.
- daily_cleanup: Cleans old failed payments and performs maintenance.
- detect_handshake_anomalies: Observes live peer handshakes and records soft anomaly signals.
- weekly_report: Generates weekly subscription stats (placeholder for notification delivery).

CHANGE_SUMMARY
- v2.8.0: Added GRACE-lite runtime markup with START_BLOCK/END_BLOCK for each class and task function.
"""
# <!-- GRACE: module="M-008" contract="scheduler" role="RUNTIME" MAP_MODE="EXPORTS" -->

from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from app.core.config import settings
from app.core.database import async_session_maker


# <!-- START_BLOCK: TaskScheduler -->
class TaskScheduler:
    """Scheduler for background tasks."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    # <!-- START_BLOCK: TaskScheduler.start -->
    def start(self):
        """Start the scheduler."""
        # Lifespan startup calls this once per process. Jobs must be idempotent enough
        # to tolerate restarts, but duplicate schedulers across multiple app instances
        # would still require operational care.
        # Subscription expiry check - every hour
        self.scheduler.add_job(
            check_subscription_expiry,
            IntervalTrigger(hours=1),
            id="check_subscription_expiry",
            replace_existing=True,
        )

        # VPN stats update - every 5 minutes
        self.scheduler.add_job(
            update_vpn_stats,
            IntervalTrigger(minutes=5),
            id="update_vpn_stats",
            replace_existing=True,
        )

        self.scheduler.add_job(
            detect_handshake_anomalies,
            IntervalTrigger(seconds=settings.anti_abuse_scan_interval_seconds),
            id="detect_handshake_anomalies",
            replace_existing=True,
        )

        # Daily cleanup - at 3 AM
        self.scheduler.add_job(
            daily_cleanup,
            CronTrigger(hour=3, minute=0),
            id="daily_cleanup",
            replace_existing=True,
        )

        # Weekly report - Monday at 9 AM
        self.scheduler.add_job(
            weekly_report,
            CronTrigger(day_of_week="mon", hour=9, minute=0),
            id="weekly_report",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info("[TASKS] Scheduler started")
    # <!-- END_BLOCK: TaskScheduler.start -->

    # <!-- START_BLOCK: TaskScheduler.stop -->
    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("[TASKS] Scheduler stopped")
    # <!-- END_BLOCK: TaskScheduler.stop -->
# <!-- END_BLOCK: TaskScheduler -->


# Global scheduler
task_scheduler = TaskScheduler()


# ==================== Tasks ====================

# <!-- START_BLOCK: check_subscription_expiry -->
async def check_subscription_expiry():
    """
    Check for expired subscriptions and deactivate them.
    """
    logger.info("[TASKS] Checking subscription expiry...")

    async with async_session_maker() as session:
        from sqlalchemy import select, update
        from app.billing.models import Subscription, SubscriptionStatus

        now = datetime.now(timezone.utc)

        # Find expired but still active subscriptions
        result = await session.execute(
            select(Subscription)
            .where(
                Subscription.is_active == True,
                Subscription.expires_at <= now,
            )
        )
        expired = result.scalars().all()

        for sub in expired:
            sub.is_active = False
            sub.status = SubscriptionStatus.EXPIRED

            # Deactivate VPN client
            from app.vpn.models import VPNClient
            from app.vpn.amneziawg import wg_manager

            client_result = await session.execute(
                select(VPNClient).where(
                    VPNClient.user_id == sub.user_id,
                    VPNClient.is_active == True,
                )
            )
            client = client_result.scalar_one_or_none()

            if client:
                client.is_active = False
                await wg_manager.remove_peer(client.public_key)
                from app.vpn.models import VPNServer
                server_result = await session.execute(
                    select(VPNServer).where(VPNServer.id == client.server_id)
                )
                server = server_result.scalar_one_or_none()
                if server and server.current_clients > 0:
                    server.current_clients -= 1
                    await session.flush()

            logger.info(f"[TASKS] Subscription {sub.id} expired for user {sub.user_id}")

        await session.commit()

        if expired:
            logger.info(f"[TASKS] Deactivated {len(expired)} expired subscriptions")
# <!-- END_BLOCK: check_subscription_expiry -->


# <!-- START_BLOCK: update_vpn_stats -->
async def update_vpn_stats():
    """
    Update VPN client statistics from AmneziaWG.
    """
    logger.debug("[TASKS] Updating VPN stats...")

    async with async_session_maker() as session:
        from sqlalchemy import select
        from app.vpn.models import VPNClient
        from app.vpn.amneziawg import wg_manager

        result = await session.execute(
            select(VPNClient).where(VPNClient.is_active == True)
        )
        clients = result.scalars().all()

        # Get peer stats
        stats = await wg_manager.get_peer_stats()

        updated = 0
        for client in clients:
            if client.public_key in stats:
                peer_stats = stats[client.public_key]
                client.total_upload_bytes = peer_stats["upload"]
                client.total_download_bytes = peer_stats["download"]
                client.last_handshake_at = peer_stats["last_handshake"]
                client.updated_at = datetime.now(timezone.utc)
                updated += 1

        await session.commit()

        if updated > 0:
            logger.debug(f"[TASKS] Updated stats for {updated} clients")
# <!-- END_BLOCK: update_vpn_stats -->


# <!-- START_BLOCK: daily_cleanup -->
async def daily_cleanup():
    """
    Daily cleanup tasks.
    """
    logger.info("[TASKS] Running daily cleanup...")

    async with async_session_maker() as session:
        from sqlalchemy import delete
        from datetime import timedelta

        # Clean old failed payments (older than 30 days)
        from app.billing.models import Payment, PaymentStatus

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)

        result = await session.execute(
            delete(Payment)
            .where(
                Payment.status == PaymentStatus.FAILED,
                Payment.created_at < cutoff,
            )
        )

        await session.commit()

        logger.info(f"[TASKS] Cleaned {result.rowcount} old failed payments")
# <!-- END_BLOCK: daily_cleanup -->


# <!-- START_BLOCK: detect_handshake_anomalies -->
async def detect_handshake_anomalies():
    """
    Observe live peer handshakes and record soft anomaly signals.
    """
    logger.debug("[TASKS] Detecting handshake anomalies...")

    async with async_session_maker() as session:
        from app.vpn.handshake_monitor import HandshakeAnomalyMonitor

        monitor = HandshakeAnomalyMonitor(session)
        processed = await monitor.scan_active_peers()
        await session.commit()

        if processed > 0:
            logger.debug(f"[TASKS] Observed handshake metadata for {processed} device-bound peers")
# <!-- END_BLOCK: detect_handshake_anomalies -->


# <!-- START_BLOCK: weekly_report -->
async def weekly_report():
    """
    Generate weekly report.
    """
    logger.info("[TASKS] Generating weekly report...")

    async with async_session_maker() as session:
        from app.billing.service import BillingService

        service = BillingService(session)
        stats = await service.get_subscription_stats()

        # TODO: Send report via email or Telegram
        logger.info(f"[TASKS] Weekly stats: {stats}")
# <!-- END_BLOCK: weekly_report -->
