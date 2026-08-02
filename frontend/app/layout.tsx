// ============================================================
// 全局布局：导航栏 + 页脚（含数据所有权声明）
// ============================================================

import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import Footer from "@/components/Footer";

// SEO 元信息（部署后标题会显示在浏览器标签页与搜索引擎）
export const metadata: Metadata = {
  title: "AI 岗位备考平台 | 招聘要求聚合与面试准备",
  description:
    "聚合各企业官方招聘页公开的 AI 岗位 JD，用 AI 结构化为项目能力要求、技术栈与针对性面试题，帮助求职者从零备考。",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="flex min-h-screen flex-col">
        {/* ===== 顶部导航栏 ===== */}
        <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur">
          <nav className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
            {/* Logo 与名称 */}
            <Link href="/" className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">
                AI
              </span>
              <span className="text-lg font-bold text-slate-800">AI 岗位备考平台</span>
            </Link>

            {/* 导航链接 */}
            <div className="flex items-center gap-4 text-sm">
              <Link href="/" className="text-slate-600 hover:text-brand-600">
                公司列表
              </Link>
              <Link
                href="/search"
                className="rounded-full border border-slate-300 px-4 py-1.5 text-slate-600 hover:border-brand-500 hover:text-brand-600"
              >
                搜索技术栈
              </Link>
            </div>
          </nav>
        </header>

        {/* ===== 页面主体 ===== */}
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">{children}</main>

        {/* ===== 页脚（含 PRD 要求的数据所有权声明）===== */}
        <Footer />
      </body>
    </html>
  );
}
