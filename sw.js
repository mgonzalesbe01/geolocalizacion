self.addEventListener("sync", (event) => {
  if (event.tag === "update-location") {
    event.waitUntil(sendLocationToServer());
  }
});

async function sendLocationToServer() {
  // Aquí implementarías la lógica para enviar la ubicación
  const location = await getLastKnownLocation();
  return fetch("/actualizar", {
    method: "POST",
    body: `codigo=${location.codigo}&latitud=${location.lat}&longitud=${location.lon}`,
  });
}
