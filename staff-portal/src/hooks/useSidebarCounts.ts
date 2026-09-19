import { useCallback, useEffect, useState } from 'react';
import { notificationService } from '../services/apiService';

/** Sidebar modules that surface unread staff notifications. */
export type SidebarBadgeKey = 'applications' | 'appointments';

export interface SidebarCounts {
  applications: number;
  appointments: number;
}

/**
 * The notification categories the backend already creates for staff
 * (`notification_type` values set by apps.applications / apps.appointments).
 */
const NOTIFICATION_TYPES: Record<SidebarBadgeKey, string> = {
  applications: 'application',
  appointments: 'appointment',
};

const REFRESH_INTERVAL_MS = 10_000;

/**
 * Unread notification counts for the staff sidebar.
 *
 * Counts are derived from the existing unread notifications of the
 * authenticated staff user (never from application/appointment records), and
 * are re-read from the existing notification API on a short interval so new
 * notifications show up without a full page reload.
 */
export function useSidebarCounts() {
  const [counts, setCounts] = useState<SidebarCounts>({ applications: 0, appointments: 0 });

  const refreshCounts = useCallback(async () => {
    try {
      const unread = await notificationService.listUnread();
      const next: SidebarCounts = { applications: 0, appointments: 0 };
      for (const notification of unread) {
        if (notification.notification_type === NOTIFICATION_TYPES.applications) {
          next.applications += 1;
        } else if (notification.notification_type === NOTIFICATION_TYPES.appointments) {
          next.appointments += 1;
        }
      }
      setCounts(next);
    } catch (err) {
      // Keep the last known counts; the next poll retries.
      console.error('Failed to load unread notification counts:', err);
    }
  }, []);

  useEffect(() => {
    refreshCounts();
    const interval = setInterval(refreshCounts, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refreshCounts]);

  /**
   * Marks only this module's unread notifications as read, reusing the existing
   * per-notification read endpoint, then re-reads the counts from the backend so
   * the backend read state stays the single source of truth.
   */
  const markModuleRead = useCallback(
    async (key: SidebarBadgeKey) => {
      try {
        const unread = await notificationService.listUnread();
        const relevant = unread.filter(
          (notification) => notification.notification_type === NOTIFICATION_TYPES[key],
        );
        await Promise.all(relevant.map((notification) => notificationService.markRead(notification.id)));
        await refreshCounts();
      } catch (err) {
        console.error('Failed to mark module notifications as read:', err);
      }
    },
    [refreshCounts],
  );

  return { counts, markModuleRead, refreshCounts };
}