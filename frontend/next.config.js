/** @type {import('next').NextConfig} */
function backendUrl() {
  if (process.env.BACKEND_URL) return process.env.BACKEND_URL.replace(/\/$/, "");
  const pub = process.env.NEXT_PUBLIC_API_URL;
  if (pub) return pub.replace(/\/api\/?$/, "").replace(/\/$/, "");
  return "http://127.0.0.1:8001";
}

const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    const target = backendUrl();
    return [
      {
        source: "/backend-api/:path*",
        destination: `${target}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
