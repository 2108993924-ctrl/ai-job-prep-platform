// ============================================================
// 页脚组件（全局布局底部）
// 包含 PRD 要求的「数据所有权声明」：
//   JD 原文版权归各企业所有，本平台仅做结构化整理与学习用途
// ============================================================

export default function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white">
      <div className="mx-auto max-w-6xl px-4 py-6">
        {/* 数据所有权声明（合规要求，不可删除） */}
        <p className="text-center text-xs leading-5 text-slate-400">
          JD 原文版权归各企业所有，本平台仅做结构化整理与学习用途。
        </p>
        <p className="mt-2 text-center text-xs text-slate-300">
          数据来源：各企业官方招聘页（仅公开岗位描述，不采集任何个人信息）· 每日自动更新
        </p>
      </div>
    </footer>
  );
}
