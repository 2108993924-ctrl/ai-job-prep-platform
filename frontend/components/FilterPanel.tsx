// ============================================================
// 筛选面板（公司详情页使用）
// 支持按 岗位类型 / 技术栈 / 业务领域 三个维度筛选岗位
// ============================================================

// 筛选条件结构（与公司详情页共享）
export interface FilterState {
  jobType: string;
  techStack: string;
  businessDomain: string;
}

// 岗位类型选项（PRD 定义的五类）
const JOB_TYPES = ["AI算法", "AI工程", "AI产品", "AI应用", "数据科学"];

interface Props {
  filters: FilterState;
  onChange: (filters: FilterState) => void;
  techStacks: string[];        // 该公司全部技术栈（下拉选项）
  businessDomains: string[];   // 该公司全部业务领域（下拉选项）
}

export default function FilterPanel({ filters, onChange, techStacks, businessDomains }: Props) {
  // 更新单个筛选条件（其余保持）
  function set(key: keyof FilterState, value: string) {
    onChange({ ...filters, [key]: value });
  }

  // 是否处于筛选状态（用于显示"清除筛选"按钮）
  const hasFilter = Boolean(filters.jobType || filters.techStack || filters.businessDomain);

  return (
    <div className="mb-5 rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-end gap-4">
        {/* ===== 岗位类型筛选 ===== */}
        <div>
          <label className="mb-1 block text-xs text-slate-400">岗位类型</label>
          <select
            value={filters.jobType}
            onChange={(e) => set("jobType", e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
          >
            <option value="">全部</option>
            {JOB_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>

        {/* ===== 技术栈筛选 ===== */}
        <div>
          <label className="mb-1 block text-xs text-slate-400">技术栈</label>
          <select
            value={filters.techStack}
            onChange={(e) => set("techStack", e.target.value)}
            className="max-w-[180px] rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
          >
            <option value="">全部</option>
            {techStacks.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>

        {/* ===== 业务领域筛选 ===== */}
        <div>
          <label className="mb-1 block text-xs text-slate-400">业务领域</label>
          <select
            value={filters.businessDomain}
            onChange={(e) => set("businessDomain", e.target.value)}
            className="max-w-[180px] rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
          >
            <option value="">全部</option>
            {businessDomains.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </div>

        {/* ===== 清除筛选 ===== */}
        {hasFilter && (
          <button
            onClick={() => onChange({ jobType: "", techStack: "", businessDomain: "" })}
            className="rounded-lg px-3 py-1.5 text-sm text-brand-600 hover:bg-brand-50"
          >
            清除筛选 ✕
          </button>
        )}
      </div>
    </div>
  );
}
