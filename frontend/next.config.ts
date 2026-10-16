import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // 产出 .next/standalone：容器镜像里只带运行必需的依赖，不用把整个 node_modules 塞进去
  output: 'standalone',

  // 生产关闭浏览器端 sourcemap，减小产物体积
  productionBrowserSourceMaps: false,

  // 图标库按需导入，降低打包体积
  experimental: {
    optimizePackageImports: ['lucide-react'],
  },
};

export default nextConfig;
