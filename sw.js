// 农历记事本 Service Worker：离线缓存 + Web Push 推送
const CACHE = "ln-v1";
const ASSETS = [
  "./", "./index.html", "./lunar.js", "./manifest.webmanifest",
  "./icon-192.png", "./icon-512.png", "./icon-maskable-512.png", "./apple-touch-icon.png"
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((ks) =>
      Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const u = new URL(e.request.url);
  if (u.pathname.startsWith("/api/")) return; // 不缓存 API
  if (e.request.method !== "GET") return;
  e.respondWith((async () => {
    try {
      const r = await fetch(e.request);
      const c = await caches.open(CACHE);
      if (["js", "html", "webmanifest", "png"].includes(u.pathname.split(".").pop())) {
        c.put(e.request, r.clone());
      }
      return r;
    } catch (err) {
      const cached = await caches.match(e.request);
      if (cached) return cached;
      return caches.match("./index.html");
    }
  })());
});

// 后台推送：即使 PWA 关闭也会触发（需部署了支持 Web Push 的后端 server.py）
self.addEventListener("push", (e) => {
  let data = { title: "农历提醒", body: "", url: "./" };
  try { data = JSON.parse(e.data.text()); } catch (_) {}
  // iOS 对相对路径图标解析不稳定，统一用 service worker 作用域拼成绝对地址
  const scope = self.registration.scope;
  const icon = new URL("icon-512.png", scope).href;
  const badge = new URL("icon-192.png", scope).href;
  // iOS 对 requireInteraction/vibrate 支持有限，去掉它们以确保锁屏能正常显示；
  // tag + renotify 已足够让每次提醒重新弹出来，避免被系统折叠后不提示。
  e.waitUntil(
    self.registration.showNotification(data.title || "农历提醒", {
      body: data.body || "",
      icon,
      badge,
      tag: "lunar-notes",
      renotify: true,
      timestamp: Date.now(),
      data: { url: data.url || "./" },
    })
  );
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "./";
  e.waitUntil(clients.openWindow(url));
});
