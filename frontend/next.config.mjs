/** @type {import('next').NextConfig} */
const nextConfig = {
  // Standalone output keeps the runtime image small (docker/frontend.Dockerfile).
  output: "standalone",
  reactStrictMode: true,
  // The frontend never renders a secret. All API calls are same-site to the API
  // origin with the session cookie; no database key ever reaches the browser (Q-4).
  poweredByHeader: false,
};
export default nextConfig;
