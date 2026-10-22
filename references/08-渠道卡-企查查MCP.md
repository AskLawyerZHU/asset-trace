# 渠道卡：企查查 MCP（qcc-company）

A 层第二主力，与元典互补。**企查查强在"执行/涉诉时间线+金额"，元典强在"文书全文+法条"**。两个都连上时先跑企查查风险扫描分诊，再按命中维度下钻。

## 推荐调用顺序

1. `get_company_by_query`（名称→锁定 USCC，多候选必须交用户选定）
2. `get_company_risk_scan`（**35 项风险因子一次性分诊**，返回各维度命中数）→ 只对命中维度下钻，省调用
3. 按命中下钻明细（下表映射）
4. 与元典结果交叉，冲突标 ❗

## 工具映射（按 35 因子）

| 查询目标 | 工具 | 实战要点 |
|---|---|---|
| 风险总分诊 | get_company_risk_scan | 先跑它；0 项≠无风险，须补舆情 |
| 终本案件 | get_terminated_cases | **给执行标的+未履行金额**→可算出已履行部分；一条即可看清全部终本与金额 |
| 限制高消费 | get_high_consumption_restriction | **申请人字段=竞争债权人清单**，直接可用 |
| 立案信息 | get_case_filing_info | 给当事人角色（原告/被告/上诉人）→ 一眼判断债权面还是负债面 |
| 裁判文书 | get_judicial_documents | 给案件金额+裁判结果摘要，比元典列表信息密度高 |
| 开庭公告 | get_hearing_notice | 给案号+当事人+开庭时间，可还原诉讼时间线 |
| 法院公告 | get_court_notice | **"起诉状副本及开庭传票"公告=对方下落不明/失联信号**；"裁判文书"公告=可能缺席判决 |
| 失信 / 被执行人 | get_dishonest_info / get_judgment_debtor_info | 有则直接可用 |
| 限高/终本/立案/文书的"历史"版本 | get_historical_* / get_executive_historical_* | 当前在册查不到时再查历史（已移出名单） |
| 股权冻结/出质 | get_equity_freeze / get_equity_pledge_info | 已冻结=他人先手 |
| 司法拍卖/询价评估 | get_judicial_auction / get_valuation_inquiry | 按名搜拍品与流拍 |
| 破产重整/清算/简易注销/注销备案 | get_bankruptcy_reorganization / get_liquidation_info / get_simple_cancellation_info / get_cancellation_record_info | 变更与退出线必查 |
| 欠税公告 | get_tax_arrears_notice | 欠税优先于普通债权，影响受偿预期 |
| 对外投资/变更/年报 | get_external_investments / get_change_records / get_annual_reports | 减资、股东变化、实缴口径 |
| 知产 | get_trademark_info / get_patent_info / get_software_copyright_info | 与元典口径交叉 |
| 招投标/资质 | get_bidding_info / get_qualifications | 在履行合同=到期债权线索 |
| 自然人（董监高）风险 | get_executive_* 系列（需 企业+personName 双锚定） | **只能查"某公司的高管/股东个人"，不能按姓名直接查自然人被执行人** |

## 实测发现的边界（2026-10-22 两案实测）

1. **无自然人被执行人入口**：全部工具以企业为主体；自然人被执行人无法直接查（get_executive_* 必须绑定企业+姓名）。自然人线仍须走执行网四库人工 + 文书库同名甄别。
2. **立案/文书有滞后**：实测 2025 年新立案的追加案未进"立案信息"与"裁判文书"（裁判文书停留在 2023 年），只在**开庭公告/法院公告**里出现 → 时间线必须三表合看（立案+开庭+公告）。
3. **风险扫描 0 项字段勿当无风险**：未含舆情，且历史已移出记录在 historical 系列里。
4. 金额口径：终本给"执行标的/未履行"，两者差额=已履行部分，报告里要写清楚，别把标的全额当未受偿。
5. 调用成本：一次 scan + 按命中下钻，避免 35 个工具全跑。

## 与元典的分工建议

| 需要 | 首选 |
|---|---|
| 执行/终本/限高/公告/时间线 + 金额 | 企查查 |
| 文书全文、法条核验、语义检索类案 | 元典 |
| 工商股东/年报/知产明细 | 两源交叉，冲突标 ❗ |
