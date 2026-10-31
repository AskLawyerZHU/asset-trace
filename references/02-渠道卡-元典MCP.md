# 渠道卡：法律数据库 MCP（以元典 yuandian 为例）

A 层主力。接口名以实际环境注册的 MCP 工具为准（v1.2 起按实测注册清单对齐）；本卡记录"基线 ID → 接口 → 关键词策略 → 已知盲区"。其他同类数据库 MCP 参照本卡自行映射。

## 两族接口划分（★v1.6.1，决定自然人能不能查）

| 接口族 | 锚定方式 | 覆盖 | 自然人可用性 |
|---|---|---|---|
| **企业锚定族**（约 30 个：`yuandian_get_company_*` / `list_company_*`） | 企业名/信用代码/企业 ID | 工商、年报、变更、涉诉明细、执行、失信、知产、行政、欠税、担保等 | ❌ 不可用——无任何自然人参数 |
| **姓名锚定族**（约 10 个：`yuandian_search_judicial_cases` / `semantic_search_cases` / `search_authoritative_cases` / `get_case_detail` 及法条法规族） | 姓名/案情描述/法条关键词 | 涉诉史、执行裁定全文、终本认定、刑事与服刑记录、对外债权、类案与法条 | ✅ **按姓名直查，是自然人机器可查的主力源**（实测金根宝核对表 12 行贡献 6 行 ✅） |

**能力边界速记**：企查查完全无案例法条检索能力；元典案例法条检索全套独有（案例检索常规/语义/权威 + 法规法条检索与详情 + 免费政策库 + 证券法规/监管案例/上市公司公告）。法人场景两源互补，自然人场景元典文书库先行。

## 接口映射（按基线 ID，2026-10-29 实测环境对齐）

### 法人线 F1–F12

| 基线 | 查询目标 | 接口 | 关键词/参数策略 |
|---|---|---|---|
| F1 | 工商登记与状态 | `yuandian_search_companies` → `yuandian_get_company_basic_profile` / `get_company_profile` | 先名称检索锁定 USCC 再取档案；**登记状态"吊销/注销/存续"是主路径分岔点** |
| F2 | 企业年报 | `yuandian_get_company_annual_report` | **重点：实缴出资额、认缴期限、股东变化**——实缴 0 + 认缴远期＝追加股东方向 |
| F3 | 股东与一层持股 | basic/profile 的股东块 | 记认缴/实缴/出资时间；"出资比例 0.0"多为数据缺陷，以年报为准 |
| F4 | 对外投资穿透 | `yuandian_list_company_external_investments` | 追到第二层（子公司→再调 basic_profile）；GP/LP 身份要区分 |
| F5 | 裁判文书 | `yuandian_search_judicial_cases`（`litigating_company` 涉诉企业参数）+ `yuandian_list_company_litigation_document_summaries` + `yuandian_get_company_litigation_statistics` | **被告面/原告面分查**：原告面＝对外债权线索；statistics 先看总量再决定翻页深度 |
| F6 | 执行案件（在册） | `yuandian_list_company_judicial_enforcement_records` ★v1.2 补录 | 被执行人记录直接可查；与企查查 `get_judgment_debtor_info` 交叉 |
| F7 | 终本案件 | 同上（终本标记）+ 企查查 `get_terminated_cases` | 元典可能漏终本 → 以企查查终本金额为准，单源无记录不作反证 |
| F8 | 失信被执行人 | `yuandian_list_company_judgment_defaulter_records` ★ | 与执行网交叉验证 |
| F9 | 限制高消费 | 元典无 → 企查查 `get_high_consumption_restriction` | 申请人字段＝竞争债权人清单 |
| F10 | 股权冻结/出质 | `yuandian_list_company_equity_freezes` / `yuandian_list_company_equity_pledges` | 记冻结法院、金额、期限；已冻结＝他人先手 |
| F11 | 知识产权 | `yuandian_list_company_patents` / `_trademarks` / `_software_copyrights` / `_work_copyrights` | 数量+法律状态；"终止/无效"要记 |
| F12 | 变动与公告 | `yuandian_list_company_registration_changes` / `_court_announcements` / `_court_hearing_notices` / `_abnormal_operations` / `_serious_violations` | 开庭案由含"变更追加被执行人"＝有竞争债权人在追；减资公告单独看 |

### 统计总览（第一调分诊，★v1.6 实测补录）

`yuandian_get_company_statistics_overview`（uscc 或 company_id）：一次返回 20+ 模块聚合统计与 Top20 摘要（商标/专利/作品著作权/软著、失信/被执行/开庭/法院公告、经营异常/严重违法/行政处罚/欠税、对外投资/股权出质/股权冻结/对外担保、变更记录、网站备案）。

**用法**：Step 3 开跑时**先调它**，用聚合计数做两件事——①找出非零模块决定下钻优先级（省调用）；②与企查查 risk_scan 交叉分诊。**它是 Top20 摘要不是全量明细**，下钻仍要调对应列表接口。

**口径纪律**：聚合计数与列表明细、与企查查可能不一致（实测：商标 422 vs 企查查 415；失信 4 vs 企查查 7）——引用计数必须标库，冲突标 ❗ 两说并陈。

### 法人扩展项（按需启用）

| 扩展 | 接口 | 用法 |
|---|---|---|
| E5 欠税与税收违法 | `yuandian_list_company_tax_arrears` ★ | 欠税优先于普通债权，直接影响受偿预期 |
| E5 税收/行政 | `yuandian_list_company_administrative_penalties` | 环保/税务/市监处罚＝或有负债 |
| 隐性负债 | `yuandian_list_company_external_guarantees` ★（对外担保） | 担保余额＝隐性债务，评估"净资产"必查 |
| E7 送达公告 | `_court_announcements` 过滤"公告送达" | 下落不明信号 |
| 经营痕迹 | `yuandian_list_company_website_filings` | 网站/APP/小程序归属 → 经营收入线索 |
| 破产 | `yuandian_search_judicial_cases`（case_category=强制清算与破产案件） | 破产受理状态决定执行程序走向 |

### 自然人线 N1–N9（姓名锚定族，元典是主力源——v1.6.1 修正）

> ⚠️ 旧表述"自然人检索只能靠企查查"**错误**：那是企查查单侧的限制。元典姓名锚定族按姓名直查，两份自然人报告实测中贡献了过半的 ✅ 行。正确分工见 08 卡"自然人检索三源三层分工"。

| 基线 | 接口 | 说明 |
|---|---|---|
| N1 同名甄别 | `yuandian_search_judicial_cases`（keywords=姓名） | 按出生日期/户籍/案由逐一排除；**无身份锚点时全线中止** |
| N2 文书双向 | 同上 + `yuandian_search_authoritative_cases` | province/court_name 过滤收窄 |
| N3 执行案件 | `yuandian_search_judicial_cases`（case_category=执行案件）★ | **实测自然人执行裁定书可按名检索**，含终本裁定全文——v1.2 明确此路径 |
| N4 终本 | 同上（case_closure_method=终结本次执行） | 终本裁定常载"未履行金额"与"无财产"认定 |
| N9 对外债权 | 同上（case_category=民事案件，原告面） | 民事 0 件＝无对外债权，如实登记 |
| N5/N6/N7 | 元典无自然人失信/限高/边控库 | 走企查查任职锚定（见 08 卡）或执行网人工 |

### 语义检索与法条

- `yuandian_semantic_search_cases`：自由描述案情检索类案（找"追股东"先例时用）
- `yuandian_search_laws_and_regulations` / `get_legal_article_detail`：法条取原文，记 validity_status 与施行日

## 已知盲区与纪律（实战踩坑沉淀）

1. **执行类数据缺失**：曾出现文书库查无执行记录、实际存在 2 件终本 + 追加案件 → 执行线必须与 B 层执行网四库交叉验证。
2. **子公司状态冲突**：同一子公司在不同源显示"吊销 vs 存续"→ 标 ❗冲突，以公示系统人工复核为终。
3. **注册资本口径差**：登记注册资本与年报认缴合计不一致 → 可能减资或未披露股东，列入"调工商内档"待办，不下"抽逃出资"结论。
4. **姓名字段**：自然人检索必须先甄别同名（见 04 文件），甄别记录保留被排除案例与理由。
5. **涉诉文书列表不全**：实测某公司文书接口仅返回 6 篇，而第三方库显示执行案件 8+ 件 → 涉诉线必须与第三方库诉讼档案时间线交叉，元典列表作"已核子集"。
6. **自然人无企业锚定族接口**：企业锚定族（任职/持股/失信/限高/边控）对自然人不可用 → 任职走企查查任职锚定法，失信/限高/边控走执行网人工。**但姓名锚定族（案例文书库）按姓名可查且是主力**，勿因本条误判元典"查不了自然人"。
7. **profile"出资比例 0.0"多为数据缺陷**：以年报认缴数据为准，勿当真 0 出资结论来源。
8. **法条不引记忆**：涉及追加/撤销/加速到期等法条时用法条接口取现行有效版本原文。
9. **检索深度**：`search_judicial_cases` 默认 top_k=10，跑基线必须显式给 top_k（建议 30–50）或用分页，否则静默截断造成"假 0 件"。
10. **聚合统计≠明细≠第三方库**：statistics_overview 与各列表接口、与企查查之间存在计数口径差（2026-10-31 实测：商标 422/415、失信 4/7），以明细接口+人工复核为终，计数引用标库。

## 降级规则

- MCP 不可用（未配置/方法失效）：对应线改用官方公开源 + 网页检索，标 `✅已核验（替代源）` 或 `⏳待补`。
- 接口报错：重试一次，仍失败则在核对表标 ⏳ 并记录报错关键词，不阻塞其他线。
