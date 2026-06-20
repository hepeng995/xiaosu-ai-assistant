import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** 合并 Tailwind 类名（clsx + tailwind-merge，去重冲突）。 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
