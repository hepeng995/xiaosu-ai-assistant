#!/usr/bin/env bash
# 生成种子数据：docx 样本文档（md/txt/pdf 样本已置于 data/samples/）
set -euo pipefail
cd "$(dirname "$0")/.."
cd apps/api

echo "===== 生成 docx 样本文档 ====="
uv run python - <<'PY'
import os

from docx import Document

os.makedirs("../../data/samples", exist_ok=True)

doc = Document()
doc.add_heading("报销制度", level=1)

doc.add_heading("适用范围", level=2)
doc.add_paragraph(
    "本制度适用于员工因公司业务产生的差旅、办公采购、客户拜访、培训会议、"
    "团队活动等费用报销。个人消费、未经审批的费用、超出预算且无合理说明的费用，"
    "原则上不予报销。"
)

doc.add_heading("发票要求", level=2)
doc.add_paragraph(
    "报销需提供发票原件或合规电子发票、费用明细清单、部门审批单。"
    "发票抬头必须为公司全称，税号填写正确，金额、日期、消费项目应与实际业务一致。"
    "电子发票需上传原始版式文件，截图、照片或重复打印件不能作为唯一凭证。"
)

doc.add_heading("审批流程", level=2)
doc.add_paragraph(
    "员工在 OA 系统提交报销单后，直属主管审批业务真实性，部门负责人确认预算，"
    "财务部门复核发票和附件。材料齐全且无异常的，一般 5 个工作日内打款；"
    "月底提交或遇到发票核验异常的，可能顺延至次月处理。"
)

doc.add_heading("差旅报销", level=2)
doc.add_paragraph(
    "出差交通、住宿、餐饮和必要市内交通可按公司标准报销。"
    "交通费用需附行程单或车票，住宿费用需附酒店水单和发票，"
    "客户拜访费用需注明客户名称、拜访目的和同行人员。"
)

doc.add_heading("特殊场景", level=2)
doc.add_paragraph(
    "客户现场紧急支持、展会旺季酒店涨价、航班延误改签等特殊场景导致超标的，"
    "员工应在报销单中说明原因并上传证明材料。主管确认业务必要性后，"
    "财务按例外流程复核。"
)

doc.add_heading("退回与补充", level=2)
doc.add_paragraph(
    "报销单被退回时，应根据财务备注补充发票、付款凭证、行程单、审批说明或费用明细。"
    "补充完成后重新提交原流程，不要重复创建多个报销单。超过 30 天未重新提交的，"
    "报销单将自动关闭。"
)

doc.add_heading("不予报销", level=2)
doc.add_paragraph(
    "个人娱乐消费、无业务关系的礼品、酒水烟草、交通违章罚款、丢失票据且无法证明真实性的费用、"
    "未经审批的高额采购，均不予报销。"
)

doc.save("../../data/samples/报销制度.docx")
print("已生成 报销制度.docx")
PY
echo ""
echo "===== 当前样本文档 ====="
ls -la ../../data/samples/
