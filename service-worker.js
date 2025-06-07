const CACHE_NAME = "geolocation-v1";
const API_ENDPOINT = "/actualizar";

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(["/"])));
});

self.addEventListener("fetch", (event) => {
  event.respondWith(
    caches
      .match(event.request)
      .then((response) => response || fetch(event.request))
  );
});

self.addEventListener("sync", (event) => {
  if (event.tag === "send-location") {
    event.waitUntil(sendLocationFromCache());
  }
});

async function sendLocationFromCache() {
  const cache = await caches.open(CACHE_NAME);
  const responses = await cache.match("last-location");

  if (!responses) return;

  const locationData = await responses.json();

  try {
    await fetch(API_ENDPOINT, {
      method: "POST",
      body: JSON.stringify(locationData),
      headers: {
        "Content-Type": "application/json",
      },
    });
    await cache.delete("last-location");
  } catch (error) {
    console.error("Error en sync:", error);
    throw error; // Reactivará el sync event
  }
}

async function cacheLocation(location) {
  const cache = await caches.open(CACHE_NAME);
  await cache.put("last-location", new Response(JSON.stringify(location)));
}
