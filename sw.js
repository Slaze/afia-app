const CACHE = "afia-shell-45";
const SHELL = ["./", "./index.html", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png", "./icon-maskable.png", "./apple-touch-icon.png", "./afia-wordmark.png", "./afia-wordmark-white.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE && key !== "afia-library-1" && key !== "afia-site-1").map((key) => caches.delete(key)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("push", (event) => {
  let payload = { title: "Afia", body: "", url: "./", tag: "afia" };
  try {
    payload = Object.assign(payload, event.data ? event.data.json() : {});
  } catch (error) { /* show the plain title */ }
  event.waitUntil(self.registration.showNotification(payload.title, {
    body: payload.body || "",
    tag: payload.tag || "afia",
    data: { url: payload.url || "./" }
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "./";
  event.waitUntil(clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
    const open = list.find((client) => client.url.includes(self.location.origin));
    if (open) {
      open.focus();
      if (target.startsWith("http")) return open.navigate(target);
      return undefined;
    }
    return clients.openWindow(target);
  }));
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  if (event.request.method !== "GET" || url.pathname.startsWith("/api/")) return;
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        return response;
      })
      .catch(() => caches.match(event.request).then((hit) => {
        if (hit) return hit;
        if (/\.(png|webmanifest)$/.test(url.pathname)) return new Response("", { status: 404 });
        return caches.match("./index.html");
      }))
  );
});
