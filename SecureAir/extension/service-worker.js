"use strict";

// Keep extension-local settings initialized. No tab listeners, URL collection,
// page scripts, network calls, or browsing history are used.
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.get({ protectedSites: [] }, ({ protectedSites }) => {
    if (!Array.isArray(protectedSites)) {
      chrome.storage.local.set({ protectedSites: [] });
    }
  });
});
