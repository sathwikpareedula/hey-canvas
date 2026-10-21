import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "UTA Academic Copilot",
    short_name: "Hey Canvas",
    description: "Academic assistant for deadlines, materials, and study",
    start_url: "/",
    display: "standalone",
    background_color: "#0a0a0a",
    theme_color: "#0064b1",
    icons: [
      {
        src: "/icons/icon-192.svg",
        sizes: "192x192",
        type: "image/svg+xml",
      },
      {
        src: "/icons/icon-512.svg",
        sizes: "512x512",
        type: "image/svg+xml",
      },
    ],
  };
}
