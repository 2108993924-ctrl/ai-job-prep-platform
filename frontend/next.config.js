/** @type {import('next').NextConfig} */
const nextConfig = {
  // 静态导出模式：可直接部署到 GitHub Pages / 任意静态托管
  // 若部署 Vercel 可改为 false（动态渲染 SSR）
  output: "export",
  images: { unoptimized: true },
};

module.exports = nextConfig;
