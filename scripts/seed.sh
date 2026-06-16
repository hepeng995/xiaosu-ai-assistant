#!/usr/bin/env bash
# 生成种子数据：docx 样本文档（md/txt 样本已手工置于 data/samples/）
set -euo pipefail
cd "$(dirname "$0")/.."
cd apps/api

echo "===== 生成 docx 样本文档 ====="
uv run python -c "
import os
from docx import Document

os.makedirs('../../data/samples', exist_ok=True)

doc = Document()
doc.add_heading('报销制度', level=1)
doc.add_heading('发票要求', level=2)
doc.add_paragraph('报销需提供：发票原件（增值税普通发票或专用发票）、费用明细清单、部门审批单。')
doc.add_heading('审批流程', level=2)
doc.add_paragraph('员工提交报销单，直属主管审批，财务复核后打款，一般 5 个工作日到账。')
doc.add_heading('差旅报销', level=2)
doc.add_paragraph('出差交通、住宿按公司标准报销，需附行程单与发票。')
doc.save('../../data/samples/报销制度.docx')
print('已生成 报销制度.docx')
"
echo ""
echo "===== 当前样本文档 ====="
ls -la ../../data/samples/
