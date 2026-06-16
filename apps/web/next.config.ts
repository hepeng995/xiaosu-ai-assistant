import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 输出独立部署产物（.next/standalone），用于精简 Docker 镜像
  output: "standalone",
};

export default nextConfig;
