import { redirect } from "next/navigation";

/**
 * 根路径：直接重定向到管理后台。
 * 终端员工入口在 IM（钉钉），Web 端仅供管理员使用。
 */
export default function Home() {
  redirect("/admin");
}
