// ============================================================
// Supabase 客户端（只读）
// 使用匿名密钥（anon key）+ RLS 策略，浏览器端安全。
// 所有查询都是只读操作，符合数据库 RLS 配置。
// ============================================================

import { createClient } from "@supabase/supabase-js";

// 从环境变量读取（frontend/.env.local 中配置）
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

// 未配置时不创建客户端（createClient 空 URL 会直接抛错），
// 页面通过 lib/data.ts 自动降级到本地静态 JSON 数据
// 注：supabase 可能为 null，调用前需判空

export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey);

export const supabase = isSupabaseConfigured
  ? createClient(supabaseUrl, supabaseAnonKey)
  : null;
