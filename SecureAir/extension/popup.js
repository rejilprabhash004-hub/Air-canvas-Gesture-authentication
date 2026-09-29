document.addEventListener("DOMContentLoaded", async () => {
  const siteNode = document.getElementById("site");
  const statusNode = document.getElementById("status");
  const manageButton = document.getElementById("manage");

  manageButton.addEventListener("click", () => chrome.runtime.openOptionsPage());

  try {
    // activeTab is granted only after the user clicks the extension action.
    const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    const url = new URL(tab?.url || "");
    if (!["http:", "https:"].includes(url.protocol)) {
      siteNode.textContent = "This page is not a supported website.";
      statusNode.textContent = "No site status";
      return;
    }

    const { protectedSites = [] } = await chrome.storage.local.get({ protectedSites: [] });
    const entry = Array.isArray(protectedSites)
      ? protectedSites.find((site) => site && site.domain === url.hostname.toLowerCase())
      : undefined;
    siteNode.textContent = entry ? `${entry.displayName} (${url.hostname})` : url.hostname;
    statusNode.textContent = entry
      ? (entry.enabled ? "Protection enabled (status preference only)" : "Protection disabled")
      : "Not configured";
  } catch {
    siteNode.textContent = "Unable to read this tab.";
    statusNode.textContent = "Status unavailable";
  }
});
