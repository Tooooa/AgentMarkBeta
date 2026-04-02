# 弱非对称解码集成 — 执行计划 (RankStego)

> **ADR 关联**：[ADR-004: 集成弱非对称水印方案 (RankStego)](../../design-docs/decision-log.md#adr-004)
> **决策确认**：编解码都换 RankStego ｜ 统一 Meteor DRBG ｜ 行为级场景 ｜ 纯算法移植 ｜ API 向后兼容

## 1. 架构目标
将 `weakly-asy-stego-E7FC` 中的 RankStego 弱非对称解码能力引入 AgentMark，解决对称差分方案对“概率数值精确一致”的强依赖，实现在仅需“排名顺序一致”即可可靠解码的能力。

## 2. 核心改动

### 2.1 DRBG 体系更新
- **Legacy DRBG**: 原有的 Counter 模式 DRBG 重命名为 `DRBG_Legacy`，仅供 `differential` 模式向后兼容。
- **Meteor DRBG**: 引入 Meteor 风格的 HMAC-SHA512 reseed 模式 DRBG 作为 `rank` 模式及未来默认实现。

### 2.2 核心算法引入 (`agentmark/core/watermark_sampler.py`)
- **Dist 类**: 轻量级概率分布封装，支持排序和 top-k。
- **RankEncStep/RankDecStep**: 基于排名二叉分裂的递归编解码逻辑。
- **适配器层**: 增加 `sample_behavior_rank` 和 `rank_based_decoder` 对接 AgentMark 的行为级(Action-level)接口。

### 2.3 SDK 封装 (`agentmark/sdk/watermarker.py`)
- **algorithm 参数**: 支持 `algorithm='rank'`（默认）和 `algorithm='differential'`。
- **透明切换**: 在 `sample()` 和 `decode()` 方法中根据配置自动路由。

## 3. 实施 Phase - **已完成 (2026-03-31)**

| Phase | 内容 | 目标文件 | 状态 |
|-------|------|----------|------|
| **P1** | 基础组件：Meteor DRBG + Dist 类 | `core/watermark_sampler.py` | ✅ |
| **P2** | 核心算法：RankEncStep 编解码递归逻辑 | `core/watermark_sampler.py` | ✅ |
| **P3** | 适配接口：对接 Action-probabilities | `core/watermark_sampler.py` | ✅ |
| **P4** | SDK 联调：AgentWatermarker 支持切换算法 | `sdk/watermarker.py` | ✅ |
| **P5** | 鲁棒性验证：弱非对称特性专项测试 | `tests/test_rank_stego.py` | ✅ |

## 4. 关键风险
1. **Embedding Rate (嵌入效率)**：行为级 Action 空间较小（通常 < 10），单步嵌入量较 Token-level 显著下降。 (验证：在 test_rank_stego.py 中 5 个 action 嵌入约 1 bit)
2. **状态同步**：PRG 在编解码两端的调用序列必须严格一致。 (验证：通过 rt_sync 强制递归层数同步)

## 5. 验收标准
- [x] `decode(sample(bits, rank))` 能够 100% 还原比特流。
- [x] 仅修改概率值但不修改行为排名，解码依然正确（弱非对称性验证）。
- [x] 指定 `algorithm='differential'` 时，旧功能保持原样（兼容性验证）。
