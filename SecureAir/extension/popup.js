"use strict";

document.addEventListener("DOMContentLoaded", async () => {
  const siteNode = document.getElementById("site");
  const statusNode = document.getElementById("status");
  const manageButton = document.getElementById("manage");

  manageButton.addEventListener("click", () => chrome.runtime.openOptionsPage());

  try {
    // The popup is opened by the user; activeTab grants access only for this check.
    const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    const url = new URL(tab?.url || "");
    if (!["http:", "https:"].includes(url.protocol)) {
      siteNode.textContent = "This page is not a supported website.";
      statusNode.textContent = "No site status";
      return;
    }

    const hostname = url.hostname.toLowerCase();
    const stored = await chrome.storage.local.get({ protectedSites: [], activityEvents: [] });
    const protectedSites = Array.isArray(stored.protectedSites) ? stored.protectedSites : [];
    const entry = protectedSites.find((site) => site && site.domain === hostname);
    siteNode.textContent = entry ? `${entry.displayName} (${hostname})` : hostname;
    statusNode.textContent = entry
      ? (entry.enabled ? "Protection enabled (status preference only)" : "Protection disabled")
      : "Not configured";

    // Store only an explicit check of an enabled, exact-host entry. Never store URL paths,
    // query strings, page content, or checks for sites that were not explicitly enabled.
    if (entry?.enabled === true) {
      try {
        const events = Array.isArray(stored.activityEvents) ? stored.activityEvents : [];
        const nextEvents = [
          ...events,
          { timestamp: new Date().toISOString(), hostname, status: "enabled_status_checked" },
        ].slice(-200);
        await chrome.storage.local.set({ activityEvents: nextEvents });
      } catch {
        statusNode.textContent += " (local event could not be saved)";
      }
    }
  } catch {
    siteNode.textContent = "Unable to read this tab.";
    statusNode.textContent = "Status unavailable";
  }
});
