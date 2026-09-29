"use strict";

document.addEventListener("DOMContentLoaded", async () => {
  const form = document.getElementById("add-form");
  const list = document.getElementById("sites");
  const message = document.getElementById("message");
  let sites = [];

  function normalizeHostname(input) {
    const raw = input.trim();
    if (!raw || /[\s/?#@]/.test(raw) || raw.includes("://") || raw.includes(":")) {
      throw new Error("Enter a hostname only, without a scheme, port, path, or credentials.");
    }
    let hostname;
    try {
      hostname = new URL(`https://${raw}`).hostname.toLowerCase().replace(/\.$/, "");
    } catch {
      throw new Error("Enter a valid DNS hostname.");
    }
    const labels = hostname.split(".");
    const validLabel = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;
    if (hostname.length > 253 || labels.length < 2 || labels.some((label) => !validLabel.test(label))
        || !/^[a-z]{2,63}$/.test(labels.at(-1))) {
      throw new Error("Enter a fully-qualified DNS hostname.");
    }
    return hostname;
  }

  async function loadSites() {
    const stored = await chrome.storage.local.get({ protectedSites: [] });
    sites = Array.isArray(stored.protectedSites)
      ? stored.protectedSites.filter((site) => site && typeof site.domain === "string"
          && typeof site.displayName === "string" && typeof site.enabled === "boolean")
      : [];
  }

  async function persist() {
    await chrome.storage.local.set({ protectedSites: sites });
    render();
  }

  function render() {
    list.replaceChildren();
    for (const site of sites) {
      const item = document.createElement("li");
      const summary = document.createElement("span");
      summary.textContent = `${site.displayName} — ${site.domain} (${site.enabled ? "enabled" : "disabled"})`;
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.textContent = site.enabled ? "Disable" : "Enable";
      toggle.setAttribute("aria-label", `${toggle.textContent} ${site.displayName}`);
      toggle.addEventListener("click", async () => {
        site.enabled = !site.enabled;
        await persist();
      });
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "Remove";
      remove.setAttribute("aria-label", `Remove ${site.displayName}`);
      remove.addEventListener("click", async () => {
        sites = sites.filter((candidate) => candidate.domain !== site.domain);
        await persist();
      });
      item.append(summary, toggle, remove);
      list.append(item);
    }
  }

  await loadSites();
  render();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    message.textContent = "";
    const displayName = document.getElementById("display-name").value.trim();
    try {
      const domain = normalizeHostname(document.getElementById("domain").value);
      if (!displayName || displayName.length > 80) {
        throw new Error("Display name must contain 1–80 characters.");
      }
      if (sites.some((site) => site.domain === domain)) {
        throw new Error("That exact hostname is already configured.");
      }
      sites.push({ domain, displayName, addedAt: new Date().toISOString(), enabled: true });
      await persist();
      form.reset();
      message.textContent = "Site added to this extension's local status list.";
    } catch (error) {
      message.textContent = error instanceof Error ? error.message : "Could not add site.";
    }
  });
});
