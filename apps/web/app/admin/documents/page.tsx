"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type DocumentItem } from "@/lib/api";

const STATUS_COLOR: Record<string, string> = {
  indexed: "text-green-600",
  pending: "text-yellow-600",
  indexing: "text-blue-600",
  failed: "text-red-600",
  deleted: "text-gray-400",
};

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string>("");
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.documents.list();
      setDocs(data.items);
    } catch (e) {
      setMsg(`加载失败: ${e}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const data = await api.documents.list();
        if (active) setDocs(data.items);
      } catch (e) {
        if (active) setMsg(`加载失败: ${e}`);
      }
    };
    load();
    const t = setInterval(load, 5000);
    return () => {
      active = false;
      clearInterval(t);
    };
  }, []);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setMsg(`上传中: ${file.name}`);
    try {
      await api.documents.upload(file);
      setMsg(`已上传: ${file.name}，正在索引`);
      if (fileRef.current) fileRef.current.value = "";
      refresh();
    } catch (err) {
      setMsg(`上传失败: ${err}`);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`确认删除 ${name}？`)) return;
    await api.documents.remove(id);
    setMsg(`已删除: ${name}`);
    refresh();
  };

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-bold">文档管理</h1>
        <label className="cursor-pointer rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700">
          + 上传文档
          <input
            ref={fileRef}
            type="file"
            accept=".md,.markdown,.pdf,.docx,.txt"
            className="hidden"
            onChange={handleUpload}
          />
        </label>
      </div>
      {msg && <p className="mb-3 text-sm text-gray-600">{msg}</p>}
      <table className="w-full border-collapse bg-white text-sm">
        <thead>
          <tr className="border-b text-left text-gray-500">
            <th className="p-2">文件名</th>
            <th className="p-2">类型</th>
            <th className="p-2">大小</th>
            <th className="p-2">状态</th>
            <th className="p-2">版本</th>
            <th className="p-2">操作</th>
          </tr>
        </thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d.id} className="border-b">
              <td className="p-2">{d.original_filename}</td>
              <td className="p-2">{d.file_type}</td>
              <td className="p-2">{(d.file_size / 1024).toFixed(1)} KB</td>
              <td className={`p-2 font-medium ${STATUS_COLOR[d.status] ?? ""}`}>{d.status}</td>
              <td className="p-2">v{d.version}</td>
              <td className="p-2">
                <Link className="mr-3 text-blue-600 hover:underline" href={`/admin/documents/${d.id}`}>
                  查看
                </Link>
                <button
                  className="text-red-600 hover:underline"
                  onClick={() => handleDelete(d.id, d.original_filename)}
                >
                  删除
                </button>
              </td>
            </tr>
          ))}
          {docs.length === 0 && !loading && (
            <tr>
              <td colSpan={6} className="p-8 text-center text-gray-400">
                暂无文档
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
